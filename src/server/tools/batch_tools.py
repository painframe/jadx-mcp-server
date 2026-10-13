"""Bounded batch access to the same backend analysis operations as individual tools."""

from typing import Literal

from src.server.config import error_response, post_to_jadx

BatchOperation = Literal['class-source', 'method-by-name', 'xrefs-to-class', 'xrefs-to-method', 'xrefs-to-field']
_REQUIRED = {
    'class-source': {'class_name'},
    'method-by-name': {'class_name', 'method_name'},
    'xrefs-to-class': {'class_name'},
    'xrefs-to-method': {'class_name', 'method_name'},
    'xrefs-to-field': {'class_name', 'field_name'},
}


async def batch_analysis(operation: BatchOperation, items: list[dict], max_bytes: int = 65536) -> dict:
    """Read up to fifty targets; one failed item does not discard successful siblings."""
    if operation not in _REQUIRED or not isinstance(items, list) or not 1 <= len(items) <= 50:
        return error_response('Batch requires a supported operation and 1..50 items', 'invalid_request')
    if type(max_bytes) is not int or not 1 <= max_bytes <= 1_048_576:
        return error_response('max_bytes must be between 1 and 1048576', 'invalid_request')
    allowed = _REQUIRED[operation] | {'method_signature', 'offset', 'limit', 'cursor'}
    for item in items:
        if not isinstance(item, dict) or not _REQUIRED[operation] <= item.keys() or item.keys() - allowed:
            return error_response('Invalid batch item parameters', 'invalid_request')
        for name, value in item.items():
            if name in {'offset', 'limit'}:
                if type(value) is not int or not 0 <= value <= (1_000_000 if name == 'offset' else 10_000):
                    return error_response('Invalid batch pagination', 'invalid_request')
            elif not isinstance(value, str) or not value or len(value) > 4096:
                return error_response('Batch identifiers must be nonempty strings under 4096 characters', 'invalid_request')
    result = await post_to_jadx('batch-analysis', json_body={
        'operation': operation, 'items': items, 'max_bytes': max_bytes})
    if isinstance(result, dict) and result.get('error'):
        return result
    if not isinstance(result, dict) or not isinstance(result.get('results'), list):
        return error_response('Invalid batch response from plugin', 'invalid_response')
    results = result['results']
    if len(results) != len(items):
        return error_response('Incomplete batch response from plugin', 'invalid_response')
    seen = set()
    for item in results:
        if (not isinstance(item, dict) or type(item.get('index')) is not int
                or not 0 <= item['index'] < len(items) or item['index'] in seen
                or type(item.get('ok')) is not bool):
            return error_response('Invalid batch item envelope', 'invalid_response')
        seen.add(item['index'])
        if (item['ok'] and not isinstance(item.get('data'), (dict, list))) or (
                not item['ok'] and not isinstance(item.get('error'), str)):
            return error_response('Invalid batch item payload', 'invalid_response')
    return result
