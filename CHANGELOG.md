# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [SemVer](https://semver.org).

## [0.1.0] - 2026-10-31

### Added
- Local server that serves a project root, saves `.excalidraw` files, and exposes
  `changes`, `seen`, `mtime`, and `send` endpoints.
- Excalidraw viewer with a send button in the top-right toolbar, autosave, reload on
  external change, send cooldown, and skip-when-nothing-changed.
- CLI: `open`, `new`, `changes`, `seen`, `reply`, `send`, `serve`, `stop`, `status`, `config`, `notify`.
- Wake-up adapters: inbox (always on), T3 Code webhook, herdr agent prompt, custom command.
- Agent skill (`SKILL.md`) and canvas notation (`references/protocol.md`).
- herdr plugin manifest with an "open canvas here" action.
