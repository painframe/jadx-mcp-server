import os
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from src.server import config


class BackendAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_post_progress_and_health_all_authenticate(self):
        observed = []
        credential = secrets.token_urlsafe(32)
        def handler(request):
            observed.append(request.headers.get('authorization'))
            return httpx.Response(200, json={'state': 'idle'})
        real_async, real_sync = httpx.AsyncClient, httpx.Client
        transport = httpx.MockTransport(handler)
        with patch.dict(os.environ, {'JADX_API_TOKEN': credential}, clear=True), patch.object(
                config, 'JADX_TOKEN_FILE', None), patch.object(config.httpx, 'AsyncClient',
                side_effect=lambda **kw: real_async(transport=transport, **kw)), patch.object(config.httpx, 'Client',
                side_effect=lambda **kw: real_sync(transport=transport, **kw)):
            await config.get_from_jadx('class-info')
            await config.post_to_jadx('cache-clear')
            await config.get_search_progress()
            config.health_ping()
        self.assertEqual(observed, [f'Bearer {credential}'] * 4)

    async def test_token_file_rotation_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / 'token'
            with patch.object(config, 'JADX_TOKEN_FILE', str(path)):
                self.assertEqual(config.backend_headers()[1]['code'], 'configuration_error')
                path.write_text('first')
                self.assertEqual(config.backend_headers()[0]['Authorization'], 'Bearer first')
                path.write_text('rotated')
                self.assertEqual(config.backend_headers()[0]['Authorization'], 'Bearer rotated')
                path.write_text('header\ninjection')
                self.assertEqual(config.backend_headers()[1]['code'], 'configuration_error')

    async def test_full_url_rejects_credentials_and_preserves_prefix(self):
        with patch.object(config, 'JADX_HTTP_BASE', config.JADX_HTTP_BASE):
            self.assertIsNotNone(config.set_jadx_url('http://user:secret@example.test'))
            self.assertIsNotNone(config.set_jadx_url('file:///etc/passwd'))
            self.assertIsNone(config.set_jadx_url('https://example.test/jadx/'))
            self.assertEqual(config.JADX_HTTP_BASE, 'https://example.test/jadx')
