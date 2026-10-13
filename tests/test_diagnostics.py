import secrets
import unittest
from unittest.mock import AsyncMock, patch

from fastmcp import Client
from fastmcp.server.auth import AccessToken

import jadx_mcp_server
from src.server import authorization, config, instances
from src.server.tools import diagnostic_tools


class DiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def test_degraded_backend_is_visible_without_losing_error(self):
        payload = {'error': 'offline', 'code': 'unavailable'}
        with patch.object(config, 'get_from_jadx', AsyncMock(return_value=payload)):
            async with Client(jadx_mcp_server.mcp) as client:
                result = await client.call_tool('get_runtime_diagnostics')
        self.assertEqual(result.data['state'], 'degraded')
        self.assertEqual(result.data['backend'], payload)

    async def test_status_never_dispatches_to_other_users_instance(self):
        registry = {name: {'id': name, 'url': f'http://localhost/{name}', 'aliases': []} for name in ('a', 'b')}
        access = AccessToken(token=secrets.token_urlsafe(32), client_id='reader', scopes=['jadx'])
        with patch.object(instances, 'registry', registry), patch.object(authorization, 'http_enabled', True), patch.object(
                authorization, 'users', {'reader': {'instances': {'a': 'read'}}}), patch.object(
                authorization, 'get_access_token', return_value=access), patch.object(
                config, 'get_from_jadx', AsyncMock(return_value={'threads': 4})) as fetch:
            result = await diagnostic_tools.status_view()
        self.assertEqual([item['instance'] for item in result['instances']], ['a'])
        self.assertEqual(fetch.await_count, 1)
        self.assertNotIn('localhost', str(result))

    async def test_status_deadline_cancels_slow_backends_together(self):
        import asyncio
        registry = {name: {'id': name, 'url': f'http://localhost/{name}', 'aliases': []} for name in ('a', 'b')}
        active = 0
        async def slow():
            nonlocal active
            active += 1
            try:
                await asyncio.sleep(60)
            finally:
                active -= 1
        with patch.object(instances, 'registry', registry), patch.object(diagnostic_tools, 'STATUS_TIMEOUT', .01), patch.object(
                diagnostic_tools, 'get_runtime_diagnostics', side_effect=slow):
            result = await asyncio.wait_for(diagnostic_tools.status_view(), .2)
        self.assertEqual(active, 0)
        self.assertEqual(len(result['instances']), 2)
        self.assertTrue(all(item['backend']['code'] == 'timeout' for item in result['instances']))
