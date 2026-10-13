import json
import unittest
from unittest.mock import patch

import httpx
from fastmcp import Client

import jadx_mcp_server
from src.server import config
from src.server.tools import project_tools


class ProjectToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_open_then_poll_uses_distinct_states(self):
        requests = []
        def handle(request):
            requests.append(request)
            return httpx.Response(200, json={'operation_id': 'load-1',
                'state': 'loading' if request.method == 'POST' else 'ready'})
        real_client = httpx.AsyncClient
        with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(handle), **kw)):
            async with Client(jadx_mcp_server.mcp) as client:
                result = await client.call_tool('open_apk', {'path': '/fixtures/app.apk'})
                self.assertEqual(result.data['state'], 'loading')
                result = await client.call_tool('get_project_operation', {'operation_id': 'load-1'})
                self.assertEqual(result.data['state'], 'ready')
        self.assertEqual(json.loads(requests[0].content), {'path': '/fixtures/app.apk', 'replace': False})
        self.assertEqual(requests[1].url.params['operation_id'], 'load-1')

    async def test_bad_paths_are_rejected(self):
        for path in ('relative.apk', '', '/a\x00b'):
            self.assertEqual((await project_tools.open_apk(path))['code'], 'invalid_request')
