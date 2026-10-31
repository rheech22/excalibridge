#!/usr/bin/env bash
# Invoked by herdr with the focused pane's context in the environment (see herdr plugin docs).
# HERDR_PANE_CWD: folder of the focused pane; HERDR_AGENT_ID: focused agent, if any.
set -euo pipefail
cwd="${HERDR_PANE_CWD:-$PWD}"
file="${EXCALIBRIDGE_DEFAULT_FILE:-docs/diagrams/canvas.excalidraw}"
cd "$cwd"
if [ -n "${HERDR_AGENT_ID:-}" ]; then
  if ! excalibridge notify list | grep -q "\"target\": \"${HERDR_AGENT_ID}\""; then
    excalibridge notify add herdr --target "$HERDR_AGENT_ID" >/dev/null || true
    excalibridge stop >/dev/null 2>&1 || true
  fi
fi
excalibridge open "$file"
