"""Always-on adapter: append the event to ~/.excalibridge/inbox.ndjson.

Any agent host can watch that file (tail -F, inotify, a Claude Code hook) to wake an agent.
"""

from excalibridge.core import append_inbox


def notify(event: dict, config: dict) -> dict:
    return {"ok": True, "path": str(append_inbox(event))}
