import assert from 'node:assert/strict';
import test from 'node:test';
import { localEmbedURL } from '../excalibridge/viewer/embeddable.mjs';
const origin = 'http://127.0.0.1:8791';

test('project HTML and explicit loopback dev servers', () => {
  for (const link of ['/examples/demo.html', '/mock%20up.htm?theme=dark#test', `${origin}/demo.html`, 'http://localhost:5173/', 'http://[::1]:3000/app']) {
    assert.ok(localEmbedURL(link, origin), link);
  }
});
test('other links defer to the existing Excalidraw provider policy', () => {
  for (const link of [null, '', '<html>raw</html>', 'javascript:alert(1)', 'data:text/html,test', 'file:///tmp/a.html', 'https://example.com/a.html', 'https://127.0.0.1.evil.test/a', 'http://user:pass@localhost/a', '/_excalibridge/viewer.html', '/%5fexcalibridge/viewer.html', '/demo.excalidraw', '/bad%ZZ.html', '/%2e%2e%2fsecret.html', 'http:\\localhost/a', '/a\nb.html']) {
    assert.equal(localEmbedURL(link, origin), null, String(link));
  }
});
