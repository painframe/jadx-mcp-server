import unittest
from unittest.mock import AsyncMock, patch

from fastmcp import Client

import jadx_mcp_server
from src.server import config


class ContinuationTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_mcp_continuation_preserves_unicode_and_cursor(self):
        payload = {'content': 'Þjóð', 'continuation': {'next_cursor': 'opaque', 'generation': '42'}}
        with patch.object(config, 'get_from_jadx', AsyncMock(return_value=payload)) as fetch:
            async with Client(jadx_mcp_server.mcp) as client:
                result = await client.call_tool('get_class_source', {'class_name': 'example.Class', 'max_bytes': 32})
            self.assertEqual(result.data, payload)
            self.assertEqual(fetch.await_args.args, ('class-source', {'class_name': 'example.Class', 'max_bytes': 32}))

    async def test_old_plugin_rejected_only_when_opted_in(self):
        with patch.object(config, 'get_from_jadx', AsyncMock(return_value={'response': 'whole'})):
            self.assertEqual(await config.get_content_from_jadx('class-source', {}), {'response': 'whole'})
            result = await config.get_content_from_jadx('class-source', {}, 32)
            self.assertEqual(result['code'], 'unsupported_capability')

    async def test_invalid_bounds_never_dispatch(self):
        with patch.object(config, 'get_from_jadx', AsyncMock()) as fetch:
            for size in (-1, 0, True, 1_048_577):
                result = await config.get_content_from_jadx('class-source', {}, size)
                self.assertEqual(result['code'], 'invalid_request')
            fetch.assert_not_called()

    async def test_manifest_entity_expansion_is_rejected(self):
        from src.server.tools import resource_tools
        payload = {'content': '<!DOCTYPE x [<!ENTITY data "expanded">]><manifest>&data;</manifest>'}
        with patch.object(resource_tools, 'get_android_manifest', AsyncMock(return_value=payload)):
            result = await resource_tools.get_manifest_component('activity')
        self.assertIn('error', result)
