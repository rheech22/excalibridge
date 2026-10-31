---
name: excalibridge
description: Talk with the user on a shared Excalidraw canvas. Use when the user wants to sketch, diagram, or think visually with you, when a send event arrives from an excalibridge canvas, or when a .excalidraw file under the project is the subject of discussion.
---

# excalibridge

A shared Excalidraw canvas between the user and you. The user draws and writes in the browser;
a send button wakes you; you read only what changed, answer on the canvas, and mark it seen.
Files live in the repository as `*.excalidraw`, so decisions stay versioned.

## Setup (once per machine)

```bash
uv tool install excalibridge   # or: pipx install excalibridge / pip install excalibridge
```

Per project, nothing is required. `excalibridge open <file>` starts a local server for the
project root (the git top-level) and opens the viewer. Wake-up adapters are optional; see below.

## Loop

1. **Open a canvas**: `excalibridge open docs/diagrams/<topic>.excalidraw` (creates it if missing).
   Share the printed URL with the user if their browser did not open.
2. **When woken** (a send event, or the user says "look at the canvas"):
   `excalibridge changes <file>` lists `added`, `modified`, `removed` elements since you last
   marked the file seen. Read only those; the user may have edited anywhere on the canvas.
3. **Answer on the canvas**: `excalibridge reply <file> --near <element id> "short answer"`
   puts a blue `A:` line under the element. To ask the user something, use
   `excalibridge ask <file> "question" --title "topic"`: it adds a numbered question card with an
   answer line the user completes by double-clicking. In `changes`, a completed answer line comes
   back with `role: "answer"`, the answer text, and the card it belongs to. Apply requests and decisions by editing the file or,
   when you have a browser tab on the viewer, by scripting `window.excalidrawAPI` there
   (`window.convertToExcalidrawElements` is exposed for labelled shapes) and calling
   `window.saveScene()`.
4. **Mark seen**: `excalibridge seen <file>`. The user's tab reloads within a few seconds.
5. **Report briefly** in chat: what you read, what you did. One sentence if nothing changed.

Keep replies short. Long reasoning belongs in chat; the canvas points at *where* a remark applies.

## Notation (see references/protocol.md)

| Meaning | How the user marks it | What you do |
|---|---|---|
| Question, request, note | plain black text, no prefix | judge from content; answer or apply |
| Decision | prefix `Decision:` or green text | move it into the project's docs, leave a one-line summary on the canvas |
| Discarded | grey text or strikethrough | ignore |
| Your reply | blue (#1971c2), prefix `A:` | `excalibridge reply` does this |

| Question card | orange card made by `excalibridge ask` | the user completes the `Answer:` line; read it from `changes` |

Prefixes win over colours. Do not restyle the user's elements. Labels (`Answer:`, `A:`, `Q`) can be
localised per project: `excalibridge config --label answer '답변: ' --label reply '답: '`.

## Drawing programmatically

The file is plain Excalidraw JSON. For free text use `excalibridge reply --at x,y`. For boxes
with labels and arrows, generate skeletons in a viewer tab with `window.convertToExcalidrawElements`
so text metrics are right, then `window.saveScene()`. Give arrows explicit `points`; bindings
without coordinates collapse to the origin.

## Wake-up adapters

The send button always appends to `~/.excalibridge/inbox.ndjson`. Add adapters to wake a host:

- **T3 Code**: create a scheduled task with schedule `{type: "webhook"}` bound to your thread and
  prompt `{{body.message}}`; then `excalibridge notify add t3 --url <webhookUrl>`. Needs T3 Connect.
- **herdr**: `excalibridge notify add herdr --target <agent name or id>`; the message is submitted
  with `herdr agent prompt`.
- **Any host**: `excalibridge notify add command --run '<script>'`; the event arrives in
  `EXB_MESSAGE`, `EXB_FILE`, `EXB_ROOT`, `EXB_NOTE`, `EXB_CHANGES`.
- **Nothing configured**: watch the inbox (`tail -F ~/.excalibridge/inbox.ndjson`) or ask the user
  to say "look at the canvas".

Restart the server after changing adapters: `excalibridge stop && excalibridge serve`.
Test with `excalibridge notify test`.

## Limits

The viewer loads Excalidraw from a CDN, so the first load needs network. Two tabs editing the same
file at once last-write-wins; the viewer refuses to reload over unsaved local edits.
