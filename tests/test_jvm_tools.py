import unittest
from unittest.mock import patch

import httpx
from fastmcp import Client

import jadx_mcp_server
from src.server import config


class JvmToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_each_section_is_forwarded_through_mcp_http(self):
        requests = []
        def handle(request):
            requests.append(request)
            return httpx.Response(200, json={'section': request.url.params['section'], 'items': []})
        real_client = httpx.AsyncClient
        with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(handle), **kw)):
            async with Client(jadx_mcp_server.mcp) as client:
                for section in ('manifest', 'services', 'entry-points', 'dependencies', 'properties', 'packages'):
                    result = await client.call_tool('get_jvm_info', {'section': section, 'offset': 100, 'count': 25})
                    self.assertEqual(result.data['section'], section)
        self.assertEqual(len(requests), 6)
        self.assertTrue(all(request.url.path == '/jvm-info' for request in requests))
        self.assertTrue(all(request.url.params['offset'] == '100' for request in requests))
        self.assertTrue(all(request.url.params['count'] == '25' for request in requests))
