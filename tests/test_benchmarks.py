import unittest

import httpx

from scripts.benchmark_analysis import sample, summarize


class BenchmarkTests(unittest.IsolatedAsyncioTestCase):
    def test_statistics_do_not_hide_failures_or_partial_results(self):
        result = summarize([{'elapsed_ms': 1, 'ok': True}, {'elapsed_ms': 10, 'ok': False, 'partial': True}])
        self.assertEqual(result['successful'], 1)
        self.assertEqual(result['partial'], 1)
        # Failure/partial latency is not successful-work latency and cannot imply a speedup.
        self.assertEqual(result['p95_ms'], 1)

    async def test_source_hash_and_unsupported_batch_are_distinct(self):
        def handler(request):
            return httpx.Response(404) if request.method == 'POST' else httpx.Response(200, json={'response': 'class A {}'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = await sample(client, 'http://localhost', 'class-source', {}, 1)
            batch = await sample(client, 'http://localhost', 'batch-analysis', {}, 1, {'items': [{}]})
        self.assertTrue(source['ok'])
        self.assertEqual(len(source['source_sha256']), 64)
        self.assertFalse(batch['ok'])

    async def test_http_200_partial_search_is_not_successful_work(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200,
                json={'classes': ['A'], 'partial': True}))) as client:
            result = await sample(client, 'http://localhost', 'search-classes-by-keyword', {}, 1)
        self.assertFalse(result['ok'])
        self.assertTrue(result['partial'])
        summary = summarize([result])
        self.assertEqual(summary['successful'], 0)
        self.assertIsNone(summary['p95_ms'])

    async def test_diagnostics_records_the_shared_java_nested_schema(self):
        payload = {'memory': {'heap': {'used_bytes': 123, 'max_bytes': 456}},
                   'threads': {'live': 7}}
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=payload))) as client:
            result = await sample(client, 'http://localhost', 'runtime-diagnostics', {}, 1)
        # The shared Java endpoint nests memory/thread metrics; flat donor keys miss them.
        self.assertEqual(result['metrics'], {'heap_used_bytes': 123,
                                            'heap_max_bytes': 456, 'thread_count': 7})
        self.assertTrue(result['ok'])
