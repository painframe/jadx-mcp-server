import secrets
import unittest
from unittest.mock import patch

import httpx

import jadx_mcp_server
from src.server import authorization, config, instances


class AuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_http_auth_and_instance_permissions(self):
        credential = secrets.token_urlsafe(32)
        saved_auth = jadx_mcp_server.mcp.auth
        saved_users, saved_mode = authorization.users, authorization.http_enabled
        saved_registry, saved_default = instances.registry, instances.default_instance
        authorization.users = {'reader': {'credential': credential, 'instances': {'a': 'read'}}}
        authorization.http_enabled = True
        instances.registry = {
            'a': {'id': 'a', 'url': 'http://127.0.0.1:8650', 'aliases': ['allowed']},
            'b': {'id': 'b', 'url': 'http://127.0.0.1:8651', 'aliases': ['denied']}}
        instances.default_instance = 'a'
        jadx_mcp_server.mcp.auth = authorization.UserTokenVerifier(required_scopes=['jadx'])
        app = jadx_mcp_server.mcp.http_app(stateless_http=True, json_response=True)
        requests = []
        def backend(request):
            requests.append(request)
            return httpx.Response(200, json={'ok': True})
        real_client = httpx.AsyncClient
        try:
            async with app.router.lifespan_context(app), real_client(
                    transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                headers = {'accept': 'application/json, text/event-stream'}
                payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                           'params': {'name': 'get_class_info', 'arguments': {'class_name': 'A'}}}
                self.assertEqual((await client.post('/mcp', json=payload, headers=headers)).status_code, 401)
                headers['authorization'] = f'Bearer {credential}'
                with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                        transport=httpx.MockTransport(backend), **kw)):
                    response = await client.post('/mcp', json=payload, headers=headers)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(len(requests), 1)
                    for selector in ('b', 'denied', '8651'):
                        payload['params']['arguments']['instance'] = selector
                        response = await client.post('/mcp', json=payload, headers=headers)
                        self.assertIn('forbidden', response.text)
                    self.assertEqual(len(requests), 1)
                    payload['params'] = {'name': 'rename_class', 'arguments': {
                        'class_name': 'A', 'new_name': 'B', 'instance': 'allowed'}}
                    response = await client.post('/mcp', json=payload, headers=headers)
                    self.assertIn('forbidden', response.text)
                    self.assertEqual(len(requests), 1)
                    payload['params'] = {'name': 'list_instances', 'arguments': {}}
                    response = await client.post('/mcp', json=payload, headers=headers)
                    result = response.json()['result']['structuredContent']
                    self.assertEqual([item['id'] for item in result['instances']], ['a'])
                    self.assertNotIn(credential, response.text)
                    self.assertNotIn('127.0.0.1', response.text)
        finally:
            jadx_mcp_server.mcp.auth = saved_auth
            authorization.users, authorization.http_enabled = saved_users, saved_mode
            instances.registry, instances.default_instance = saved_registry, saved_default

    async def test_unauthenticated_internal_dispatch_fails_closed(self):
        with patch.object(authorization, 'http_enabled', True), patch.object(authorization, 'get_access_token', return_value=None):
            result = await config.get_from_jadx('class-info')
            self.assertEqual(result['code'], 'forbidden')
