"""T3 Code adapter: POST the event to a webhook scheduled task bound to a thread.

Config: {"type": "t3", "url": "https://relay.t3.codes/v1/hooks/..."}
In T3, create a scheduled task with schedule {type: "webhook"} and a prompt of `{{body.message}}`.
"""

import json
import urllib.request


def notify(event: dict, config: dict) -> dict:
    url = config["url"]
    body = json.dumps(event).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "User-Agent": "excalibridge/1",  # the relay rejects the default urllib agent
    })
    with urllib.request.urlopen(req, timeout=config.get("timeout", 8)) as r:
        return {"ok": 200 <= r.status < 300, "status": r.status}
