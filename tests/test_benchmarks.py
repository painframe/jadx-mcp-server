import unittest

import httpx

from scripts.benchmark_analysis import sample, summarize


class BenchmarkTests(unittest.IsolatedAsyncioTestCase):
    def test_statistics_do_not_hide_failures_or_partial_results(self):
        result = summarize([{'elapsed_ms': 1, 'ok': True}, {'elapsed_ms': 10, 'ok': False, 'partial': True}])
        self.assertEqual(result['successful'], 1)
        self.assertEqual(result['partial'], 1)
        self.assertEqual(result['p95_ms'], 10)

    async def test_source_hash_and_unsupported_batch_are_distinct(self):
        def handler(request):
            return httpx.Response(404) if request.method == 'POST' else httpx.Response(200, json={'response': 'class A {}'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = await sample(client, 'http://localhost', 'class-source', {}, 1)
            batch = await sample(client, 'http://localhost', 'batch-analysis', {}, 1, {'items': [{}]})
        self.assertTrue(source['ok'])
        self.assertEqual(len(source['source_sha256']), 64)
        self.assertFalse(batch['ok'])
