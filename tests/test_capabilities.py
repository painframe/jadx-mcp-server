import unittest
from unittest.mock import patch

import httpx
from fastmcp import Client

import jadx_mcp_server
from src.server import config, instances


class CapabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_headless_capabilities_and_unsupported_gui_action(self):
        payload = {'service': 'jadx-ai-mcp', 'mode': 'headless', 'capabilities': ['class-info']}
        selected = {'id': 'headless', 'url': 'http://localhost:8650', 'capabilities': ['class-info']}
        real_client = httpx.AsyncClient
        with patch.object(instances, 'current', return_value=selected), patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)), **kw)):
            async with Client(jadx_mcp_server.mcp) as client:
                result = await client.call_tool('get_backend_capabilities')
                self.assertEqual(result.data['mode'], 'headless')
                result = await client.call_tool('get_selected_text')
                self.assertEqual(result.data['code'], 'unsupported_capability')

    async def test_missing_route_and_missing_entity_are_distinguished(self):
        real_client = httpx.AsyncClient
        async def run(capabilities):
            def handler(request):
                if request.url.path == '/health':
                    return httpx.Response(200, json={'capabilities': capabilities})
                return httpx.Response(404, text='not found')
            with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                    transport=httpx.MockTransport(handler), **kw)):
                return await config.get_from_jadx('class-info')
        self.assertEqual((await run([]))['code'], 'unsupported_capability')
        self.assertEqual((await run(['class-info']))['code'], 'http_error')
