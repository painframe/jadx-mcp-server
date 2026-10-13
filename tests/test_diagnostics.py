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
