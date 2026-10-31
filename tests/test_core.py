import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ["EXCALIBRIDGE_HOME"] = tempfile.mkdtemp()
from excalibridge import core  # noqa: E402


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.rel = "docs/diagrams/a.excalidraw"
        core.write_scene(self.root / self.rel, core.empty_scene())
        core.mark_seen(self.root, self.rel)

    def test_rel_path_rejects_escape_and_suffix(self):
        with self.assertRaises(ValueError):
            core.rel_path(self.root, "../x.excalidraw")
        with self.assertRaises(ValueError):
            core.rel_path(self.root, "docs/a.json")
        self.assertEqual(core.rel_path(self.root, "/docs/diagrams/a.excalidraw"), self.rel)

    def test_changes_then_seen(self):
        self.assertEqual(core.changes_since_seen(self.root, self.rel)["count"], 0)
        scene = core.read_scene(self.root / self.rel)
        scene["elements"].append(core.text_element("Q: why?", 10, 10, color="#1e1e1e", element_id="q1"))
        core.write_scene(self.root / self.rel, scene)
        d = core.changes_since_seen(self.root, self.rel)
        self.assertEqual([e["id"] for e in d["added"]], ["q1"])
        core.mark_seen(self.root, self.rel)
        self.assertEqual(core.changes_since_seen(self.root, self.rel)["count"], 0)

    def test_modified_and_removed(self):
        scene = core.read_scene(self.root / self.rel)
        scene["elements"].append(core.text_element("x", 0, 0, element_id="e1"))
        scene["elements"].append(core.text_element("y", 0, 0, element_id="e2"))
        core.write_scene(self.root / self.rel, scene)
        core.mark_seen(self.root, self.rel)
        scene["elements"][0]["version"] += 1
        scene["elements"][0]["text"] = "x changed"
        scene["elements"][1]["isDeleted"] = True
        core.write_scene(self.root / self.rel, scene)
        d = core.changes_since_seen(self.root, self.rel)
        self.assertEqual([e["id"] for e in d["modified"]], ["e1"])
        self.assertEqual([e["id"] for e in d["removed"]], ["e2"])

    def test_remeasured_text_is_not_a_change(self):
        scene = core.read_scene(self.root / self.rel)
        scene["elements"].append(core.text_element("hello", 0, 0, element_id="t"))
        core.write_scene(self.root / self.rel, scene)
        core.mark_seen(self.root, self.rel)
        el = scene["elements"][0]
        el["version"] += 3; el["width"] += 17.5; el["height"] += 2; el["updated"] += 1000
        core.write_scene(self.root / self.rel, scene)
        self.assertEqual(core.changes_since_seen(self.root, self.rel)["count"], 0)
        el["x"] += 5
        core.write_scene(self.root / self.rel, scene)
        self.assertEqual(core.changes_since_seen(self.root, self.rel)["count"], 1)

    def test_reply_near_anchor(self):
        scene = core.read_scene(self.root / self.rel)
        scene["elements"].append(core.text_element("Q: ?", 100, 200, color="#1e1e1e", element_id="q"))
        core.write_scene(self.root / self.rel, scene)
        out = core.add_reply(self.root, self.rel, "because", near="q")
        self.assertEqual(out["color"], core.AGENT_COLOR)
        self.assertTrue(out["text"].startswith("A: "))
        self.assertEqual(out["mode"], "callout")
        self.assertEqual(out["x"], 112)  # 12px inside the callout box that starts at the anchor's x
        self.assertGreater(out["y"], 200)
        with self.assertRaises(ValueError):
            core.add_reply(self.root, self.rel, "x", near="missing")

    def test_event_message_mentions_commands(self):
        ev = core.make_event(self.root, self.rel, "hi", 2)
        self.assertIn(f"excalibridge changes {self.rel}", ev["message"])
        self.assertIn("hi", ev["message"])

    def test_config_roundtrip(self):
        cfg = core.ProjectConfig.load(self.root)
        cfg.port = 9999
        cfg.notify.append({"type": "command", "run": "true"})
        cfg.save()
        again = core.ProjectConfig.load(self.root)
        self.assertEqual(again.port, 9999)
        self.assertEqual(again.notify[0]["type"], "command")
        self.assertEqual(oct(cfg.path.stat().st_mode)[-3:], "600")


class QuestionCardTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()); self.rel = "q.excalidraw"
        core.write_scene(self.root / self.rel, core.empty_scene())

    def test_numbering_continues_after_handwritten_headings(self):
        scene = core.read_scene(self.root / self.rel)
        scene["elements"].append(core.text_element("Q7 · old topic", 0, 0, color="#1e1e1e"))
        core.write_scene(self.root / self.rel, scene)
        q = core.add_question(self.root, self.rel, "next?")
        self.assertEqual(q["number"], 8)
        self.assertEqual(core.add_question(self.root, self.rel, "forced", number=20)["number"], 20)
        self.assertEqual(core.add_question(self.root, self.rel, "after forced")["number"], 21)

    def test_ask_numbers_and_answer_detection(self):
        labels = {"answer": "답변: ", "reply": "답: ", "question": "Q"}
        q1 = core.add_question(self.root, self.rel, "first?", title="one", labels=labels)
        q2 = core.add_question(self.root, self.rel, "second?", labels=labels)
        self.assertEqual((q1["number"], q2["number"]), (1, 2))
        self.assertGreater(q2["y"], q1["y"] + q1["height"])
        core.mark_seen(self.root, self.rel)
        scene = core.read_scene(self.root / self.rel)
        ans = next(e for e in scene["elements"] if e["id"] == q1["answerId"])
        ans["text"] = ans["originalText"] = "답변: yes, do it"; ans["version"] += 1
        core.write_scene(self.root / self.rel, scene)
        d = core.changes_since_seen(self.root, self.rel, labels)
        self.assertEqual(len(d["modified"]), 1)
        m = d["modified"][0]
        self.assertEqual(m["role"], "answer"); self.assertEqual(m["answer"], "yes, do it")
        self.assertEqual(m["question"], "one"); self.assertEqual(m["questionId"], q1["id"])


class AdapterTests(unittest.TestCase):
    def test_dispatch_isolates_failures(self):
        from excalibridge.adapters import dispatch
        ev = core.make_event(Path(tempfile.mkdtemp()), "x.excalidraw")
        res = dispatch(ev, [{"type": "command", "run": "exit 3"}, {"type": "nope"}])
        self.assertTrue(res[0]["ok"])            # inbox
        self.assertFalse(res[1]["ok"]); self.assertEqual(res[1]["code"], 3)
        self.assertFalse(res[2]["ok"]); self.assertIn("error", res[2])
        line = json.loads(core.inbox_path().read_text().splitlines()[-1])
        self.assertEqual(line["file"], "x.excalidraw")


if __name__ == "__main__":
    unittest.main()


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()); self.rel = "l.excalidraw"
        core.write_scene(self.root / self.rel, core.empty_scene())

    def test_wrap_respects_width(self):
        from excalibridge import layout
        out = layout.wrap("가나다라마바사아자차카타파하 " * 4, 200, 12)
        self.assertTrue(all(sum(12 * (1.0 if ord(c) > 0x2E7F else 0.58) for c in l) <= 200 + 12 for l in out.split("\n")))
        self.assertGreater(out.count("\n"), 1)

    def test_sections_flow_right_then_wrap(self):
        a = core.add_section(self.root, self.rel, "A", width=900)
        b = core.add_section(self.root, self.rel, "B", width=900)
        c = core.add_section(self.root, self.rel, "C", width=900)
        self.assertEqual(b["y"], a["y"]); self.assertGreater(b["x"], a["x"] + 800)
        self.assertEqual(c["x"], 40.0); self.assertGreater(c["y"], a["y"] + a["height"])
        self.assertEqual((a["index"], b["index"], c["index"]), (1, 2, 3))

    def test_ask_goes_into_latest_section_and_grows_it(self):
        core.add_section(self.root, self.rel, "S", width=600, height=120)
        q1 = core.add_question(self.root, self.rel, "one?")
        q2 = core.add_question(self.root, self.rel, "two?")
        scene = core.read_scene(self.root / self.rel)
        fr = next(e for e in scene["elements"] if e["type"] == "frame")
        self.assertEqual(q1["section"], 1)
        self.assertGreater(q2["y"], q1["y"] + q1["height"])
        self.assertGreaterEqual(fr["y"] + fr["height"], q2["y"] + q2["height"])
        card = next(e for e in scene["elements"] if e["id"] == q2["id"])
        self.assertEqual(card["frameId"], fr["id"])

    def test_card_reply_grows_card_and_pushes_below(self):
        q = core.add_question(self.root, self.rel, "why?")
        scene = core.read_scene(self.root / self.rel)
        below = core.text_element("below", q["x"], q["y"] + q["height"] + 10, element_id="below")
        scene["elements"].append(below); core.write_scene(self.root / self.rel, scene)
        out = core.add_reply(self.root, self.rel, "because " * 30, near=q["answerId"])
        self.assertEqual(out["mode"], "card")
        scene = core.read_scene(self.root / self.rel)
        card = next(e for e in scene["elements"] if e["id"] == q["id"])
        moved = next(e for e in scene["elements"] if e["id"] == "below")
        self.assertGreater(card["height"], q["height"])
        self.assertGreater(moved["y"], q["y"] + q["height"] + 10)
        self.assertGreaterEqual(moved["y"], card["y"] + card["height"])
        self.assertIn("\n", out["text"])  # wrapped

    def test_free_reply_is_callout_under_anchor(self):
        scene = core.read_scene(self.root / self.rel)
        note = core.text_element("a note", 100, 100, element_id="note"); note["width"] = 200
        scene["elements"].append(note); core.write_scene(self.root / self.rel, scene)
        out = core.add_reply(self.root, self.rel, "ok", near="note")
        self.assertEqual(out["mode"], "callout")
        scene = core.read_scene(self.root / self.rel)
        box = next(e for e in scene["elements"] if e["type"] == "rectangle")
        self.assertEqual(box["x"], 100); self.assertGreater(box["y"], 100)


class TidyTests(unittest.TestCase):
    def test_tidy_spaces_overlapping_sections_and_styles_them(self):
        from excalibridge import layout
        root = Path(tempfile.mkdtemp()); rel = "t.excalidraw"
        core.write_scene(root / rel, core.empty_scene())
        scene = core.read_scene(root / rel)
        a = core.text_element("a", 0, 0, element_id="a"); a["height"] = 100
        b = core.text_element("b", 0, 90, element_id="b"); b["height"] = 100
        scene["elements"] += [a, b]
        core.write_scene(root / rel, scene)
        core.add_section(root, rel, "A", wrap_y=(0, 50))
        core.add_section(root, rel, "B", wrap_y=(50, 150))
        rep = core.tidy(root, rel)
        scene = core.read_scene(root / rel)
        secs = sorted(layout.sections(scene), key=lambda f: f["y"])
        self.assertEqual(rep["sections"], 2)
        self.assertGreaterEqual(secs[1]["y"], secs[0]["y"] + secs[0]["height"] + layout.GAP - 0.5)
        bgs = [e for e in scene["elements"] if e.get("customData", {}).get("excalibridge") == "section-bg"]
        self.assertEqual(len(bgs), 2)
        bg1 = next(e for e in bgs if e["customData"]["section"] == secs[1]["id"])
        self.assertEqual(bg1["y"], secs[1]["y"])
        # members start below the coloured title
        for f in secs:
            mem = [e for e in scene["elements"] if e.get("frameId") == f["id"]
                   and e.get("customData", {}).get("excalibridge") not in ("section-bg", "section-title")]
            self.assertGreaterEqual(min(e["y"] for e in mem), f["y"] + layout.TITLE_H + 8 - 0.5)
        # the backdrop sits before the section's members in z-order
        idx = {e["id"]: i for i, e in enumerate(scene["elements"])}
        self.assertLess(idx[bg1["id"]], idx["b"])
