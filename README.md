# excalibridge

A shared [Excalidraw](https://excalidraw.com) canvas between you and your coding agent.
You sketch and write in the browser, press **Send**, and the agent wakes up, reads only what
changed, answers in blue on the canvas, and marks it seen. Canvases are `.excalidraw` files in
your repository, so decisions stay versioned.

Works with any agent that can run a shell command (Claude Code, Codex, …). Wake-up adapters
exist for [T3 Code](https://t3.chat) webhooks, [herdr](https://herdr.dev) agent panes, and any
custom command; without one, the send event lands in `~/.excalibridge/inbox.ndjson`.

## Install

```bash
uv tool install 'excalibridge @ git+https://github.com/rheech22/excalibridge@v0.7.0'
```

Release wheels and source packages are also available on [GitHub Releases](https://github.com/rheech22/excalibridge/releases).
The package is not currently published on PyPI.

Give your agent the skill: symlink this repository (or the installed `SKILL.md`) into the
skills directory your agent reads, e.g. `~/.claude/skills/excalibridge` or `~/.codex/skills/excalibridge`.

## Use

```bash
excalibridge open docs/diagrams/idea.excalidraw   # starts a local server, opens the viewer
excalibridge changes docs/diagrams/idea.excalidraw   # agent: what changed since I last looked
excalibridge reply docs/diagrams/idea.excalidraw --near <id> "because …"
excalibridge seen docs/diagrams/idea.excalidraw
```

`xb` is a short alias. `excalibridge --help` lists everything.

## Interactive HTML on the canvas

Project HTML pages can be real, clickable iframe embeds inside the canvas:

```bash
excalibridge embed docs/diagrams/idea.excalidraw prototypes/colors.html --width 640 --height 440
excalibridge open docs/diagrams/idea.excalidraw
```

Double-click the embed to interact; click outside to return to drawing. The CLI appends an element
without replacing other content, creates a missing canvas, and defaults to placing it below existing
content (`--at x,y` overrides placement). Save viewer edits before editing the file from the CLI.
Links to project HTML are root-relative, so the canvas also works when the server port changes.
Keep the HTML and its assets inside the project root; paths and symlinks escaping it are refused.

The viewer additionally accepts explicit `http(s)://localhost`, `127.0.0.1`, and `[::1]` URLs for
local development servers through Excalidraw's Web Embed tool. Other providers keep Excalidraw's
existing validation. Local embeds use a sandbox with `allow-scripts` only: inline scripts and
buttons work, but parent DOM access, forms, popups, storage, and same-origin APIs are unavailable.
Dev servers may need CORS for fetch/module scripts and must permit framing. Only embed local
pages you trust; this is not a full network sandbox.

This feature takes **URLs / HTML file paths**, not pasted HTML source or `srcdoc`. Saving a canvas
preserves the embed element and URL, not the page's transient JavaScript state. Remote viewers
need their own copy of the HTML/dev server; localhost always refers to the viewer's machine.

See [the runnable HTML embed example](examples/html-embed/README.md).

## Wake the agent

```bash
excalibridge notify add t3 --url <webhook url>        # T3 Code scheduled task (webhook)
excalibridge notify add herdr --target <agent>        # herdr agent pane
excalibridge notify add command --run './wake.sh'     # anything else
excalibridge notify test
```

Details and the canvas notation are in [SKILL.md](SKILL.md) and [references/protocol.md](references/protocol.md).

## Development

```bash
python -m unittest discover -s tests
node --test tests/test_embeddable.mjs    # optional Node.js check for viewer URL policy
```

Versioned with [SemVer](https://semver.org); see [CHANGELOG.md](CHANGELOG.md). Tags `v*` build a GitHub release.

MIT
