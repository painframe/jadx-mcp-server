"""
JADX MCP Server - Configuration Module

This module manages server configuration, HTTP client setup, and communication
with the JADX Java plugin. Handles connection management, error handling,
and request/response processing.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

import asyncio
import logging
import math
import os
import sys
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from src.server import authorization, instances
from src.server.scheduling import gate_for

# Default Configuration
JADX_HOST = "127.0.0.1"
JADX_PORT = 8650
JADX_HTTP_BASE = f"http://{JADX_HOST}:{JADX_PORT}"
JADX_TOKEN_FILE: str | None = None
FEATURE_ENDPOINTS = frozenset({"class-info", "method-signature", "search-native-methods", "batch-analysis",
    "open-apk", "project-operation", "jvm-info", "runtime-diagnostics"})

# HTTP read timeouts (seconds) for plugin communication
JADX_DEFAULT_TIMEOUT = 60.0
JADX_SEARCH_TIMEOUT = 3600.0
MUTATING_ENDPOINTS = frozenset({"rename-class", "rename-method", "rename-field",
    "rename-package", "rename-variable", "add-comment", "cache-clear", "open-apk"})


def is_mutation(method: str, endpoint: str) -> bool:
    return (method != "GET" and not (method == "POST" and endpoint.strip("/") == "batch-analysis")) or endpoint.strip("/") in MUTATING_ENDPOINTS
JADX_CONNECT_TIMEOUT = 5.0
JADX_FAILURE_COOLDOWN = 3.0
_FAILURES_MAX = 128
_failures: OrderedDict[str, float] = OrderedDict()


def _http_timeout(read_timeout: float) -> httpx.Timeout:
    return httpx.Timeout(read_timeout, connect=min(read_timeout, JADX_CONNECT_TIMEOUT),
                         pool=min(read_timeout, JADX_CONNECT_TIMEOUT))


def _cooling_down(base: str) -> bool:
    failed_at = _failures.get(base)
    if failed_at is None:
        return False
    if time.monotonic() - failed_at < JADX_FAILURE_COOLDOWN:
        return True
    _failures.pop(base, None)
    return False


def _record_failure(base: str) -> None:
    _failures[base] = time.monotonic()
    _failures.move_to_end(base)
    while len(_failures) > _FAILURES_MAX:
        _failures.popitem(last=False)


# Logging Setup
logger = logging.getLogger("jadx-mcp-server")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
logger.setLevel(logging.ERROR)
logger.propagate = False


def _rebuild_jadx_http_base():
    """Rebuild the base URL used for all requests to the JADX plugin."""
    global JADX_HTTP_BASE
    host = f"[{JADX_HOST}]" if ":" in JADX_HOST and not JADX_HOST.startswith("[") else JADX_HOST
    JADX_HTTP_BASE = f"http://{host}:{JADX_PORT}"


def set_jadx_url(url: str) -> dict | None:
    global JADX_HTTP_BASE
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme in {"http", "https"} and parsed.hostname
                 and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
                 and (parsed.port is None or 1 <= parsed.port <= 65535))
    except ValueError:
        valid = False
    if not valid:
        return error_response("Invalid backend URL; use HTTP(S) without credentials, query or fragment", "invalid_request")
    JADX_HTTP_BASE = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
    return None


def backend_headers() -> tuple[dict, dict | None]:
    selected = instances.current()
    path = selected.get("token_file") if selected else JADX_TOKEN_FILE or os.environ.get("JADX_API_TOKEN_FILE")
    token = os.environ.get(selected.get("token_env", ""), "") if selected else os.environ.get("JADX_API_TOKEN", "")
    if selected and selected.get("token_env") and not token:
        return {}, error_response("Backend token environment variable is empty", "configuration_error")
    if path:
        try:
            with Path(path).open(encoding="utf-8") as source:
                token = source.read(8193).strip()
        except (OSError, UnicodeError):
            return {}, error_response("Cannot read backend token file", "configuration_error")
    if (path and not token) or len(token) > 8192 or not token.isascii() or any(c.isspace() or not c.isprintable() for c in token):
        return {}, error_response("Invalid backend bearer token", "configuration_error")
    return ({"Authorization": f"Bearer {token}"} if token else {}), None


def set_jadx_host(host: str):
    """
    Updates the JADX plugin host.

    Args:
        host: Hostname or IP where JADX AI MCP plugin is reachable

    Side Effects:
        Updates global JADX_HOST and JADX_HTTP_BASE configuration
    """
    global JADX_HOST
    JADX_HOST = host
    _rebuild_jadx_http_base()


def set_jadx_port(port: int):
    """
    Updates the JADX plugin port.

    Args:
        port: TCP port number where JADX AI MCP plugin is listening

    Side Effects:
        Updates global JADX_PORT and JADX_HTTP_BASE configuration
    """
    global JADX_PORT
    JADX_PORT = port
    _rebuild_jadx_http_base()


def error_response(message: str, code: str = "invalid_response", *, retryable: bool = False,
                   endpoint: str | None = None, status: int | None = None) -> dict:
    result = {"error": message, "code": code, "retryable": retryable, "source": "bridge"}
    if endpoint is not None:
        result["endpoint"] = endpoint
    if status is not None:
        result["status"] = status
    return result


def _decode_response(response: httpx.Response, endpoint: str):
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if response.is_error:
        # Never echo arbitrary error bodies: they may contain credentials or HTML.
        if isinstance(payload, dict) and isinstance(payload.get("error"), str):
            message = "".join(c if c.isprintable() else " " for c in payload["error"][:512])
            result = error_response(message, endpoint=endpoint, status=response.status_code)
            result["code"] = payload.get("code", "http_error") if isinstance(payload.get("code", "http_error"), str) else "http_error"
            result["source"] = "jadx"
            result["retryable"] = payload.get("retryable") is True
            if isinstance(payload.get("candidates"), list):
                result["candidates"] = [value[:512] for value in payload["candidates"][:100]
                                        if isinstance(value, str)]
            return result
        return error_response(f"HTTP error {response.status_code} from JADX plugin", "http_error",
                              endpoint=endpoint, status=response.status_code,
                              retryable=response.status_code >= 500)
    if payload is None:
        if response.headers.get("content-type", "").startswith("application/json"):
            return error_response("Expected a JSON object or list", endpoint=endpoint)
        return {"response": response.text}
    if isinstance(payload, (dict, list)):
        return payload
    return error_response("Expected a JSON object or list", endpoint=endpoint)


def health_ping() -> str | dict[str, Any]:
    selected = instances.current()
    base = selected["url"] if selected else JADX_HTTP_BASE
    identity = selected["id"] if selected else base
    denied = authorization.forbidden(selected["id"] if selected else None)
    if denied:
        return denied
    headers, auth_error = backend_headers()
    if auth_error:
        return auth_error
    if _cooling_down(identity):
        return error_response("JADX connection is cooling down", "unavailable", retryable=True,
                              endpoint="health")
    try:
        with httpx.Client(trust_env=False) as client:
            response = client.get(f"{base}/health", headers=headers, timeout=_http_timeout(JADX_CONNECT_TIMEOUT))
            _failures.pop(identity, None)
            if response.is_success:
                return response.text
            return _decode_response(response, "health")
    except httpx.ConnectError:
        _record_failure(identity)
        return error_response("JADX health check failed", "unavailable", retryable=True,
                              endpoint="health")
    except httpx.HTTPError:
        return error_response("JADX health check failed", "unavailable", retryable=True,
                              endpoint="health")


async def _request_jadx(method: str, endpoint: str, params=None,
                        timeout: float = JADX_DEFAULT_TIMEOUT, json_body=None):
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        return error_response("timeout must be a positive finite number", "invalid_request", endpoint=endpoint)
    selected = instances.current()
    base = selected["url"] if selected else JADX_HTTP_BASE
    identity = selected["id"] if selected else base
    denied = authorization.forbidden(selected["id"] if selected else None, is_mutation(method, endpoint))
    if denied:
        return denied
    capabilities = selected.get("capabilities") if selected else None
    if isinstance(capabilities, list) and endpoint != "health" and endpoint not in capabilities:
        return error_response("Operation is not supported by this plugin mode", "unsupported_capability", endpoint=endpoint)
    headers, auth_error = backend_headers()
    if auth_error:
        return auth_error
    if _cooling_down(identity):
        return error_response("JADX connection is cooling down", "unavailable", retryable=not is_mutation(method, endpoint), endpoint=endpoint)
    url = f"{base}/{endpoint.lstrip('/')}"
    try:
        async with asyncio.timeout(timeout + JADX_CONNECT_TIMEOUT):
            control = endpoint.strip("/") in {"health", "search-progress", "project-operation", "runtime-diagnostics"}
            gate = gate_for((identity, "control") if control else identity)
            write = is_mutation(method, endpoint)
            if gate is None or not await gate.acquire(write):
                return error_response("Backend request queue is full", "busy", retryable=True, endpoint=endpoint)
            try:
                async with httpx.AsyncClient(trust_env=False) as client:
                    response = await client.request(method, url, params=params or {},
                                                    json=json_body, headers=headers, timeout=_http_timeout(timeout))
            finally:
                await gate.release(write)
        _failures.pop(identity, None)
        result = _decode_response(response, endpoint)
        if (endpoint in FEATURE_ENDPOINTS and isinstance(result, dict)
                and result.get("status") == 404 and result.get("code") == "http_error"):
            health = await _request_jadx("GET", "health", timeout=5)
            advertised = health.get("capabilities") if isinstance(health, dict) else None
            if not isinstance(advertised, list) or endpoint not in advertised:
                return error_response("Plugin does not advertise the requested feature", "unsupported_capability", endpoint=endpoint)
        if isinstance(result, dict) and result.get("error") and is_mutation(method, endpoint):
            result["retryable"] = False
        return result
    except (httpx.TimeoutException, TimeoutError):
        return error_response(
            f"Request timed out after {timeout}s; operation may still be running in JADX",
            "timeout", retryable=not is_mutation(method, endpoint), endpoint=endpoint)
    except httpx.ConnectError:
        _record_failure(identity)
        return error_response("Cannot connect to JADX plugin", "unavailable",
                              retryable=not is_mutation(method, endpoint), endpoint=endpoint)
    except httpx.HTTPError:
        return error_response("Cannot communicate with JADX plugin", "unavailable",
                              retryable=not is_mutation(method, endpoint), endpoint=endpoint)


async def get_from_jadx(endpoint: str, params: dict[str, Any] | None = None,
                        timeout: float = JADX_DEFAULT_TIMEOUT):
    return await _request_jadx("GET", endpoint, params, timeout)


async def post_to_jadx(endpoint: str, params: dict[str, Any] | None = None,
                       timeout: float = 30, json_body=None):
    return await _request_jadx("POST", endpoint, params, timeout, json_body)


async def get_search_progress() -> dict[str, Any]:
    result = await get_from_jadx("search-progress", timeout=5)
    if not isinstance(result, dict) or result.get("error"):
        return {"state": "unknown", **(result if isinstance(result, dict) else {})}
    return result


async def get_content_from_jadx(endpoint: str, params: dict, max_bytes: int | None = None,
                                cursor: str | None = None):
    """Request explicit backend-owned UTF-8 continuation without truncating metadata."""
    if max_bytes is None and cursor is None:
        return await get_from_jadx(endpoint, params)
    if max_bytes is not None and (type(max_bytes) is not int or not 1 <= max_bytes <= 1_048_576):
        return error_response("max_bytes must be between 1 and 1048576", "invalid_request")
    if cursor is not None and (not isinstance(cursor, str) or not cursor or len(cursor) > 4096):
        return error_response("Invalid continuation cursor", "invalid_request")
    if max_bytes is not None:
        params = {**params, "max_bytes": max_bytes}
    if cursor is not None:
        params = {**params, "cursor": cursor}
    result = await get_from_jadx(endpoint, params)
    if isinstance(result, dict) and result.get("error"):
        return result
    if not isinstance(result, dict) or not isinstance(result.get("continuation"), dict):
        return error_response("Plugin does not support content continuation", "unsupported_capability")
    return result
