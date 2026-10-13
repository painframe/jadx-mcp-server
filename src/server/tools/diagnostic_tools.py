"""Permitted backend diagnostics and an authenticated MCP status resource."""

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


async def status_view() -> dict:
    identities = [item['id'] for item in instances.public_instances()] if instances.registry else [None]
    results = []
    for identity in identities:
        if not authorization.can_access(identity):
            continue
        token = instances.selected_instance.set(identity)
        try:
            results.append(await get_runtime_diagnostics())
        finally:
            instances.selected_instance.reset(token)
    return {'instances': results}
