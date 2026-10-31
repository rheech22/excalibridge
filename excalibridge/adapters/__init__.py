"""Notification adapters. Each adapter turns a send event into a wake-up for some agent host.

An adapter is a module with `notify(event: dict, config: dict) -> dict`. The returned dict is
merged into the send response; use {"ok": bool, ...}. The inbox adapter always runs first.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

BUILTIN = {"inbox": "excalibridge.adapters.inbox", "t3": "excalibridge.adapters.t3",
           "herdr": "excalibridge.adapters.herdr", "command": "excalibridge.adapters.command"}


def load(kind: str):
    mod = BUILTIN.get(kind, kind)  # allow dotted path for third-party adapters
    return importlib.import_module(mod)


def dispatch(event: dict, notify_configs: list[dict[str, Any]]) -> list[dict]:
    results = []
    for cfg in [{"type": "inbox"}, *notify_configs]:
        kind = cfg.get("type", "")
        try:
            res = load(kind).notify(event, cfg)
        except Exception as e:  # one failing adapter must not block the others
            res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            print(f"excalibridge: adapter {kind} failed: {e}", file=sys.stderr, flush=True)
        results.append({"type": kind, **res})
    return results
