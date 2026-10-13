import unittest
from unittest.mock import patch

import httpx
from fastmcp import Client

import jadx_mcp_server
from src.server import config


class CacheControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_stats_preserve_bounds_and_clear_uses_post(self):
        calls = []
        stats = {'generation': 12, 'policy': {'max_entries': 256}, 'entries': 3}
        def handle(request):
            calls.append((request.method, request.url.path))
            return httpx.Response(200, json=stats if request.method == 'GET' else {'cleared': True, 'generation': 13})
        real_client = httpx.AsyncClient
        with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(handle), **kw)):
            async with Client(jadx_mcp_server.mcp) as client:
                self.assertEqual((await client.call_tool('get_cache_stats')).data, stats)
                self.assertEqual((await client.call_tool('clear_cache')).data['generation'], 13)
        self.assertEqual(calls, [('GET', '/cache-stats'), ('POST', '/cache-clear')])
