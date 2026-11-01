import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from excalibridge import core
from excalibridge.server import make_handler


class EmbedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.page = self.root / 'mock up.html'
        self.page.write_text('<button>hello</button>')

    def test_append_preserves_scene_and_uses_port_independent_url(self):
        path = self.root / 'demo.excalidraw'
        scene = core.empty_scene()
        scene['elements'].append(core.text_element('keep me', 0, 0))
        core.write_scene(path, scene)
        result = core.add_embed(self.root, path.name, self.page.name)
        saved = core.read_scene(path)
        self.assertEqual(saved['elements'][0], scene['elements'][0])
        self.assertEqual(result['link'], '/mock%20up.html')
        self.assertEqual(saved['elements'][1]['type'], 'embeddable')
        self.assertGreater(saved['elements'][1]['y'], 0)

    def test_embed_link_changes_are_reported_to_agent(self):
        core.add_embed(self.root, 'demo.excalidraw', self.page.name)
        core.mark_seen(self.root, 'demo.excalidraw')
        path = self.root / 'demo.excalidraw'
        scene = core.read_scene(path)
        scene['elements'][0]['link'] = 'http://localhost:5173/'
        core.write_scene(path, scene)
        changes = core.changes_since_seen(self.root, 'demo.excalidraw')
        self.assertEqual(changes['count'], 1)
        self.assertEqual(changes['modified'][0]['link'], 'http://localhost:5173/')

    def test_invalid_paths_and_geometry_do_not_write(self):
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / 'outside.html'
            external.write_text('secret')
            (self.root / 'linked.html').symlink_to(external)
            for html in [str(external), 'linked.html', 'missing.html', '../escape.html']:
                with self.subTest(html=html), self.assertRaises(ValueError):
                    core.add_embed(self.root, 'demo.excalidraw', html)
            with self.assertRaises(ValueError):
                core.add_embed(self.root, '../escape.excalidraw', self.page.name)
            for width in [0, -1, float('nan'), float('inf')]:
                with self.subTest(width=width), self.assertRaises(ValueError):
                    core.add_embed(self.root, 'demo.excalidraw', self.page.name, width=width)
        self.assertFalse((self.root / 'demo.excalidraw').exists())

    def test_server_serves_embed_module_and_html_but_not_external_symlinks(self):
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / 'secret.html'
            external.write_text('secret')
            (self.root / 'linked.html').symlink_to(external)
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(core.ProjectConfig(self.root)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f'http://127.0.0.1:{server.server_port}'
                with urlopen(base + '/mock%20up.html') as response:
                    self.assertEqual(response.read(), self.page.read_bytes())
                with urlopen(base + '/_excalibridge/embeddable.mjs') as response:
                    self.assertIn('javascript', response.headers['Content-Type'])
                    self.assertIn(b'localEmbedURL', response.read())
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + '/linked.html')
                self.assertEqual(error.exception.code, 403)
                error.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
