"""Operate the active AKGB release, including after automatic main updates."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("status", "start", "stop", "logs", "updater-logs"))
    parser.add_argument("service", nargs="?", choices=("api", "web", "gateway", "postgres"), default="api")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    state = json.loads((root / ".release/current.json").read_text())
    release = Path(state["directory"]).resolve()
    if not release.is_relative_to(root):
        raise SystemExit("Release directory must be inside AKGB")
    environment = {**os.environ, "RELEASE_TAG": state["sha"]}
    compose = ["docker", "compose", "--project-name", "akgb", "--env-file", str(root / "infra/pi/.env"), "-f", str(release / "infra/pi/compose.yaml")]
    updater = ["docker", "compose", "-f", str(root / "infra/pi/updater.compose.yaml")]
    if args.action == "status":
        print("Active release:", state["sha"], "directory:", release, flush=True)
        subprocess.run(compose + ["ps", "-a"], env=environment, check=True)
        subprocess.run(updater + ["ps", "-a"], check=True)
    elif args.action == "stop":
        subprocess.run(updater + ["stop"], check=True)
        subprocess.run(compose + ["stop", "-t", "30"], env=environment, check=True)
    elif args.action == "start":
        subprocess.run(compose + ["up", "-d"], env=environment, check=True)
        subprocess.run(updater + ["up", "-d"], check=True)
    else:
        command = compose + ["logs", "--tail", "100", "-f", args.service]
        if args.action == "updater-logs":
            command = updater + ["logs", "--tail", "100", "-f", "updater"]
        process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for line in process.stdout:
                print(re.sub(r"token=[^&\s]+", "token=[REDACTED]", line), end="", flush=True)
        except KeyboardInterrupt:
            process.terminate()


if __name__ == "__main__":
    main()
