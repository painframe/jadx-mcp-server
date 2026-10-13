"""Project loading operations; a submitted load is not yet a ready project."""

from src.server.config import error_response, get_from_jadx, post_to_jadx


async def open_apk(path: str, replace: bool = False) -> dict:
    """Schedule opening a backend-host APK/DEX/JAR; poll its operation for readiness."""
    if not isinstance(path, str) or not path.startswith('/') or '\x00' in path or len(path) > 4096:
        return error_response('path must be an absolute backend-host path under 4096 characters', 'invalid_request')
    if type(replace) is not bool:
        return error_response('replace must be boolean', 'invalid_request')
    return await post_to_jadx('open-apk', json_body={'path': path, 'replace': replace})


async def get_project_operation(operation_id: str) -> dict:
    """Read loading/ready/failed state; ready is the point at which analysis may begin."""
    if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 128:
        return error_response('Invalid project operation identifier', 'invalid_request')
    return await get_from_jadx('project-operation', {'operation_id': operation_id})
