"""Local HTTP server: serves the project root and the viewer, and exposes the bridge endpoints.

GET  /_excalibridge/viewer?file=<rel>   the Excalidraw viewer for one file
GET  /_excalibridge/mtime?file=<rel>    file mtime, used by the viewer to reload external changes
GET  /_excalibridge/changes?file=<rel>  diff against the agent's last-seen copy
POST /_excalibridge/save?file=<rel>     body: scene JSON
POST /_excalibridge/send?file=<rel>     body: {scene, note, changes}; saves, then notifies adapters
POST /_excalibridge/seen?file=<rel>     copy the file into the seen store
"""

from __future__ import annotations

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from excalibridge import __version__, core
from excalibridge.adapters import dispatch

VIEWER = Path(__file__).parent / "viewer" / "index.html"
PREFIX = "/_excalibridge/"


def make_handler(cfg: core.ProjectConfig):
    root = cfg.root

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(root), **k)

        def send_head(self):
            # SimpleHTTPRequestHandler follows symlinks; project content must stay in root.
            target = Path(self.translate_path(self.path)).resolve()
            if not target.is_relative_to(root.resolve()):
                self.send_error(403, "outside the project root")
                return None
            return super().send_head()

        # -- helpers
        def _json(self, obj, code=200):
            data = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _rel(self, u):
            try:
                return core.rel_path(root, parse_qs(u.query).get("file", [""])[0])
            except ValueError as e:
                self._json({"ok": False, "error": str(e)}, 403)
                return None

        def _body(self):
            return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, *a):  # quiet
            pass

        # -- routes
        def do_GET(self):
            u = urlparse(self.path)
            if not u.path.startswith(PREFIX):
                return super().do_GET()
            op = u.path[len(PREFIX):]
            if op == "embeddable.mjs":
                data = (VIEWER.parent / "embeddable.mjs").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                return self.wfile.write(data)
            if op == "viewer":
                html = VIEWER.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                return self.wfile.write(html)
            if op == "health":
                return self._json({"ok": True, "version": __version__, "root": str(root)})
            rel = self._rel(u)
            if rel is None:
                return
            if not (root / rel).exists():
                return self._json({"ok": False, "error": "not found"}, 404)
            if op == "mtime":
                return self._json({"mtime": os.stat(root / rel).st_mtime})
            if op == "changes":
                return self._json(core.changes_since_seen(root, rel, cfg.labels))
            return self._json({"ok": False, "error": "unknown op"}, 404)

        def do_POST(self):
            u = urlparse(self.path)
            if not u.path.startswith(PREFIX):
                return self._json({"ok": False, "error": "not found"}, 404)
            op = u.path[len(PREFIX):]
            rel = self._rel(u)
            if rel is None:
                return
            if op == "seen":
                core.mark_seen(root, rel)
                return self._json({"ok": True, "seen": rel})
            body = self._body()
            if op == "save":
                core.write_scene(root / rel, body)
                return self._json({"ok": True, "file": rel, "elements": len(body.get("elements", []))})
            if op == "send":
                if body.get("scene"):
                    core.write_scene(root / rel, body["scene"])
                event = core.make_event(root, rel, body.get("note", ""), int(body.get("changes", 0)))
                results = dispatch(event, cfg.notify)
                return self._json({"ok": True, "file": rel, "results": results})
            return self._json({"ok": False, "error": "unknown op"}, 404)

    return Handler


def serve(cfg: core.ProjectConfig, host: str = "127.0.0.1") -> None:
    httpd = ThreadingHTTPServer((host, cfg.port), make_handler(cfg))
    print(f"excalibridge {__version__} serving {cfg.root} on http://{host}:{cfg.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
