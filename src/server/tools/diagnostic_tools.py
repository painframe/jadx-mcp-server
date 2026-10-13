"""Permitted backend diagnostics and an authenticated MCP status resource."""

import asyncio

from src.server import authorization, config, instances
from src.server.scheduling import gate_for


async def get_runtime_diagnostics() -> dict:
    identity = instances.selected_instance.get()
    denied = authorization.forbidden(identity)
    if denied:
        return denied
    result = await config.get_from_jadx('runtime-diagnostics', timeout=5)
    gate = gate_for(identity or config.JADX_HTTP_BASE)
    scheduling = {'readers': gate.readers, 'writer': gate.writer, 'queued': gate.pending} if gate else {'saturated': True}
    return {'instance': identity or 'default', 'backend': result, 'bridge_queue': scheduling,
            'state': 'degraded' if isinstance(result, dict) and result.get('error') else 'ready'}


STATUS_TIMEOUT = 5.0


async def status_view() -> dict:
    identities = [item['id'] for item in instances.public_instances()] if instances.registry else [None]
    permitted = [identity for identity in identities if authorization.can_access(identity)]
    semaphore = asyncio.Semaphore(4)

    async def inspect(identity):
        async with semaphore:
            token = instances.selected_instance.set(identity)
            try:
                return await get_runtime_diagnostics()
            finally:
                instances.selected_instance.reset(token)

    tasks = {asyncio.create_task(inspect(identity)): identity for identity in permitted}
    if not tasks:
        return {'instances': []}
    try:
        done, pending = await asyncio.wait(tasks, timeout=STATUS_TIMEOUT)
        results = [task.result() for task in tasks if task in done]
        results.extend({'instance': tasks[task] or 'default', 'state': 'degraded',
                        'backend': {'error': 'Status deadline exceeded', 'code': 'timeout'}}
                       for task in tasks if task in pending)
        return {'instances': results}
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
