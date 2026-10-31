"""herdr adapter: submit the message as a prompt to an agent pane via `herdr agent prompt`.

Config: {"type": "herdr", "target": "<agent name or id>", "wait": false}
"""

import shutil
import subprocess


def notify(event: dict, config: dict) -> dict:
    exe = shutil.which("herdr")
    if not exe:
        return {"ok": False, "error": "herdr not found on PATH"}
    cmd = [exe, "agent", "prompt", str(config["target"]), event["message"]]
    if config.get("wait"):
        cmd += ["--wait", "--timeout", str(int(config.get("timeout_ms", 10000)))]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=config.get("timeout_ms", 10000) / 1000 + 5)
    return {"ok": p.returncode == 0, "stdout": p.stdout.strip()[-300:], "stderr": p.stderr.strip()[-300:]}
