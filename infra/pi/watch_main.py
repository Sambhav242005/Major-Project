"""Pi-owned AKGB updater. Poll successful main CI; deploy only this project.

No inbound webhook, repository write token, cron entry or host-service change.
State, releases, logs and database backups remain under the AKGB directory.
"""

import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time
import urllib.request

REPOSITORY = "Sambhav242005/Major-Project"


def read_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AKGB-Pi-updater", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def extract_application(archive: Path, destination: Path):
    """Extract only regular application/configuration files, without secrets."""
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as source:
        for member in source:
            parts = Path(member.name).parts[1:]
            if not member.isfile() or not parts:
                continue
            relative = Path(*parts)
            if relative.is_absolute() or ".." in parts:
                raise ValueError("Unsafe release archive path")
            if parts[0] not in {"apps", "infra"} or any(p in {"node_modules", ".next", "__pycache__"} for p in parts):
                continue
            if any(p.startswith(".env") for p in parts):
                continue
            target = destination / relative
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Release path escapes destination through a symlink")
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(member) as stream, target.open("wb") as out:
                shutil.copyfileobj(stream, out)


class Updater:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.state_dir = self.root / ".release"
        self.state_dir.mkdir(exist_ok=True)
        self.env_file = self.root / "infra/pi/.env"

    def compose(self, release, tag, *args, capture=False):
        environment = {**os.environ, "RELEASE_TAG": tag}
        return subprocess.run(
            ["docker", "compose", "--project-name", "akgb", "--env-file", str(self.env_file), "-f", str(Path(release) / "infra/pi/compose.yaml"), *args],
            env=environment, check=True, text=True,
            stdout=subprocess.PIPE if capture else None,
            timeout=2400,
        )

    def validate(self, release, tag):
        config = json.loads(self.compose(release, tag, "config", "--format", "json", capture=True).stdout)
        if config.get("secrets") or config.get("configs"):
            raise ValueError("Additional secret/config file mounts are not allowed")
        if set(config["services"]) != {"postgres", "api", "web", "gateway"}:
            raise ValueError("Updater accepts only the four AKGB application services")
        for name, service in config["services"].items():
            if service.get("privileged") or service.get("network_mode") == "host" or service.get("pid") == "host":
                raise ValueError("Host privilege configuration is not allowed")
            if any(service.get(field) for field in ("devices", "device_cgroup_rules", "cap_add", "volumes_from", "external_links")):
                raise ValueError("Additional host capabilities are not allowed")
            if service.get("use_api_socket"):
                raise ValueError("Application services cannot mount the Docker API")
            if any(str(service.get(field, "")).startswith("container:") for field in ("network_mode", "pid", "ipc")):
                raise ValueError("Foreign container namespaces are not allowed")
            if service.get("container_name") and service["container_name"] != f"akgb-{name}-1":
                raise ValueError("Unrelated container name is not allowed")
            if service.get("ipc") == "host" or service.get("uts") == "host":
                raise ValueError("Host namespaces are not allowed")
            for port in service.get("ports", []):
                if not 9900 <= int(port["published"]) <= 9910:
                    raise ValueError("Published port outside authorized AKGB range")
            for volume in service.get("volumes", []):
                if volume["type"] == "bind" and not Path(volume["source"]).resolve().is_relative_to(self.root):
                    raise ValueError("Bind mount outside AKGB folder")
                if volume["type"] == "volume" and volume["source"] not in {"postgres_data", "api_data", "gateway_data", "gateway_config"}:
                    raise ValueError("Unknown data volume")
            if name in {"postgres", "gateway"} and service.get("build"):
                raise ValueError("Only application services may build images")
            if name in {"api", "web"} and service.get("build"):
                context = Path(service["build"]["context"]).resolve()
                if not context.is_relative_to(Path(release).resolve()):
                    raise ValueError("Build context outside release")
                dockerfile = (context / service["build"].get("dockerfile", "Dockerfile")).resolve()
                if not dockerfile.is_relative_to(Path(release).resolve()):
                    raise ValueError("Dockerfile outside release")
                if service["build"].get("additional_contexts") or service["build"].get("ssh"):
                    raise ValueError("Additional build inputs are not allowed")
        for definition in config.get("volumes", {}).values():
            if definition.get("external") or definition.get("driver_opts") or not definition.get("name", "").startswith("akgb_"):
                raise ValueError("External or unrelated volume is not allowed")
        for definition in config.get("networks", {}).values():
            if definition.get("external") or definition.get("driver_opts") or not definition.get("name", "").startswith("akgb_"):
                raise ValueError("External or unrelated network is not allowed")

    def backup_database(self, release, tag):
        backup = self.state_dir / "backups"
        backup.mkdir(exist_ok=True)
        filename = backup / (time.strftime("%Y%m%d_%H%M%S") + ".sql.gz")
        result = self.compose(release, tag, "exec", "-T", "postgres", "pg_dump", "-U", "akgb", "-d", "akgb", capture=True)
        with gzip.open(filename, "wt") as target:
            target.write(result.stdout)
        os.chmod(filename, 0o600)

    def deploy(self, release, tag):
        self.validate(release, tag)
        self.compose(release, tag, "build", "api", "web")
        self.compose(release, tag, "up", "-d", "--no-deps", "postgres")
        for attempt in range(30):
            try:
                self.compose(release, tag, "exec", "-T", "postgres", "pg_isready", "-U", "akgb", "-d", "akgb")
                break
            except subprocess.CalledProcessError:
                if attempt == 29:
                    raise
                time.sleep(2)
        self.backup_database(release, tag)
        self.compose(release, tag, "run", "--rm", "-T", "--no-deps", "api", "alembic", "upgrade", "head")
        self.compose(release, tag, "up", "-d", "--no-deps", "--force-recreate", "api", "web", "gateway")
        import ssl
        ca = self.compose(release, tag, "exec", "-T", "gateway", "cat", "/data/caddy/pki/authorities/local/root.crt", capture=True).stdout
        context = ssl.create_default_context(cadata=ca)
        env = dict(line.split("=", 1) for line in self.env_file.read_text().splitlines() if line and not line.startswith("#") and "=" in line)
        for attempt in range(36):
            try:
                with urllib.request.urlopen(env["APP_URL"].rstrip("/") + "/api/health", context=context, timeout=10) as response:
                    if json.load(response) != {"status": "ok"}:
                        raise ValueError("Unexpected health payload")
                with urllib.request.urlopen(env["APP_URL"].rstrip("/") + "/auth/signin", context=context, timeout=10) as response:
                    if response.status != 200:
                        raise ValueError("Sign-in page unavailable")
                break
            except Exception:
                if attempt == 35:
                    raise
                time.sleep(5)
        current = {"sha": tag, "directory": str(release), "deployed_at": time.time()}
        pending = self.state_dir / "current.tmp"
        pending.write_text(json.dumps(current))
        pending.replace(self.state_dir / "current.json")
        print("AKGB deployment healthy:", tag, flush=True)

    def run(self, interval):
        lock = (self.state_dir / "updater.lock").open("w")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print("AKGB updater watching successful main builds every", interval, "seconds.", flush=True)
        while True:
            try:
                current = json.loads((self.state_dir / "current.json").read_text())
                sha = read_json(f"https://api.github.com/repos/{REPOSITORY}/commits/main")["sha"]
                if not re.fullmatch(r"[0-9a-f]{40}", sha):
                    raise ValueError("Invalid main revision")
                (self.state_dir / "updater_status.json").write_text(json.dumps({"checked_at": time.time(), "main_sha": sha, "deployed_tag": current["sha"]}))
                if sha != current.get("main_sha", current["sha"]):
                    runs = read_json(f"https://api.github.com/repos/{REPOSITORY}/actions/runs?head_sha={sha}&per_page=10")["workflow_runs"]
                    checks = [run for run in runs if run["name"] == "Continuous integration" and run["head_branch"] == "main"]
                    if checks and checks[0]["status"] == "completed" and checks[0]["conclusion"] == "success":
                        release = self.state_dir / "releases" / sha
                        archive = self.state_dir / (sha + ".tar.gz")
                        urllib.request.urlretrieve(f"https://codeload.github.com/{REPOSITORY}/tar.gz/{sha}", archive)
                        extract_application(archive, release)
                        try:
                            self.deploy(release, sha)
                        except Exception:
                            print("Candidate failed. Restoring previous application containers; database migration is NOT automatically reversed.", flush=True)
                            self.compose(current["directory"], current["sha"], "up", "-d", "--no-deps", "--force-recreate", "api", "web", "gateway")
                            raise
                        archive.unlink()
                    else:
                        print("Waiting for successful main CI:", sha, flush=True)
            except Exception as exc:
                print("AKGB updater:", type(exc).__name__, str(exc)[:300], flush=True)
            time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/home/pulkit26/akgb")
    parser.add_argument("--interval", type=int, default=180)
    args = parser.parse_args()
    Updater(args.root).run(max(args.interval, 120))
