# HTML embed demo

`demo.excalidraw` embeds `demo.html` as a real sandboxed iframe. It is not an image.
Its two buttons change the theme and accent color. Colors are illustrative, not approved tokens.

Run from this checkout (no install/config changes required):

```sh
cd /path/to/excalibridge
python3 -m excalibridge.cli serve --port 8791 --foreground
```

Open <http://127.0.0.1:8791/_excalibridge/viewer?file=examples/html-embed/demo.excalidraw>.
Use any free port if 8791 is busy. Double-click the embed, then click **Toggle light / dark**
and **Change accent**. Click outside to draw. Cmd/Ctrl+S saves the scene; reload to verify that
the HTML embed returns. The HTML page's theme/counter resets when reloaded; it is not scene data.

Create another canvas using the same HTML:

```sh
python3 -m excalibridge.cli embed examples/html-embed/another.excalidraw examples/html-embed/demo.html --at 0,0
```

The installed CLI may be an older release. Use `python3 -m excalibridge.cli` from this checkout
until you choose to update it. A server already running from the installed package must be
restarted with this checkout to serve the new viewer; this demo does not restart other projects.

## Verification

- `python3 -m unittest discover -s tests` checks scene preservation, HTML paths, dimensions,
  module delivery, and symlink escape rejection.
- `node --test tests/test_embeddable.mjs` checks local URL handling and rejection/fallback cases.
- Browser acceptance: verify there is an iframe titled `Local HTML prototype` inside Excalidraw,
  with `sandbox="allow-scripts"`. Double-click the embed, click theme, and check the page switches
  from dark to light. Click accent and check the swatch changes. Save and reload: the same URL
  and iframe must return. The page's theme/click count resets. Parent DOM access from the iframe
  must throw a sandbox origin error.

Excalidraw 0.18.0's [renderEmbeddable/validateEmbeddable props](https://github.com/excalidraw/excalidraw/blob/v0.18.0/packages/excalidraw/types.ts)
and [iframe interaction wrapper](https://github.com/excalidraw/excalidraw/blob/v0.18.0/packages/excalidraw/components/App.tsx)
provide the canvas integration; Excalibridge supplies the local URL policy and sandboxed renderer.
