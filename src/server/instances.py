"""Administrator-owned backend registry and request-local instance selection."""

import asyncio
import json
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx

selected_instance: ContextVar[str | None] = ContextVar('jadx_instance', default=None)
registry: dict[str, dict] = {}
default_instance: str | None = None


def normalize_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment or
                (parsed.port is not None and not 1 <= parsed.port <= 65535)):
            return None
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip('/'), '', ''))
    except (ValueError, TypeError):
        return None


def load_registry(path: str) -> str | None:
    global registry, default_instance
    try:
        with Path(path).open(encoding='utf-8') as source:
            raw = source.read(1_048_577)
        if len(raw) > 1_048_576:
            return 'Instance registry exceeds 1 MiB'
        document = json.loads(raw)
    except (OSError, ValueError):
        return 'Cannot read instance registry JSON'
    if not isinstance(document, dict) or not isinstance(document.get('instances'), list) or not 1 <= len(document['instances']) <= 128:
        return 'Registry requires 1..128 instances'
    proposed, selectors, urls = {}, set(), set()
    for item in document['instances']:
        if not isinstance(item, dict):
            return 'Instance entries must be objects'
        name, url, aliases = item.get('id'), normalize_url(item.get('url')), item.get('aliases', [])
        if (not isinstance(name, str) or not name or len(name) > 128 or not url
                or not isinstance(aliases, list) or len(aliases) > 32
                or any(not isinstance(alias, str) or not alias or len(alias) > 128 for alias in aliases)):
            return 'Invalid instance identifier, URL or aliases'
        if name in selectors or any(alias in selectors for alias in aliases) or url in urls:
            return 'Instance selectors and URLs must be unique'
        if any(key in item and (not isinstance(item[key], str) or not item[key]) for key in ('token_env', 'token_file')):
            return 'Invalid backend credential reference'
        selectors.update([name, *aliases])
        urls.add(url)
        proposed[name] = {**item, 'id': name, 'url': url, 'aliases': aliases}
    default = document.get('default')
    if default is not None and default not in proposed:
        return 'Default instance must name a registered ID'
    registry, default_instance = proposed, default
    return None


def resolve(selector: str | None) -> tuple[str | None, str | None]:
    if not registry:
        return (None, None) if selector in (None, 'default') else (None, 'Unknown instance')
    wanted = selector or default_instance
    if wanted is None:
        return (next(iter(registry)), None) if len(registry) == 1 else (None, 'Select an instance explicitly')
    explicit = [name for name, item in registry.items() if wanted == name or wanted in item['aliases']]
    if explicit:
        return (explicit[0], None) if len(explicit) == 1 else (None, 'Ambiguous instance alias')
    matches = [name for name, item in registry.items()
               if wanted == str(urlsplit(item['url']).port) or wanted == item.get('project_name')]
    return (matches[0], None) if len(matches) == 1 else (None, 'Unknown or ambiguous instance')


def current() -> dict | None:
    return registry.get(selected_instance.get())


def public_instances() -> list[dict]:
    return [{'id': name, 'aliases': item['aliases'], 'project_name': item.get('project_name'),
             'instance_id': item.get('instance_id'), 'capabilities': item.get('capabilities', [])}
            for name, item in registry.items()]


async def refresh_instances() -> list[dict]:
    from src.server import config
    for name in tuple(registry):
        token = selected_instance.set(name)
        try:
            result = await config.get_from_jadx('health', timeout=5)
            if isinstance(result, dict) and result.get('service') == 'jadx-ai-mcp' and isinstance(result.get('instance_id'), str):
                for field in ('instance_id', 'project_name', 'capabilities'):
                    registry[name][field] = result.get(field)
                registry[name]['available'] = True
            else:
                registry[name]['available'] = False
        finally:
            selected_instance.reset(token)
    return public_instances()


async def discover_local() -> None:
    """Only administrator-started, bounded loopback discovery; identity is mandatory."""
    async with httpx.AsyncClient(trust_env=False, timeout=1) as client:
        async def probe(port):
            try:
                response = await client.get(f'http://127.0.0.1:{port}/health')
                payload = response.json()
            except (httpx.HTTPError, ValueError):
                return None
            if response.is_success and isinstance(payload, dict) and payload.get('service') == 'jadx-ai-mcp' and isinstance(payload.get('instance_id'), str):
                return {'id': payload['instance_id'], 'url': f'http://127.0.0.1:{port}', 'aliases': [str(port)],
                        'project_name': payload.get('project_name'), 'capabilities': payload.get('capabilities', [])}
            return None
        for item in await asyncio.gather(*(probe(port) for port in range(8650, 8666))):
            if item and len(registry) < 128 and item['id'] not in registry and all(existing['url'] != item['url'] for existing in registry.values()):
                registry[item['id']] = item
