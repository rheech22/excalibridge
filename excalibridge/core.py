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
USER_COLOR = "#1e1e1e"
QUESTION_COLOR = "#e67700"
DEFAULT_PORT = 8765
DEFAULT_LABELS = {"answer": "Answer: ", "reply": "A: ", "question": "Q"}


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
    labels: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_LABELS))

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
            cfg.labels = {**DEFAULT_LABELS, **data.get("labels", {})}
        return cfg

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"root": str(self.root), "port": self.port, "notify": self.notify,
                                         "labels": self.labels}, ensure_ascii=False, indent=2) + "\n")
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


def _signature(e: dict) -> tuple:
    """What counts as a meaningful change. Excalidraw bumps `version` for re-measured text,
    selection nudges, and other noise, so we compare content and placement instead."""
    sig = [e.get("type"), e.get("text"), round(e.get("x", 0)), round(e.get("y", 0)), e.get("strokeColor"),
           e.get("backgroundColor"), e.get("containerId"), e.get("strokeStyle"), e.get("opacity"),
           tuple(tuple(round(v) for v in pt) for pt in e.get("points", []) or [])]
    if e.get("type") != "text":  # text boxes auto-resize; their size is not a user edit
        sig += [round(e.get("width", 0)), round(e.get("height", 0))]
    return tuple(sig)


def diff_scenes(seen: dict, now: dict, labels: dict[str, str] | None = None) -> dict:
    a, b = _live(seen), _live(now)
    answer = (labels or DEFAULT_LABELS)["answer"].strip()
    cards = [e for e in b.values() if e.get("customData", {}).get("excalibridge") == "question"]

    def annotate(e: dict) -> dict:
        out = brief(e)
        text = (e.get("text") or "").strip()
        if e.get("type") == "text" and text.startswith(answer):
            out["role"] = "answer"
            out["answer"] = text[len(answer):].strip()
            for c in cards:  # which question card contains this answer line?
                if c["x"] <= e.get("x", 0) <= c["x"] + c.get("width", 0) and c["y"] <= e.get("y", 0) <= c["y"] + c.get("height", 0):
                    out["question"] = c["customData"].get("title")
                    out["questionId"] = c["id"]
        return out

    return {
        "added": [annotate(e) for i, e in b.items() if i not in a],
        "modified": [annotate(e) for i, e in b.items() if i in a and _signature(a[i]) != _signature(e)],
        "removed": [brief(e) for i, e in a.items() if i not in b],
    }


def changes_since_seen(root: Path, rel: str, labels: dict[str, str] | None = None) -> dict:
    now = read_scene(root / rel)
    sp = seen_path(root, rel)
    seen = read_scene(sp) if sp.exists() else {"elements": []}
    d = diff_scenes(seen, now, labels)
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
    """Agent reply. Near a question card it extends the card; near anything else it adds a callout box
    under it; with explicit coordinates it is a plain wrapped text. Things below are pushed down."""
    from excalibridge import layout
    path = root / rel
    scene = read_scene(path)
    body = prefix + text if prefix and not text.startswith(prefix) else text
    if at is not None:
        el = text_element(layout.wrap(body, 480, font_size), at[0], at[1], color=color, font_size=font_size)
        scene["elements"].append(el)
        write_scene(path, scene)
        return brief(el)
    if near is None:
        raise ValueError("pass near=<element id> or at=(x, y)")
    anchor = next((e for e in scene["elements"] if e["id"] == near and not e.get("isDeleted")), None)
    if anchor is None:
        raise ValueError(f"element {near} not found in {rel}")
    new = layout.reply_near(scene, anchor, body, color=color, font_size=font_size)
    write_scene(path, scene)
    txt = next(e for e in new if e["type"] == "text")
    return {**brief(txt), "mode": "card" if layout._question_card_for(scene, anchor) else "callout"}


# --------------------------------------------------------------------------- question cards


def _base(kind: str, x: float, y: float, w: float, h: float, **extra) -> dict:
    now_ms = int(time.time() * 1000)
    el = {"id": _rand_id(), "type": kind, "x": x, "y": y, "width": w, "height": h, "angle": 0,
          "strokeColor": USER_COLOR, "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 1,
          "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
          "roundness": None, "seed": random.randint(1, 2**31 - 1), "version": 1,
          "versionNonce": random.randint(1, 2**31 - 1), "isDeleted": False, "boundElements": [],
          "updated": now_ms, "link": None, "locked": False}
    el.update(extra)
    return el


def _wrap(text: str, max_chars: int) -> str:
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            if line and len(line) + 1 + len(word) > max_chars:
                out.append(line); line = word
            else:
                line = f"{line} {word}" if line else word
        out.append(line)
    return "\n".join(out)


def next_question_number(scene: dict, label: str = "Q") -> int:
    """One past the highest existing question number, counting both cards made by `ask` and any
    hand-written heading that starts with the question label and a number (e.g. "Q7 · topic")."""
    import re
    nums = [int(e["customData"].get("number", 0)) for e in scene.get("elements", [])
            if not e.get("isDeleted") and e.get("customData", {}).get("excalibridge") == "question"]
    pat = re.compile(rf"^{re.escape(label)}\s*(\d+)\b")
    for e in scene.get("elements", []):
        if e.get("type") == "text" and not e.get("isDeleted"):
            for line in (e.get("text") or "").split("\n"):
                m = pat.match(line.strip())
                if m:
                    nums.append(int(m.group(1)))
    return max(nums, default=0) + 1


def add_question(root: Path, rel: str, question: str, *, title: str | None = None, at: tuple[float, float] | None = None,
                 width: float = 420, labels: dict[str, str] | None = None, number: int | None = None,
                 section: int | None = None) -> dict:
    """Append a question card: title, question text, a dashed rule, and an answer line the user
    double-clicks to complete. The answer line is in the user's colour so nothing needs restyling."""
    from excalibridge import layout
    labels = {**DEFAULT_LABELS, **(labels or {})}
    path = root / rel
    scene = read_scene(path)
    n = number if number is not None else next_question_number(scene, labels["question"])
    heading = f"{labels['question']}{n}" + (f" · {title}" if title else "")
    body = layout.wrap(question, width - 24, 12)
    body_h = max(30.0, estimate_text_box(body, 12)[1])
    frame = layout.current_section(scene, section)
    if at is None:
        at = layout.place_in_section(scene, frame, width)
    x, y = at
    h = 34 + body_h + 16 + 1 + 12 + 30
    card = _base("rectangle", x, y, width, h, strokeColor=QUESTION_COLOR, backgroundColor="#fff9db", roundness={"type": 3},
                 customData={"excalibridge": "question", "number": n, "title": title or "", "question": question})
    els = [card,
           text_element(heading, x + 12, y + 10, color=QUESTION_COLOR, font_size=14),
           text_element(body, x + 12, y + 34, color=USER_COLOR, font_size=12),
           _base("line", x + 12, y + 34 + body_h + 12, width - 24, 0, strokeColor=QUESTION_COLOR, strokeStyle="dashed",
                 points=[[0, 0], [width - 24, 0]], lastCommittedPoint=None, startBinding=None, endBinding=None,
                 startArrowhead=None, endArrowhead=None),
           text_element(labels["answer"], x + 12, y + 34 + body_h + 24, color=USER_COLOR, font_size=12)]
    for e in els[1:]:
        e["seed"] = random.randint(1, 2**31 - 1)
    scene["elements"].extend(els)
    layout.adopt(scene, frame, els)
    write_scene(path, scene)
    return {"id": card["id"], "number": n, "title": title or "", "x": x, "y": y, "width": width, "height": h,
            "answerId": els[-1]["id"], "section": int(frame["customData"]["index"]) if frame else None}


def add_section(root: Path, rel: str, title: str, *, width: float = 900, height: float = 260,
                at: tuple[float, float] | None = None, wrap_y: tuple[float, float] | None = None) -> dict:
    from excalibridge import layout
    path = root / rel
    scene = read_scene(path)
    fr = layout.add_section(scene, title, width=width, height=height, at=at, wrap_y=wrap_y)
    write_scene(path, scene)
    return {"id": fr["id"], "index": fr["customData"]["index"], "title": title, "x": fr["x"], "y": fr["y"],
            "width": fr["width"], "height": fr["height"]}


def tidy(root: Path, rel: str) -> dict:
    from excalibridge import layout
    path = root / rel
    scene = read_scene(path)
    out = layout.tidy(scene)
    write_scene(path, scene)
    return out


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
