# Canvas notation

Rules for a canvas shared between a person and an agent. The point is to let content carry meaning
and reserve markers for what content cannot say.

## Who wrote it

- The person writes in the default colour (black). No prefix needed.
- The agent writes in blue `#1971c2` with the prefix `A:`, placed directly under the element it answers.

## What it means

| Marker | Meaning | Agent behaviour |
|---|---|---|
| none | question, request, or note | decide from the text; answer or apply |
| `Decision:` prefix, or green text | settled | copy into the project's documentation; leave a one-line summary on the canvas |
| grey text, or strikethrough | abandoned | skip |
| `Q1`, `Q2` … | numbered questions | answer with the same number |

Prefixes are authoritative; colours are a hint. Agents must not change the style of the person's elements.

## Question cards

The agent asks with `excalibridge ask`. A card has a numbered title, the question, a dashed rule,
and one answer line (`Answer: `) in the person's own colour. The person double-clicks that line and
types after the label; nothing needs restyling. The agent reads the completed line from `changes`
(`role: "answer"`) and moves settled answers into the documentation.

## Rhythm

- The person presses **Send** when a batch is ready. The viewer saves first, then notifies.
- Send is skipped when nothing changed since the agent last looked; Shift+click forces it.
- The agent reads only the diff, replies, and marks the file seen. The person's tab reloads on its own.
