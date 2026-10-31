"""excalibridge command line."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from excalibridge import __version__, core


def _cfg(args) -> core.ProjectConfig:
    root = Path(args.root).resolve() if getattr(args, "root", None) else core.find_root()
    return core.ProjectConfig.load(root)


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


# ----------------------------------------------------------------- server lifecycle


def _server_alive(cfg: core.ProjectConfig) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{cfg.port}/_excalibridge/health", timeout=1.5) as r:
            info = json.loads(r.read())
            return info if info.get("root") == str(cfg.root) else {"ok": False, "other": info}
    except Exception:
        return None


def _start_daemon(cfg: core.ProjectConfig) -> None:
    rp = core.run_path(cfg.root)
    rp.parent.mkdir(parents=True, exist_ok=True)
    log = rp.with_suffix(".log")
    with log.open("ab") as lf:
        p = subprocess.Popen([sys.executable, "-m", "excalibridge.cli", "--root", str(cfg.root), "serve",
                              "--port", str(cfg.port), "--foreground"],
                             stdout=lf, stderr=lf, stdin=subprocess.DEVNULL, start_new_session=True)
    rp.write_text(json.dumps({"pid": p.pid, "port": cfg.port, "root": str(cfg.root)}))
    for _ in range(40):
        time.sleep(0.1)
        if _server_alive(cfg):
            return
    raise SystemExit(f"server did not come up; see {log}")


def cmd_serve(args):
    cfg = _cfg(args)
    if args.port:
        cfg.port = args.port
    if args.foreground:
        from excalibridge.server import serve
        return serve(cfg)
    alive = _server_alive(cfg)
    if alive and alive.get("ok"):
        return print(f"already running on http://127.0.0.1:{cfg.port} for {cfg.root}")
    if alive and alive.get("other"):
        raise SystemExit(f"port {cfg.port} is serving another root: {alive['other'].get('root')}. "
                         f"Use `excalibridge config --port <n>`.")
    _start_daemon(cfg)
    print(f"serving {cfg.root} on http://127.0.0.1:{cfg.port}")


def cmd_stop(args):
    cfg = _cfg(args)
    rp = core.run_path(cfg.root)
    if not rp.exists():
        return print("not running")
    info = json.loads(rp.read_text())
    try:
        os.kill(info["pid"], signal.SIGTERM)
        print(f"stopped pid {info['pid']}")
    except ProcessLookupError:
        print("process already gone")
    rp.unlink()


def cmd_status(args):
    cfg = _cfg(args)
    _print({"root": str(cfg.root), "port": cfg.port, "server": _server_alive(cfg), "notify": cfg.notify,
            "config": str(cfg.path), "inbox": str(core.inbox_path()), "version": __version__})


# ----------------------------------------------------------------- files


def cmd_new(args):
    cfg = _cfg(args)
    rel = core.rel_path(cfg.root, args.file)
    path = cfg.root / rel
    if path.exists() and not args.force:
        raise SystemExit(f"{rel} exists (use --force to overwrite)")
    core.write_scene(path, core.empty_scene())
    core.mark_seen(cfg.root, rel)
    print(rel)


def cmd_open(args):
    cfg = _cfg(args)
    rel = core.rel_path(cfg.root, args.file)
    if not (cfg.root / rel).exists():
        core.write_scene(cfg.root / rel, core.empty_scene())
        core.mark_seen(cfg.root, rel)
    alive = _server_alive(cfg)
    if not (alive and alive.get("ok")):
        if alive and alive.get("other"):
            raise SystemExit(f"port {cfg.port} is serving another root; set a different port with `excalibridge config --port`.")
        _start_daemon(cfg)
    url = f"http://127.0.0.1:{cfg.port}/_excalibridge/viewer?file={rel}"
    print(url)
    if not args.no_browser:
        webbrowser.open(url)


def cmd_changes(args):
    cfg = _cfg(args)
    _print(core.changes_since_seen(cfg.root, core.rel_path(cfg.root, args.file)))


def cmd_seen(args):
    cfg = _cfg(args)
    rel = core.rel_path(cfg.root, args.file)
    core.mark_seen(cfg.root, rel)
    print(f"seen {rel}")


def cmd_reply(args):
    cfg = _cfg(args)
    rel = core.rel_path(cfg.root, args.file)
    at = tuple(float(v) for v in args.at.split(",")) if args.at else None
    out = core.add_reply(cfg.root, rel, args.text, near=args.near, at=at, prefix=args.prefix, color=args.color,
                         font_size=args.size)
    _print(out)


def cmd_send(args):
    """Simulate the viewer's send button (useful for testing adapters)."""
    cfg = _cfg(args)
    rel = core.rel_path(cfg.root, args.file)
    body = json.dumps({"note": args.note or "", "changes": core.changes_since_seen(cfg.root, rel)["count"]}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{cfg.port}/_excalibridge/send?file={rel}", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        _print(json.loads(r.read()))


# ----------------------------------------------------------------- config


def cmd_config(args):
    cfg = _cfg(args)
    if args.port:
        cfg.port = args.port
        cfg.save()
    _print({"root": str(cfg.root), "port": cfg.port, "notify": cfg.notify, "path": str(cfg.path)})


def cmd_notify(args):
    cfg = _cfg(args)
    if args.action == "list":
        return _print(cfg.notify)
    if args.action == "remove":
        before = len(cfg.notify)
        cfg.notify = [n for i, n in enumerate(cfg.notify) if str(i) != args.target and n.get("type") != args.target]
        cfg.save()
        return print(f"removed {before - len(cfg.notify)}")
    if args.action == "add":
        entry = {"type": args.kind}
        if args.kind == "t3":
            if not args.url:
                raise SystemExit("--url is required for t3")
            entry["url"] = args.url
        elif args.kind == "herdr":
            if not args.target:
                raise SystemExit("--target is required for herdr (agent name or id)")
            entry["target"] = args.target
            entry["wait"] = bool(args.wait)
        elif args.kind == "command":
            if not args.run:
                raise SystemExit("--run is required for command")
            entry["run"] = args.run
        else:
            raise SystemExit(f"unknown adapter {args.kind}")
        cfg.notify.append(entry)
        cfg.save()
        print(f"added {args.kind}; restart the server to apply: excalibridge stop && excalibridge serve")
    if args.action == "test":
        from excalibridge.adapters import dispatch
        ev = core.make_event(cfg.root, args.file or "test.excalidraw", "adapter test", 0)
        _print(dispatch(ev, cfg.notify))


# ----------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="excalibridge", description="A shared Excalidraw canvas between you and your coding agent.")
    p.add_argument("--version", action="version", version=f"excalibridge {__version__}")
    p.add_argument("--root", help="project root (default: git top-level of the current directory)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("open", help="start the server if needed and open a canvas in the browser")
    s.add_argument("file"); s.add_argument("--no-browser", action="store_true"); s.set_defaults(fn=cmd_open)

    s = sub.add_parser("new", help="create an empty .excalidraw file")
    s.add_argument("file"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_new)

    s = sub.add_parser("changes", help="what changed since the agent last looked (JSON)")
    s.add_argument("file"); s.set_defaults(fn=cmd_changes)

    s = sub.add_parser("seen", help="mark the current file as seen by the agent")
    s.add_argument("file"); s.set_defaults(fn=cmd_seen)

    s = sub.add_parser("reply", help="add an agent reply (blue text) to the canvas")
    s.add_argument("file"); s.add_argument("text")
    s.add_argument("--near", help="element id to place the reply under")
    s.add_argument("--at", help="x,y coordinates instead of --near")
    s.add_argument("--prefix", default="A: "); s.add_argument("--color", default=core.AGENT_COLOR)
    s.add_argument("--size", type=int, default=12); s.set_defaults(fn=cmd_reply)

    s = sub.add_parser("send", help="simulate the send button (for testing adapters)")
    s.add_argument("file"); s.add_argument("--note"); s.set_defaults(fn=cmd_send)

    s = sub.add_parser("serve", help="run the local server (daemon by default)")
    s.add_argument("--port", type=int); s.add_argument("--foreground", action="store_true"); s.set_defaults(fn=cmd_serve)
    s = sub.add_parser("stop", help="stop the server for this project"); s.set_defaults(fn=cmd_stop)
    s = sub.add_parser("status", help="show server, config, and inbox locations"); s.set_defaults(fn=cmd_status)

    s = sub.add_parser("config", help="show or change project config")
    s.add_argument("--port", type=int); s.set_defaults(fn=cmd_config)

    s = sub.add_parser("notify", help="manage wake-up adapters")
    s.add_argument("action", choices=["list", "add", "remove", "test"])
    s.add_argument("kind", nargs="?", help="t3 | herdr | command (for add)")
    s.add_argument("--url"); s.add_argument("--target"); s.add_argument("--wait", action="store_true")
    s.add_argument("--run"); s.add_argument("--file")
    s.set_defaults(fn=cmd_notify)
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    if args.cmd == "notify" and args.action == "remove" and args.kind:
        args.target = args.target or args.kind
    args.fn(args)


if __name__ == "__main__":
    main()
