import unittest
from unittest.mock import AsyncMock, patch

import httpx

from src.PaginationUtils import PaginationUtils
from src.server import config


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, method, response):
        real_client = httpx.AsyncClient
        with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(lambda request: response), **kw)):
            return await method('example')

    async def test_get_and_post_preserve_structured_error(self):
        payload = {'error': 'No project', 'code': 'no_project', 'source': 'jadx', 'retryable': False}
        for method in (config.get_from_jadx, config.post_to_jadx):
            result = await self.request(method, httpx.Response(409, json=payload))
            self.assertEqual(result, {**payload, 'endpoint': 'example', 'status': 409})

    async def test_null_json_is_error_and_legacy_text_preserved(self):
        result = await self.request(config.get_from_jadx, httpx.Response(200, json=None,
                                    headers={'content-type': 'application/json'}))
        self.assertEqual(result['code'], 'invalid_response')
        self.assertEqual(await self.request(config.get_from_jadx, httpx.Response(200, text='legacy')),
                         {'response': 'legacy'})

    async def test_invalid_pagination_does_not_dispatch(self):
        fetch = AsyncMock()
        for offset, count in [(-1, 20), (0, -1), (True, 2), ('0', 1), (0, 10001)]:
            result = await PaginationUtils.get_paginated_data('classes', offset, count, fetch_function=fetch)
            self.assertEqual(result['code'], 'invalid_request')
        fetch.assert_not_called()

    async def test_invalid_items_and_null_are_errors(self):
        for response in [None, {'items': None}, {'items': {}}, {'pagination': []}]:
            result = await PaginationUtils.get_paginated_data('classes', fetch_function=AsyncMock(return_value=response))
            self.assertEqual(result['code'], 'invalid_response')

    async def test_error_body_is_not_echoed(self):
        result = await self.request(config.get_from_jadx, httpx.Response(500, text='secret credential'))
        self.assertNotIn('secret', str(result))

    async def test_actual_class_tool_preserves_backend_list(self):
        from src.server.tools import class_tools
        with patch.object(class_tools, 'get_from_jadx', AsyncMock(return_value=['a.Class'])):
            result = await class_tools.get_all_classes()
        self.assertEqual(result['items'], ['a.Class'])

    async def test_legacy_get_mutation_timeout_is_not_retryable(self):
        real_client = httpx.AsyncClient
        def fail(request):
            raise httpx.ReadTimeout('late')
        with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(fail), **kw)):
            result = await config.get_from_jadx('rename-class')
        self.assertFalse(result['retryable'])

    async def test_error_metadata_is_bounded_and_transport_owned(self):
        result = await self.request(config.get_from_jadx, httpx.Response(409, json={
            'error': 'x' * 10000, 'status': 200, 'endpoint': 'other', 'source': 'evil'}))
        self.assertEqual(len(result['error']), 512)
        self.assertEqual(result['status'], 409)
        self.assertEqual(result['endpoint'], 'example')
        self.assertEqual(result['source'], 'jadx')

    async def test_malformed_transform_becomes_error(self):
        result = await PaginationUtils.get_paginated_data('classes',
            fetch_function=AsyncMock(return_value={'items': [None]}),
            item_transformer=lambda item: item['name'])
        self.assertEqual(result['code'], 'invalid_response')

class ResilienceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        config._failures.clear()

    def tearDown(self):
        config._failures.clear()

    async def test_connection_failure_cooldown_is_per_backend(self):
        calls = []
        def fail(request):
            calls.append(str(request.url))
            raise httpx.ConnectError('unreachable')
        real_client = httpx.AsyncClient
        with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(fail), **kw)):
            await config.get_from_jadx('classes')
            result = await config.post_to_jadx('cache-clear')
            self.assertEqual(result['code'], 'unavailable')
            self.assertEqual(len(calls), 1)
            with patch.object(config, 'JADX_HTTP_BASE', 'http://127.0.0.1:9999'):
                await config.get_from_jadx('classes')
            self.assertEqual(len(calls), 2)

    async def test_search_keeps_long_read_timeout_and_no_proxy(self):
        observed = []
        def handle(request):
            observed.append(request.extensions['timeout'])
            return httpx.Response(200, json={'items': []})
        real_client = httpx.AsyncClient
        def factory(**kw):
            self.assertFalse(kw['trust_env'])
            return real_client(transport=httpx.MockTransport(handle), **kw)
        with patch.object(config.httpx, 'AsyncClient', side_effect=factory):
            await config.get_from_jadx('search', timeout=config.JADX_SEARCH_TIMEOUT)
        self.assertEqual(observed[0]['read'], 3600)
        self.assertEqual(observed[0]['connect'], 5)

    async def test_ordinary_http_errors_do_not_cooldown(self):
        real_client = httpx.AsyncClient
        with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(lambda request: httpx.Response(404)), **kw)):
            await config.get_from_jadx('missing')
        self.assertEqual(config._failures, {})

    async def test_total_deadline_and_cancellation(self):
        import asyncio
        async def slow(request):
            await asyncio.sleep(60)
        real_client = httpx.AsyncClient
        with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(slow), **kw)), patch.object(config, 'JADX_CONNECT_TIMEOUT', .001):
            result = await config.get_from_jadx('slow', timeout=.001)
            self.assertEqual(result['code'], 'timeout')
            task = asyncio.create_task(config.post_to_jadx('mutation'))
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
