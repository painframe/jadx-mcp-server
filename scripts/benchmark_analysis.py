"""Compare the same loaded fixture on two plugin revisions, without modifying projects."""

import argparse
import asyncio
import hashlib
import json
import math
import os
import statistics
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def summarize(samples: list[dict]) -> dict:
    complete = [sample for sample in samples if sample['ok'] and not sample.get('partial', False)]
    latencies = sorted(sample['elapsed_ms'] for sample in complete)
    return {'requests': len(samples), 'successful': len(complete), 'failed': sum(not sample['ok'] and not sample.get('partial', False) for sample in samples),
            'partial': sum(sample.get('partial', False) for sample in samples),
            'median_ms': statistics.median(latencies) if latencies else None,
            'p95_ms': latencies[max(0, math.ceil(.95 * len(latencies)) - 1)] if latencies else None,
            'samples': samples}


async def sample(client: httpx.AsyncClient, base: str, endpoint: str, params: dict,
                 timeout: float, body: dict | None = None) -> dict:
    started = time.perf_counter()
    result = {'ok': False, 'partial': False}
    try:
        async with asyncio.timeout(timeout), client.stream('POST' if body else 'GET',
                f'{base}/{endpoint}', params=params, json=body) as response:
            content = bytearray()
            async for chunk in response.aiter_bytes():
                if len(content) + len(chunk) > MAX_RESPONSE_BYTES:
                    result['code'] = 'response_too_large'
                    break
                content.extend(chunk)
            else:
                try:
                    payload = json.loads(content)
                except ValueError:
                    payload = {'response': content.decode('utf-8', errors='replace')}
                result.update(status=response.status_code, bytes=len(content))
                if isinstance(payload, dict):
                    result['ok'] = response.is_success and not payload.get('error')
                    result['partial'] = payload.get('partial') is True or payload.get('timed_out') is True
                    if payload.get('error'):
                        result['code'] = payload.get('code', 'backend_error')
                    source = next((payload[key] for key in ('content', 'response', 'code')
                                   if isinstance(payload.get(key), str) and not payload.get('error')), None)
                    if endpoint == 'class-source':
                        result['ok'] = result['ok'] and source is not None
                        if source is not None:
                            result['source_sha256'] = hashlib.sha256(source.encode()).hexdigest()
                    if endpoint == 'runtime-diagnostics':
                        result['metrics'] = {key: payload[key] for key in
                            ('heap_used_bytes', 'heap_max_bytes', 'thread_count')
                            if type(payload.get(key)) in (int, float)}
                        for key, path in {'heap_used_bytes': ('memory', 'heap', 'used_bytes'),
                                          'heap_max_bytes': ('memory', 'heap', 'max_bytes'),
                                          'thread_count': ('threads', 'live')}.items():
                            value = payload
                            for part in path:
                                value = value.get(part) if isinstance(value, dict) else None
                            if type(value) in (int, float):
                                result['metrics'][key] = value
                    if endpoint == 'batch-analysis':
                        items = payload.get('results')
                        result['ok'] = result['ok'] and isinstance(items, list) and len(items) == len(body['items']) and all(
                            isinstance(item, dict) and item.get('ok') is True and isinstance(item.get('data'), (dict, list)) for item in items)
                    if endpoint == 'search-classes-by-keyword':
                        classes = payload.get('classes', payload.get('items'))
                        result['ok'] = result['ok'] and isinstance(classes, list)
                        result['result_count'] = len(classes) if isinstance(classes, list) else 0
                else:
                    result['code'] = 'invalid_response'
    except (httpx.HTTPError, TimeoutError):
        result['code'] = 'transport_error'
    if result['partial']:
        result['ok'] = False
    result['elapsed_ms'] = round((time.perf_counter() - started) * 1000, 3)
    return result


async def benchmark(base: str, credential: str, class_name: str, iterations: int, concurrency: int, timeout: float) -> dict:
    semaphore = asyncio.Semaphore(concurrency)
    headers = {'Authorization': f'Bearer {credential}'} if credential else {}
    async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(timeout, connect=5), trust_env=False) as client:
        cases = {
            'source_warm': ('class-source', {'class_name': class_name}, None),
            'search_repeated': ('search-classes-by-keyword', {'search_term': class_name.rsplit('.', 1)[-1], 'search_in': 'class', 'limit': 100}, None),
            'batch_source': ('batch-analysis', {}, {'operation': 'class-source', 'items': [{'class_name': class_name}], 'max_bytes': 65536}),
            'cache_stats': ('cache-stats', {}, None),
            'runtime_diagnostics': ('runtime-diagnostics', {}, None),
        }
        output = {}
        for name, (endpoint, params, body) in cases.items():
            warmup = await sample(client, base, endpoint, params, timeout, body)
            async def measured(endpoint=endpoint, params=params, body=body):
                async with semaphore:
                    return await sample(client, base, endpoint, params, timeout, body)
            output[name] = summarize(await asyncio.gather(*(measured() for _ in range(iterations))))
            output[name]['warmup'] = warmup
        return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for label in ('baseline', 'candidate'):
        parser.add_argument(f'--{label}-url', required=True)
        parser.add_argument(f'--{label}-revision', required=True)
        parser.add_argument(f'--{label}-token-env', default=f'JADX_{label.upper()}_TOKEN')
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--class-name', required=True)
    parser.add_argument('--iterations', type=int, default=5)
    parser.add_argument('--concurrency', type=int, default=4)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.iterations <= 100 or not 1 <= args.concurrency <= 16 or not 0 < args.timeout <= 3600:
        parser.error('iterations 1..100, concurrency 1..16, timeout (0,3600] required')
    endpoints = {}
    for label in ('baseline', 'candidate'):
        url = getattr(args, f'{label}_url').rstrip('/')
        try:
            parsed = urlsplit(url)
        except ValueError:
            parser.error('Invalid HTTP(S) benchmark URL')
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            parser.error('Benchmark URLs require HTTP(S), without credentials, query or fragment')
        credential = os.environ.get(getattr(args, f'{label}_token_env'), '')
        if not credential.isascii() or any(char.isspace() or not char.isprintable() for char in credential):
            parser.error('Invalid runtime benchmark token')
        endpoints[label] = url, credential
    try:
        with args.fixture.open('rb') as source:
            fixture_hash = hashlib.file_digest(source, 'sha256').hexdigest()
    except OSError:
        parser.error('Cannot read fixture')
    report = {'fixture_sha256': fixture_hash, 'class_name': args.class_name, 'iterations': args.iterations,
              'concurrency': args.concurrency, 'results': {}, 'limits': [
                  'Fixtures must be loaded manually before running; fixture hash identifies the supplied local file.',
                  'Warm repeated reads only; no cold-cache claim or process RSS measurement.',
                  'Unsupported and partial results are not successful performance comparisons.']}
    for label, (url, credential) in endpoints.items():
        report['results'][label] = {'revision': getattr(args, f'{label}_revision'),
            'cases': asyncio.run(benchmark(url, credential, args.class_name, args.iterations, args.concurrency, args.timeout))}
    source_sets = [{sample.get('source_sha256') for sample in report['results'][label]['cases']['source_warm']['samples']}
                   for label in ('baseline', 'candidate')]
    report['source_equal'] = (source_sets[0] == source_sets[1] and None not in source_sets[0]
        and all(report['results'][label]['cases']['source_warm']['successful'] == args.iterations
                for label in ('baseline', 'candidate')))
    try:
        with args.output.open('x', encoding='utf-8') as target:
            json.dump(report, target, indent=2)
            target.write('\n')
    except OSError:
        parser.error('Cannot create output report; existing files are not overwritten')
    return 0 if report['source_equal'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
