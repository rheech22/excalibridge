"""Layout helpers: text wrapping, pushing elements out of the way, sections (Excalidraw frames),
question-card replies, and free-standing callouts. Everything here works on the plain scene dict."""

from __future__ import annotations

import random
import time

from excalibridge import core

GAP = 60            # between sections
PAD = 24            # inside a section
CANVAS_WIDTH = 2000  # sections flow to the right until this, then wrap to a new row


# ----------------------------------------------------------------------------- geometry


def _live(scene: dict) -> list[dict]:
    return [e for e in scene.get("elements", []) if not e.get("isDeleted")]


def bounds(e: dict) -> tuple[float, float, float, float]:
    return e["x"], e["y"], e["x"] + e.get("width", 0), e["y"] + e.get("height", 0)


def content_bottom(elements: list[dict]) -> float:
    return max((bounds(e)[3] for e in elements), default=0.0)


def push_down(scene: dict, threshold_y: float, x0: float, x1: float, dy: float, exclude: set[str] = frozenset()) -> int:
    """Move everything that starts at or below `threshold_y` and overlaps [x0, x1] down by dy.
    Frames that straddle the threshold grow instead of moving. Returns the number of touched elements."""
    n = 0
    for e in _live(scene):
        if e["id"] in exclude:
            continue
        ex0, ey0, ex1, ey1 = bounds(e)
        if not (ex0 < x1 and ex1 > x0):
            continue
        if e["type"] == "frame":
            if ey0 >= threshold_y - 0.5:
                e["y"] += dy
            elif ey1 >= threshold_y - 0.5:
                e["height"] += dy
            else:
                continue
        elif ey0 >= threshold_y - 0.5:
            e["y"] += dy
        else:
            continue
        e["version"] = e.get("version", 1) + 1
        n += 1
    return n


def wrap(text: str, width_px: float, font_size: int) -> str:
    """Greedy wrap by estimated glyph width (CJK ≈ 1em, others ≈ 0.58em). Keeps existing newlines."""
    def w(s: str) -> float:
        return sum(font_size * (1.0 if ord(c) > 0x2E7F else 0.58) for c in s)
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            cand = f"{line} {word}" if line else word
            if line and w(cand) > width_px:
                out.append(line)
                line = word
            else:
                line = cand
            while w(line) > width_px and len(line) > 1:  # a single over-long token (long CJK run)
                cut = max(1, int(len(line) * width_px / w(line)))
                out.append(line[:cut])
                line = line[cut:]
        out.append(line)
    return "\n".join(out)


# ----------------------------------------------------------------------------- sections (frames)


def sections(scene: dict) -> list[dict]:
    secs = [e for e in _live(scene) if e["type"] == "frame" and e.get("customData", {}).get("excalibridge") == "section"]
    return sorted(secs, key=lambda e: int(e["customData"].get("index", 0)))


def current_section(scene: dict, index: int | None = None) -> dict | None:
    secs = sections(scene)
    if not secs:
        return None
    if index is None:
        return secs[-1]
    return next((s for s in secs if int(s["customData"]["index"]) == index), None)


def _frame(title: str, x: float, y: float, w: float, h: float, index: int) -> dict:
    return {
        "id": core._rand_id(), "type": "frame", "x": x, "y": y, "width": w, "height": h, "angle": 0,
        "strokeColor": "#bbb", "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 2,
        "strokeStyle": "solid", "roughness": 0, "opacity": 100, "groupIds": [], "frameId": None, "roundness": None,
        "seed": random.randint(1, 2**31 - 1), "version": 1, "versionNonce": random.randint(1, 2**31 - 1),
        "isDeleted": False, "boundElements": [], "updated": int(time.time() * 1000), "link": None, "locked": False,
        "name": title, "customData": {"excalibridge": "section", "index": index, "title": title},
    }


def add_section(scene: dict, title: str, *, width: float = 900, height: float = 260, at: tuple[float, float] | None = None,
                wrap_y: tuple[float, float] | None = None, canvas_width: float = CANVAS_WIDTH) -> dict:
    """Add a titled frame. With `wrap_y`, wrap the existing elements whose top lies in that y-range (no moving).
    Otherwise place it to the right of the last section, or on a new row when the canvas width is exceeded."""
    secs = sections(scene)
    index = max((int(s["customData"]["index"]) for s in secs), default=0) + 1
    if wrap_y is not None:
        y0, y1 = wrap_y
        inside = [e for e in _live(scene) if e["type"] != "frame" and y0 <= e["y"] < y1]
        if not inside:
            raise ValueError("no elements in that y-range")
        xs0 = min(bounds(e)[0] for e in inside); ys0 = min(bounds(e)[1] for e in inside)
        xs1 = max(bounds(e)[2] for e in inside); ys1 = max(bounds(e)[3] for e in inside)
        fr = _frame(title, xs0 - PAD, ys0 - PAD, xs1 - xs0 + 2 * PAD, ys1 - ys0 + 2 * PAD, index)
        for e in inside:
            e["frameId"] = fr["id"]
    else:
        if at is not None:
            x, y = at
        elif not secs:
            x, y = 40.0, (content_bottom(_live(scene)) + GAP if _live(scene) else 40.0)
        else:
            last = secs[-1]
            x, y = last["x"] + last["width"] + GAP, last["y"]
            if x + width > canvas_width:
                x, y = 40.0, max(bounds(s)[3] for s in secs) + GAP
        fr = _frame(title, x, y, width, height, index)
    scene["elements"].append(fr)
    return fr


def _grow_section_to_fit(scene: dict, frame: dict | None, needed_bottom: float) -> None:
    """Grow the frame so `needed_bottom` (+ padding) fits, pushing whatever lies below the frame."""
    if frame is None:
        return
    want = needed_bottom + PAD
    cur = frame["y"] + frame["height"]
    if want > cur:
        dy = want - cur
        push_down(scene, cur + 1, frame["x"], frame["x"] + frame["width"], dy, exclude={frame["id"]})
        frame["height"] += dy
        frame["version"] = frame.get("version", 1) + 1


def place_in_section(scene: dict, frame: dict | None, width: float) -> tuple[float, float]:
    """Top-left for a new block inside the frame (below its current content), or below everything if no frame."""
    live = _live(scene)
    if frame is None:
        return 40.0, content_bottom(live) + GAP if live else 40.0
    members = [e for e in live if e.get("frameId") == frame["id"]]
    y = (content_bottom(members) + PAD) if members else frame["y"] + 48
    return frame["x"] + PAD, y


def adopt(scene: dict, frame: dict | None, new_elements: list[dict]) -> None:
    if frame is None:
        return
    for e in new_elements:
        e["frameId"] = frame["id"]
    _grow_section_to_fit(scene, frame, max(bounds(e)[3] for e in new_elements))


# ----------------------------------------------------------------------------- replies


def _question_card_for(scene: dict, el: dict) -> dict | None:
    if el.get("customData", {}).get("excalibridge") == "question":
        return el
    x, y = el["x"], el["y"]
    for c in _live(scene):
        if c.get("customData", {}).get("excalibridge") == "question":
            cx0, cy0, cx1, cy1 = bounds(c)
            if cx0 <= x <= cx1 and cy0 <= y <= cy1:
                return c
    return None


def _frame_of(scene: dict, el: dict) -> dict | None:
    fid = el.get("frameId")
    return next((f for f in _live(scene) if f["id"] == fid), None) if fid else None


def reply_near(scene: dict, anchor: dict, text: str, *, color: str = core.AGENT_COLOR, font_size: int = 12,
               max_width: float = 480) -> list[dict]:
    """Inside a question card: add a blue dashed rule and the wrapped reply, grow the card, push things below.
    Elsewhere: a blue callout box of the anchor's width directly under it, pushing things below."""
    card = _question_card_for(scene, anchor)
    frame = _frame_of(scene, card or anchor)
    if card is not None:
        inner_w = card["width"] - 24
        body = wrap(text, inner_w, font_size)
        _, th = core.estimate_text_box(body, font_size)
        old_bottom = card["y"] + card["height"]
        x = card["x"] + 12
        y = old_bottom - 12  # the card keeps 12px bottom padding
        rule = core._base("line", x, y, inner_w, 0, strokeColor=color, strokeStyle="dashed", points=[[0, 0], [inner_w, 0]],
                          lastCommittedPoint=None, startBinding=None, endBinding=None, startArrowhead=None, endArrowhead=None)
        txt = core.text_element(body, x, y + 10, color=color, font_size=font_size)
        grow = 10 + th + 12
        push_down(scene, old_bottom + 1, card["x"], card["x"] + card["width"], grow, exclude={card["id"]})
        card["height"] += grow
        card["version"] = card.get("version", 1) + 1
        new = [rule, txt]
    else:
        ax0, ay0, ax1, ay1 = bounds(anchor)
        w = min(max(ax1 - ax0, 320), max_width)
        body = wrap(text, w - 24, font_size)
        _, th = core.estimate_text_box(body, font_size)
        h = th + 24
        y = ay1 + 8
        push_down(scene, y, ax0, ax0 + w, h + 16)
        box = core._base("rectangle", ax0, y, w, h, strokeColor=color, backgroundColor="#e7f5ff", roundness={"type": 3})
        tick = core._base("line", ax0 + 20, ay1, 0, 8, strokeColor=color, points=[[0, 0], [0, 8]],
                          lastCommittedPoint=None, startBinding=None, endBinding=None, startArrowhead=None, endArrowhead=None)
        txt = core.text_element(body, ax0 + 12, y + 12, color=color, font_size=font_size)
        new = [box, tick, txt]
    for e in new:
        e["frameId"] = (card or anchor).get("frameId")
    scene["elements"].extend(new)
    if frame is not None:
        _grow_section_to_fit(scene, frame, max(bounds(e)[3] for e in new))
    return new
