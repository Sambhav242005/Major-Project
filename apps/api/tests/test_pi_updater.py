"""Offline safety and successful-main-only deployment checks; never invoke Docker."""

import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def updater_module(monkeypatch):
    # Production runs Linux. Supply only the lock API for Windows offline tests.
    if sys.platform == "win32":
        monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=lambda *_: None))
    path = Path(__file__).resolve().parents[3] / "infra/pi/watch_main.py"
    spec = importlib.util.spec_from_file_location("akgb_pi_updater_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def archive_at(path, records):
    with tarfile.open(path, "w:gz") as archive:
        for name, content, kind in records:
            member = tarfile.TarInfo(name)
            member.type = kind
            if kind == tarfile.REGTYPE:
                data = content.encode()
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            else:
                member.linkname = content
                archive.addfile(member)
    return path


def test_archive_extracts_only_application_files_without_secrets_or_links(updater_module, tmp_path):
    archive = archive_at(tmp_path / "release.tar.gz", [
        ("repo/apps/api/main.py", "safe", tarfile.REGTYPE),
        ("repo/infra/pi/compose.yaml", "safe", tarfile.REGTYPE),
        ("repo/Assets/context.txt", "private", tarfile.REGTYPE),
        ("repo/docs/paper.pdf", "private", tarfile.REGTYPE),
        ("repo/apps/api/.env", "SECRET=value", tarfile.REGTYPE),
        ("repo/apps/web/.env.production", "SECRET=value", tarfile.REGTYPE),
        ("repo/apps/web/node_modules/library/file", "skip", tarfile.REGTYPE),
        ("repo/apps/api/link", "/etc/passwd", tarfile.SYMTYPE),
        ("repo/apps/api/hardlink", "repo/apps/api/main.py", tarfile.LNKTYPE),
    ])
    destination = tmp_path / "release"
    updater_module.extract_application(archive, destination)
    assert sorted(str(p.relative_to(destination)).replace("\\", "/") for p in destination.rglob("*") if p.is_file()) == ["apps/api/main.py", "infra/pi/compose.yaml"]


def test_archive_rejects_parent_traversal(updater_module, tmp_path):
    archive = archive_at(tmp_path / "release.tar.gz", [("repo/apps/../../escape", "unsafe", tarfile.REGTYPE)])
    with pytest.raises(ValueError):
        updater_module.extract_application(archive, tmp_path / "release")
    assert not (tmp_path / "escape").exists()


def test_archive_rejects_existing_symlink_escape(updater_module, tmp_path):
    destination = tmp_path / "release"
    (destination / "apps").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (destination / "apps/api").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks is not permitted on this Windows host")
    archive = archive_at(tmp_path / "release.tar.gz", [("repo/apps/api/escape", "unsafe", tarfile.REGTYPE)])
    with pytest.raises(ValueError):
        updater_module.extract_application(archive, destination)
    assert not (outside / "escape").exists()


@pytest.fixture
def deployment(updater_module, tmp_path):
    root = tmp_path / "akgb"
    root.mkdir()
    instance = updater_module.Updater(root)
    release = root / ".release/releases/candidate"
    release.mkdir(parents=True)
    config = {
        "services": {name: {} for name in ["postgres", "api", "web", "gateway"]},
        "volumes": {name: {"name": "akgb_" + name} for name in ["postgres_data", "api_data", "gateway_data", "gateway_config"]},
    }
    config["services"]["api"] = {"build": {"context": str(release / "apps/api")}, "ports": [{"published": "9901"}], "volumes": [{"type": "volume", "source": "api_data", "target": "/data"}]}
    config["services"]["web"] = {"build": {"context": str(release / "apps/web")}}
    config["services"]["gateway"] = {"ports": [{"published": "9900"}], "volumes": [{"type": "bind", "source": str(release / "infra/pi/Caddyfile"), "target": "/etc/caddy/Caddyfile"}]}
    return instance, release, config


def validate_config(instance, release, config):
    instance.compose = Mock(return_value=SimpleNamespace(stdout=json.dumps(config)))
    instance.validate(release, "candidate")


def test_accepts_only_isolated_akgb_configuration(deployment):
    instance, release, config = deployment
    validate_config(instance, release, config)


@pytest.mark.parametrize("mutation", [
    lambda c, r: c["services"].update({"foreign": {}}),
    lambda c, r: c["services"]["api"].update(privileged=True),
    lambda c, r: c["services"]["api"].update(network_mode="host"),
    lambda c, r: c["services"]["api"].update(pid="host"),
    lambda c, r: c["services"]["api"].update(ports=[{"published": "22"}]),
    lambda c, r: c["services"]["api"].update(volumes=[{"type": "bind", "source": str(r.parent.parent.parent.parent / "foreign"), "target": "/foreign"}]),
    lambda c, r: c["services"]["api"].update(volumes=[{"type": "volume", "source": "foreign_data", "target": "/foreign"}]),
    lambda c, r: c["volumes"]["api_data"].update(external=True),
    lambda c, r: c["volumes"]["api_data"].update(name="foreign_data"),
    lambda c, r: c["services"]["api"]["build"].update(context=str(r.parent.parent.parent.parent / "foreign")),
    lambda c, r: c["services"]["api"]["build"].update(dockerfile=str(r.parent.parent.parent.parent / "foreign/Dockerfile")),
    lambda c, r: c["services"]["api"]["build"].update(additional_contexts={"outside": str(r.parent.parent.parent.parent / "foreign")}),
    lambda c, r: c["volumes"]["api_data"].update(driver_opts={"type": "none", "o": "bind", "device": "/etc"}),
    lambda c, r: c["services"]["api"].update(devices=["/dev/mem:/dev/mem"]),
    lambda c, r: c["services"]["api"].update(cap_add=["SYS_ADMIN"]),
    lambda c, r: c.update(networks={"foreign": {"external": True, "name": "foreign_default"}}),
    lambda c, r: c["services"]["postgres"].update(build={"context": str(r.parent.parent.parent.parent / "foreign")}),
    lambda c, r: c["services"]["api"].update(network_mode="container:foreign-service"),
    lambda c, r: c["services"]["api"].update(pid="container:foreign-service"),
    lambda c, r: c["services"]["api"].update(ipc="container:foreign-service"),
    lambda c, r: c["services"]["api"].update(use_api_socket=True),
])
def test_rejects_scope_and_privilege_escapes(deployment, mutation):
    instance, release, original = deployment
    config = copy.deepcopy(original)
    mutation(config, release)
    with pytest.raises(ValueError):
        validate_config(instance, release, config)


class StopPolling(BaseException):
    pass


def poll_once(module, instance, monkeypatch, sha, runs):
    def read(url):
        return {"sha": sha} if "/commits/main" in url else {"workflow_runs": runs}
    monkeypatch.setattr(module, "read_json", read)
    monkeypatch.setattr(module.time, "sleep", Mock(side_effect=StopPolling))
    with pytest.raises(StopPolling):
        instance.run(180)


def current_state(instance, sha="a" * 40, main_sha=None):
    current = {"sha": sha, "directory": str(instance.root / "old")}
    if main_sha:
        current["main_sha"] = main_sha
    (instance.state_dir / "current.json").write_text(json.dumps(current))
    return current


@pytest.mark.parametrize("runs", [[], [{"name": "Continuous integration", "head_branch": "main", "status": "completed", "conclusion": "failure"}], [{"name": "Continuous integration", "head_branch": "main", "status": "in_progress", "conclusion": None}], [{"name": "Continuous integration", "head_branch": "feature", "status": "completed", "conclusion": "success"}], [{"name": "Unrelated workflow", "head_branch": "main", "status": "completed", "conclusion": "success"}]])
def test_requires_completed_successful_main_ci(updater_module, deployment, monkeypatch, runs):
    instance, _, _ = deployment
    current_state(instance)
    instance.deploy = Mock()
    download = Mock()
    monkeypatch.setattr(updater_module.urllib.request, "urlretrieve", download)
    poll_once(updater_module, instance, monkeypatch, "b" * 40, runs)
    instance.deploy.assert_not_called()
    download.assert_not_called()


def test_tracks_main_sha_and_does_not_redeploy_same_revision(updater_module, deployment, monkeypatch):
    instance, _, _ = deployment
    sha = "b" * 40
    current_state(instance, main_sha=sha)
    instance.deploy = Mock()
    poll_once(updater_module, instance, monkeypatch, sha, [])
    instance.deploy.assert_not_called()


def test_successful_main_ci_downloads_and_deploys_that_exact_commit(updater_module, deployment, monkeypatch):
    instance, _, _ = deployment
    current_state(instance)
    sha = "b" * 40
    download_urls = []
    def download(url, path):
        download_urls.append(url)
        Path(path).write_bytes(b"archive")
    monkeypatch.setattr(updater_module.urllib.request, "urlretrieve", download)
    extract = Mock()
    monkeypatch.setattr(updater_module, "extract_application", extract)
    instance.deploy = Mock()
    runs = [{"name": "Continuous integration", "head_branch": "main", "head_sha": sha, "status": "completed", "conclusion": "success"}]
    poll_once(updater_module, instance, monkeypatch, sha, runs)
    release = instance.state_dir / "releases" / sha
    instance.deploy.assert_called_once_with(release, sha)
    extract.assert_called_once_with(instance.state_dir / (sha + ".tar.gz"), release)
    assert download_urls == [f"https://codeload.github.com/{updater_module.REPOSITORY}/tar.gz/{sha}"]
    assert not (instance.state_dir / (sha + ".tar.gz")).exists()


def test_compose_command_is_scoped_to_project_and_private_env(deployment, monkeypatch, updater_module):
    instance, release, _ = deployment
    runner = Mock(return_value=SimpleNamespace(stdout="{}"))
    monkeypatch.setattr(updater_module.subprocess, "run", runner)
    instance.compose(release, "b" * 40, "config", "--format", "json", capture=True)
    command = runner.call_args.args[0]
    assert command[:4] == ["docker", "compose", "--project-name", "akgb"]
    assert command[command.index("--env-file") + 1] == str(instance.root / "infra/pi/.env")
    assert command[command.index("-f") + 1] == str(release / "infra/pi/compose.yaml")
    assert runner.call_args.kwargs["check"] is True
    assert runner.call_args.kwargs["env"]["RELEASE_TAG"] == "b" * 40


def test_failed_deployment_restores_only_previous_application_containers(updater_module, deployment, monkeypatch):
    instance, _, _ = deployment
    previous = current_state(instance)
    instance.deploy = Mock(side_effect=RuntimeError("build failed"))
    instance.compose = Mock()
    monkeypatch.setattr(updater_module, "extract_application", Mock())
    monkeypatch.setattr(updater_module.urllib.request, "urlretrieve", Mock())
    runs = [{"name": "Continuous integration", "head_branch": "main", "head_sha": "b" * 40, "status": "completed", "conclusion": "success"}]
    poll_once(updater_module, instance, monkeypatch, "b" * 40, runs)
    instance.compose.assert_called_once_with(previous["directory"], previous["sha"], "up", "-d", "--no-deps", "--force-recreate", "api", "web", "gateway")
    assert json.loads((instance.state_dir / "current.json").read_text()) == previous
