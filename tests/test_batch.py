import json
import unittest
from unittest.mock import patch

import httpx
from fastmcp import Client

import jadx_mcp_server
from src.server import config
from src.server.tools import batch_tools


class BatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_sends_json_and_preserves_partial_outcomes(self):
        requests = []
        payload = {'operation': 'class-source', 'results': [
            {'index': 0, 'ok': True, 'data': {'content': 'class A {}'}},
            {'index': 1, 'ok': False, 'error': 'missing', 'code': 'not_found'}]}
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json=payload)
        real_client = httpx.AsyncClient
        with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(handler), **kw)):
            async with Client(jadx_mcp_server.mcp) as client:
                result = await client.call_tool('batch_analysis', {'operation': 'class-source',
                    'items': [{'class_name': 'A'}, {'class_name': 'missing'}]})
        self.assertEqual(result.data, payload)
        self.assertEqual(requests[0].method, 'POST')
        self.assertEqual(json.loads(requests[0].content)['items'][0], {'class_name': 'A'})

    async def test_invalid_batch_rejected_before_transport(self):
        for items in ([], [{'class_name': 'A'}] * 51, [{'class_name': None}], [{'class_name': 'A', 'url': 'external'}]):
            self.assertEqual((await batch_tools.batch_analysis('class-source', items))['code'], 'invalid_request')
