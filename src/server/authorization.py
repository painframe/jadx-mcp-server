"""Runtime bearer identities and canonical instance permissions for remote MCP."""

import hmac
import json
import os
from pathlib import Path

from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.dependencies import get_access_token, get_http_request

from src.server import instances

http_enabled = False
users: dict[str, dict] = {}


def load_policy(path: str) -> str | None:
    global users
    try:
        with Path(path).open(encoding='utf-8') as source:
            raw = source.read(1_048_577)
        if len(raw) > 1_048_576:
            return 'User policy exceeds 1 MiB'
        document = json.loads(raw)
    except (OSError, ValueError):
        return 'Cannot read user policy JSON'
    if not isinstance(document, dict) or not isinstance(document.get('users'), list) or not 1 <= len(document['users']) <= 256:
        return 'User policy requires 1..256 users'
    proposed = {}
    known = set(instances.registry) or {'default'}
    for item in document['users']:
        if not isinstance(item, dict):
            return 'Each user policy must be an object'
        name, token_env, permissions = item.get('id'), item.get('token_env'), item.get('instances')
        if (not isinstance(name, str) or not name or len(name) > 128 or name in proposed
                or not isinstance(token_env, str) or not token_env or not isinstance(permissions, dict)
                or not permissions.keys() <= known or any(not isinstance(value, str) or value not in {'read', 'write'} for value in permissions.values())):
            return 'Invalid user ID, credential reference or canonical instance permissions'
        credential = os.environ.get(token_env, '')
        if len(credential) < 32 or len(credential) > 8192 or not credential.isascii() or any(char.isspace() or not char.isprintable() for char in credential):
            return 'User token must be an ASCII environment value of 32..8192 characters'
        if any(hmac.compare_digest(credential, other['credential']) for other in proposed.values()):
            return 'Each user must have a distinct token'
        proposed[name] = {'credential': credential, 'instances': dict(permissions)}
    users = proposed
    return None


class UserTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        if not token.isascii() or len(token) > 8192:
            return None
        identity = None
        for name, item in users.items():
            if hmac.compare_digest(token, item['credential']):
                identity = name
        if identity is None:
            return None
        return AccessToken(token=token, client_id=identity, scopes=['jadx'])


def can_access(identity: str | None, write: bool = False) -> bool:
    if not http_enabled:
        try:
            get_http_request()
        except RuntimeError:
            # FastMCP signals trusted in-process/stdio execution with no HTTP request.
            return True
    access = get_access_token()
    if access is None or access.client_id not in users:
        return False
    permission = users[access.client_id]['instances'].get(identity or 'default')
    return permission == 'write' or (permission == 'read' and not write)


def forbidden(identity: str | None, write: bool = False) -> dict | None:
    if can_access(identity, write):
        return None
    return {'error': 'Access to this instance or operation is forbidden', 'code': 'forbidden',
            'retryable': False, 'source': 'bridge', 'status': 403}
