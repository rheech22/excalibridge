"""Core logic shared by the server and the CLI: files, diffs, seen-store, replies, config."""

from __future__ import annotations

import hashlib
import json
import os
import random
import string
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HOME = Path(os.environ.get("EXCALIBRIDGE_HOME", Path.home() / ".excalibridge"))
AGENT_COLOR = "#1971c2"
DEFAULT_PORT = 8765


# --------------------------------------------------------------------------- paths


def find_root(start: Path | None = None) -> Path:
    """Project root: the git top-level if any, else the start directory."""
    start = (start or Path.cwd()).resolve()
    try:
        out = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
        if out:
            return Path(out)
    except Exception:
        pass
    return start


def slug_for(root: Path) -> str:
    h = hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:8]
    return f"{root.name}-{h}"


def rel_path(root: Path, file: str | Path) -> str:
    """Normalize a user-supplied path to a root-relative POSIX path, refusing escapes."""
    raw = str(file)
    root_r = root.resolve()
    # A leading slash means root-relative (what the viewer sends); an absolute path inside the root also works.
    candidates = [root / raw.lstrip("/")]
    if Path(raw).is_absolute():
        candidates.insert(0, Path(raw))
    for cand in candidates:
        abs_p = cand.resolve()
        try:
            rel = abs_p.relative_to(root_r)
        except ValueError:
            continue
        if abs_p.suffix != ".excalidraw":
            raise ValueError("only .excalidraw files are handled")
        return rel.as_posix()
    raise ValueError(f"{file} is outside the project root {root}")


# --------------------------------------------------------------------------- config


@dataclass
class ProjectConfig:
    root: Path
    port: int = DEFAULT_PORT
    notify: list[dict[str, Any]] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return slug_for(self.root)

    @property
    def path(self) -> Path:
        return HOME / "projects" / f"{self.slug}.json"

    @classmethod
    def load(cls, root: Path) -> "ProjectConfig":
        cfg = cls(root=root.resolve())
        if cfg.path.exists():
            data = json.loads(cfg.path.read_text())
            cfg.port = int(data.get("port", DEFAULT_PORT))
            cfg.notify = list(data.get("notify", []))
        return cfg

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"root": str(self.root), "port": self.port, "notify": self.notify},
                                        indent=2) + "\n")
        os.chmod(self.path, 0o600)  # notify entries may hold webhook URLs


def seen_path(root: Path, rel: str) -> Path:
    return HOME / "seen" / slug_for(root) / rel.replace("/", "__")


def inbox_path() -> Path:
    return HOME / "inbox.ndjson"


def run_path(root: Path) -> Path:
    return HOME / "run" / f"{slug_for(root)}.json"


# --------------------------------------------------------------------------- scenes


def empty_scene() -> dict:
    return {"type": "excalidraw", "version": 2, "source": "excalibridge",
            "elements": [], "appState": {"viewBackgroundColor": "#ffffff"}, "files": {}}


def read_scene(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_scene(path: Path, scene: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(scene, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _live(scene: dict) -> dict[str, dict]:
    return {e["id"]: e for e in scene.get("elements", []) if not e.get("isDeleted")}


def brief(e: dict) -> dict:
    out = {"id": e["id"], "type": e["type"], "x": round(e.get("x", 0)), "y": round(e.get("y", 0))}
    if e.get("text") is not None:
        out["text"] = e["text"]
    if e.get("containerId"):
        out["container"] = e["containerId"]
    if e.get("strokeColor"):
        out["color"] = e["strokeColor"]
    return out


def diff_scenes(seen: dict, now: dict) -> dict:
    a, b = _live(seen), _live(now)
    return {
        "added": [brief(e) for i, e in b.items() if i not in a],
        "modified": [brief(e) for i, e in b.items() if i in a and a[i].get("version") != e.get("version")],
        "removed": [brief(e) for i, e in a.items() if i not in b],
    }


def changes_since_seen(root: Path, rel: str) -> dict:
    now = read_scene(root / rel)
    sp = seen_path(root, rel)
    seen = read_scene(sp) if sp.exists() else {"elements": []}
    d = diff_scenes(seen, now)
    d["file"] = rel
    d["count"] = len(d["added"]) + len(d["modified"]) + len(d["removed"])
    return d


def mark_seen(root: Path, rel: str) -> Path:
    sp = seen_path(root, rel)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text((root / rel).read_text(encoding="utf-8"), encoding="utf-8")
    return sp


# --------------------------------------------------------------------------- replies


def _rand_id(n: int = 20) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def estimate_text_box(text: str, font_size: int) -> tuple[float, float]:
    """Rough width/height for a text element; Excalidraw re-measures on edit."""
    lines = text.split("\n")
    def w(line: str) -> float:
        return sum(font_size * (1.0 if ord(ch) > 0x2E7F else 0.58) for ch in line)
    return max((w(l) for l in lines), default=0.0), len(lines) * font_size * 1.25


def text_element(text: str, x: float, y: float, *, color: str = AGENT_COLOR, font_size: int = 12,
                 element_id: str | None = None) -> dict:
    width, height = estimate_text_box(text, font_size)
    now_ms = int(time.time() * 1000)
    return {
        "id": element_id or _rand_id(), "type": "text", "x": x, "y": y, "width": width, "height": height,
        "angle": 0, "strokeColor": color, "backgroundColor": "transparent", "fillStyle": "solid",
        "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [],
        "frameId": None, "roundness": None, "seed": random.randint(1, 2**31 - 1), "version": 1,
        "versionNonce": random.randint(1, 2**31 - 1), "isDeleted": False, "boundElements": [],
        "updated": now_ms, "link": None, "locked": False, "text": text, "fontSize": font_size,
        "fontFamily": 5, "textAlign": "left", "verticalAlign": "top", "containerId": None,
        "originalText": text, "autoResize": True, "lineHeight": 1.25,
    }


def add_reply(root: Path, rel: str, text: str, *, near: str | None = None, at: tuple[float, float] | None = None,
              prefix: str = "A: ", color: str = AGENT_COLOR, font_size: int = 12) -> dict:
    """Append an agent reply (blue text) below `near` element or at explicit coordinates."""
    path = root / rel
    scene = read_scene(path)
    if at is None:
        if near is None:
            raise ValueError("pass near=<element id> or at=(x, y)")
        anchor = next((e for e in scene["elements"] if e["id"] == near and not e.get("isDeleted")), None)
        if anchor is None:
            raise ValueError(f"element {near} not found in {rel}")
        at = (anchor["x"], anchor["y"] + anchor.get("height", 20) + 8)
    el = text_element(prefix + text if prefix and not text.startswith(prefix) else text, at[0], at[1],
                      color=color, font_size=font_size)
    scene["elements"].append(el)
    write_scene(path, scene)
    return brief(el)


# --------------------------------------------------------------------------- events


def build_message(event: dict) -> str:
    """The instruction an agent receives when the send button is pressed."""
    note = f' Note from the author: "{event["note"]}".' if event.get("note") else ""
    return (
        f"[excalibridge] The canvas {event['file']} was sent to you ({event.get('changes', 0)} changed element(s))."
        f"{note} In {event['root']}, run `excalibridge changes {event['file']}` to read what changed since you "
        f"last looked. Answer questions on the canvas with `excalibridge reply {event['file']} --near <id> "
        f"\"...\"` and apply requests, then run `excalibridge seen {event['file']}`. Report in two or three "
        f"sentences. Follow the SKILL.md of excalibridge for the notation rules."
    )


def make_event(root: Path, rel: str, note: str = "", changes: int = 0) -> dict:
    ev = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "root": str(root), "file": rel, "note": note,
          "changes": changes}
    ev["message"] = build_message(ev)
    return ev


def append_inbox(event: dict) -> Path:
    p = inbox_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return p
