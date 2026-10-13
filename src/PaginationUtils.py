"""
JADX MCP Server - Pagination Utilities

This module provides a reusable pagination framework for handling large datasets
from JADX API endpoints. Ensures consistent pagination behavior across all tools
with validation, error handling, and standardized response formatting.

Author: Jafar Pathan (zinja-coder@github)
License: See LICENSE file
"""

import logging
from collections.abc import Callable
from typing import Any

from src.server.config import error_response

# Set up logging configuration
logger = logging.getLogger("jadx-mcp-server.pagination")
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
logger.setLevel(logging.ERROR)
logger.propagate = False


class PaginationUtils:
    """
    Utility class for handling pagination across different MCP tools.

    Provides consistent pagination behavior with validation, error handling,
    and standardized response formatting for all JADX API endpoints.
    """

    # Configuration constants
    DEFAULT_PAGE_SIZE = 100
    MAX_PAGE_SIZE = 10000
    MAX_OFFSET = 1000000

    @staticmethod
    def validate_pagination_params(offset: int, count: int) -> tuple[int, int]:
        """
        Validate and normalize pagination parameters.

        Args:
            offset: Requested starting offset (can be negative or excessive)
            count: Requested item count (can be negative or excessive)

        Returns:
            tuple[int, int]: Validated (offset, count) within safe bounds

        Note:
            Clamps values to [0, MAX_OFFSET] and [0, MAX_PAGE_SIZE]
        """
        offset = max(0, min(offset, PaginationUtils.MAX_OFFSET))
        count = max(0, min(count, PaginationUtils.MAX_PAGE_SIZE))
        return offset, count

    @staticmethod
    async def get_paginated_data(
        endpoint: str,
        offset: int = 0,
        count: int = 0,
        additional_params: dict | None = None,
        data_extractor: Callable[[Any], list[Any]] | None = None,
        item_transformer: Callable[[Any], Any] | None = None,
        fetch_function: Callable | None = None
    ) -> dict[str, Any] | str:
        """
        Generic pagination handler for JADX endpoints.

        Args:
            endpoint: The JADX API endpoint to call
            offset: Starting offset for pagination (default: 0)
            count: Number of items to return (default: 0 = all)
            additional_params: Additional query parameters for the endpoint
            data_extractor: Function to extract data list from API response
            item_transformer: Optional function to transform individual items
            fetch_function: Async function to fetch data (typically get_from_jadx)

        Returns:
            Union[Dict[str, Any], str]: Standardized paginated response with metadata

        Response Format:
            {
                "type": "paginated-list",
                "items": [...],
                "pagination": {
                    "total": int,
                    "offset": int,
                    "limit": int,
                    "count": int,
                    "has_more": bool
                }
            }

        Raises:
            Returns error dict on failures with descriptive error messages
        """
        if (type(offset) is not int or type(count) is not int or
                not 0 <= offset <= PaginationUtils.MAX_OFFSET or
                not 0 <= count <= PaginationUtils.MAX_PAGE_SIZE):
            return error_response("offset and count must be integers within pagination bounds",
                                  "invalid_request", status=400, endpoint=endpoint)
        if fetch_function is None:
            return error_response("fetch_function must be provided", endpoint=endpoint)
        params = dict(additional_params or {})
        params["offset"] = offset
        if count > 0:
            params["limit"] = count
        response = await fetch_function(endpoint, params)
        if isinstance(response, list):
            response = {"items": response}
        if not isinstance(response, dict):
            return error_response("Expected an object or list", endpoint=endpoint)
        if response.get("error"):
            return response
        items = data_extractor(response) if data_extractor else next(
            (response[key] for key in ("classes", "methods", "fields", "items") if key in response), [])
        if not isinstance(items, list) or not isinstance(response.get("pagination", {}), dict):
            return error_response("Invalid paginated response", endpoint=endpoint)
        if item_transformer:
            items = [item_transformer(item) for item in items]
        result = PaginationUtils._build_standardized_response(response, items)
        # Keep search completion metadata alongside standardized pagination.
        for key in ("partial", "timed_out", "search_id", "warnings"):
            if key in response:
                result[key] = response[key]
        return result

    @staticmethod
    def _build_standardized_response(parsed_response: dict, items: list[Any]) -> dict:
        """
        Build standardized pagination response.

        Args:
            parsed_response: Raw API response from JADX
            items: Extracted and transformed items list

        Returns:
            dict: Standardized response with pagination metadata

        Note:
            Includes navigation helpers (next_offset, prev_offset, current_page)
            if available in the API response
        """
        pagination_info = parsed_response.get("pagination", {})

        result = {
            "type": parsed_response.get("type", "paginated-list"),
            "items": items,
            "pagination": {
                "total": pagination_info.get("total", len(items)),
                "offset": pagination_info.get("offset", 0),
                "limit": pagination_info.get("limit", 0),
                "count": pagination_info.get("count", len(items)),
                "has_more": pagination_info.get("has_more", False)
            }
        }

        # Add navigation helpers if available
        if "next_offset" in pagination_info:
            result["pagination"]["next_offset"] = pagination_info["next_offset"]
        if "prev_offset" in pagination_info:
            result["pagination"]["prev_offset"] = pagination_info["prev_offset"]
        if "current_page" in pagination_info:
            result["pagination"]["current_page"] = pagination_info["current_page"]
            result["pagination"]["total_pages"] = pagination_info.get("total_pages", 1)
            result["pagination"]["page_size"] = pagination_info.get("page_size", 0)

        return result

    @staticmethod
    def create_page_based_tool(base_func: Callable) -> Callable:
        """
        Decorator to create page-based versions of offset-based functions.

        Args:
            base_func: Async function that uses offset-based pagination

        Returns:
            Callable: Wrapped function that accepts page numbers instead

        Example:
            @create_page_based_tool
            async def get_classes_by_page(page=1, page_size=100):
                # Automatically converts to offset-based call
                pass
        """
        async def page_wrapper(page: int = 1, page_size: int = PaginationUtils.DEFAULT_PAGE_SIZE, **kwargs) -> dict:
            page = max(1, page)
            page_size = max(1, min(page_size, PaginationUtils.MAX_PAGE_SIZE))
            offset = (page - 1) * page_size
            return await base_func(offset=offset, count=page_size, **kwargs)

        return page_wrapper
