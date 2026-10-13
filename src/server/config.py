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
import sys
import time
from collections import OrderedDict
from typing import Any

import httpx

# Default Configuration
JADX_HOST = "127.0.0.1"
JADX_PORT = 8650
JADX_HTTP_BASE = f"http://{JADX_HOST}:{JADX_PORT}"

# HTTP read timeouts (seconds) for plugin communication
JADX_DEFAULT_TIMEOUT = 60.0
JADX_SEARCH_TIMEOUT = 3600.0
MUTATING_ENDPOINTS = frozenset({"rename-class", "rename-method", "rename-field",
    "rename-package", "rename-variable", "add-comment", "cache-clear", "open-apk"})


def is_mutation(method: str, endpoint: str) -> bool:
    return method != "GET" or endpoint.strip("/") in MUTATING_ENDPOINTS
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
    JADX_HTTP_BASE = f"http://{JADX_HOST}:{JADX_PORT}"


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
    base = JADX_HTTP_BASE
    if _cooling_down(base):
        return error_response("JADX connection is cooling down", "unavailable", retryable=True,
                              endpoint="health")
    try:
        with httpx.Client(trust_env=False) as client:
            response = client.get(f"{base}/health", timeout=_http_timeout(JADX_CONNECT_TIMEOUT))
            _failures.pop(base, None)
            if response.is_success:
                return response.text
            return _decode_response(response, "health")
    except httpx.ConnectError:
        _record_failure(base)
        return error_response("JADX health check failed", "unavailable", retryable=True,
                              endpoint="health")
    except httpx.HTTPError:
        return error_response("JADX health check failed", "unavailable", retryable=True,
                              endpoint="health")


async def _request_jadx(method: str, endpoint: str, params=None,
                        timeout: float = JADX_DEFAULT_TIMEOUT, json_body=None):
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        return error_response("timeout must be a positive finite number", "invalid_request", endpoint=endpoint)
    base = JADX_HTTP_BASE
    if _cooling_down(base):
        return error_response("JADX connection is cooling down", "unavailable", retryable=not is_mutation(method, endpoint), endpoint=endpoint)
    url = f"{base}/{endpoint.lstrip('/')}"
    try:
        async with asyncio.timeout(timeout + JADX_CONNECT_TIMEOUT):
            async with httpx.AsyncClient(trust_env=False) as client:
                response = await client.request(method, url, params=params or {},
                                                json=json_body, timeout=_http_timeout(timeout))
        _failures.pop(base, None)
        result = _decode_response(response, endpoint)
        if isinstance(result, dict) and result.get("error") and is_mutation(method, endpoint):
            result["retryable"] = False
        return result
    except (httpx.TimeoutException, TimeoutError):
        return error_response(
            f"Request timed out after {timeout}s; operation may still be running in JADX",
            "timeout", retryable=not is_mutation(method, endpoint), endpoint=endpoint)
    except httpx.ConnectError:
        _record_failure(base)
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
