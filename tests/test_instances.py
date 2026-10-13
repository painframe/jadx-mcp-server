import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastmcp import Client

import jadx_mcp_server
from src.server import config, instances


class InstanceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.saved = instances.registry, instances.default_instance
        instances.registry = {
            'a': {'id': 'a', 'url': 'http://127.0.0.1:8650', 'aliases': ['first']},
            'b': {'id': 'b', 'url': 'http://127.0.0.1:8651', 'aliases': ['second']},
        }
        instances.default_instance = 'a'

    def tearDown(self):
        instances.registry, instances.default_instance = self.saved

    async def test_concurrent_mcp_selectors_do_not_cross_route(self):
        async def handler(request):
            await asyncio.sleep(0)
            return httpx.Response(200, json={'backend': request.url.port})
        real_client = httpx.AsyncClient
        with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(handler), **kw)):
            async with Client(jadx_mcp_server.mcp) as client:
                first, second = await asyncio.gather(
                    client.call_tool('get_class_info', {'class_name': 'A', 'instance': 'first'}),
                    client.call_tool('get_class_info', {'class_name': 'B', 'instance': '8651'}))
                self.assertEqual(first.data, {'backend': 8650})
                self.assertEqual(second.data, {'backend': 8651})
                denied = await client.call_tool('get_class_info', {'class_name': 'A', 'instance': 'http://attacker.test'})
                self.assertEqual(denied.data['code'], 'invalid_instance')
                tools = await client.list_tools()
                for tool in tools:
                    if tool.name in ('list_instances', 'refresh_instances'):
                        continue
                    schema = getattr(tool, 'input_schema', None) or tool.inputSchema
                    self.assertIn('instance', schema['properties'])
        self.assertIsNone(instances.selected_instance.get())

    async def test_registry_rejects_alias_collision_atomically(self):
        document = {'instances': [{'id': 'a', 'url': 'http://localhost:1', 'aliases': ['b']},
                                  {'id': 'b', 'url': 'http://localhost:2'}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'registry.json'
            path.write_text(json.dumps(document))
            self.assertIsNotNone(instances.load_registry(str(path)))
        self.assertEqual(len(instances.registry), 2)
        self.assertEqual(instances.registry['a']['aliases'], ['first'])

    async def test_refresh_requires_plugin_identity(self):
        real_client = httpx.AsyncClient
        with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'status': 'OK'})), **kw)):
            await instances.refresh_instances()
        self.assertFalse(instances.registry['a']['available'])
        self.assertFalse(instances.registry['b']['available'])
