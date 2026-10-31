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
        self.assertEqual(out["x"], 100)
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
