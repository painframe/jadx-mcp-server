"""
JADX MCP Server - Configuration Module

This module manages server configuration, HTTP client setup, and communication
with the JADX Java plugin. Handles connection management, error handling,
and request/response processing.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

import logging
import sys
from typing import Any

import httpx

# Default Configuration
JADX_HOST = "127.0.0.1"
JADX_PORT = 8650
JADX_HTTP_BASE = f"http://{JADX_HOST}:{JADX_PORT}"

# HTTP read timeouts (seconds) for plugin communication
JADX_DEFAULT_TIMEOUT = 60.0
JADX_SEARCH_TIMEOUT = 3600.0

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
            return {**error_response(payload["error"], "http_error", endpoint=endpoint,
                                    status=response.status_code,
                                    retryable=response.status_code >= 500), **payload}
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
    try:
        with httpx.Client(trust_env=False) as client:
            response = client.get(f"{JADX_HTTP_BASE}/health", timeout=JADX_DEFAULT_TIMEOUT)
            if response.is_success:
                return response.text
            return _decode_response(response, "health")
    except httpx.HTTPError:
        return error_response("JADX health check failed", "unavailable", retryable=True,
                              endpoint="health")


async def _request_jadx(method: str, endpoint: str, params=None,
                        timeout: float = JADX_DEFAULT_TIMEOUT, json_body=None):
    url = f"{JADX_HTTP_BASE}/{endpoint.lstrip('/')}"
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.request(method, url, params=params or {},
                                            json=json_body, timeout=timeout)
        return _decode_response(response, endpoint)
    except httpx.TimeoutException:
        return error_response(
            f"Request timed out after {timeout}s; operation may still be running in JADX",
            "timeout", retryable=method == "GET", endpoint=endpoint)
    except httpx.HTTPError:
        return error_response("Cannot communicate with JADX plugin", "unavailable",
                              retryable=method == "GET", endpoint=endpoint)


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
