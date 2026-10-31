"""Generic adapter: run a shell command with the event in environment variables.

Config: {"type": "command", "run": "my-wake-script.sh"}
Environment: EXB_FILE, EXB_ROOT, EXB_NOTE, EXB_CHANGES, EXB_MESSAGE, EXB_EVENT_JSON.
"""

import json
import os
import subprocess


def notify(event: dict, config: dict) -> dict:
    env = dict(os.environ, EXB_FILE=event["file"], EXB_ROOT=event["root"], EXB_NOTE=event.get("note", ""),
               EXB_CHANGES=str(event.get("changes", 0)), EXB_MESSAGE=event["message"],
               EXB_EVENT_JSON=json.dumps(event))
    p = subprocess.run(config["run"], shell=True, env=env, cwd=event["root"], capture_output=True, text=True,
                       timeout=config.get("timeout", 20))
    return {"ok": p.returncode == 0, "code": p.returncode, "stderr": p.stderr.strip()[-300:]}
