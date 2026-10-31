# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [SemVer](https://semver.org).

## [0.2.2] - 2026-10-31

### Changed
- When there is nothing to send, the button stays hoverable and clickable: the tooltip and a click
  explain why (the agent has seen everything), and Shift+click still forces a send. The status line
  now reads "Agent is caught up" or "N change(s) to send" instead of the file path.

## [0.2.1] - 2026-10-31

### Fixed
- Change detection compared Excalidraw's `version` counter, so text the viewer re-measured after a
  CLI reply showed up as a user edit. It now compares content and placement (text, position,
  colours, points, and size for non-text shapes).

## [0.2.0] - 2026-10-31

### Added
- The send button is disabled while there is nothing new for the agent (no unsaved edits and no
  changes since the agent last marked the file seen). It re-enables as you draw and turns off again
  once the agent has caught up. Cmd/Ctrl+Shift+Enter still forces a send.

## [0.1.1] - 2026-10-31

### Fixed
- Viewer fetched the canvas relative to the viewer URL and showed an empty scene; it now fetches
  from the project root and reports load failures instead of staying silent.
- `excalibridge serve` passed `--root` after the subcommand when spawning the daemon.
- Request body parsing in the server (syntax error).

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
