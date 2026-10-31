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
uv tool install excalibridge        # or pipx / pip
```

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
```

Versioned with [SemVer](https://semver.org); see [CHANGELOG.md](CHANGELOG.md). Tags `v*` build a GitHub release.

MIT
