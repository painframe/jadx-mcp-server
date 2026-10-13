import unittest
from unittest.mock import AsyncMock, patch

from fastmcp import Client

import jadx_mcp_server
from src.server.tools import search_tools


class AnalysisToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_regex_reaches_backend_without_case_corruption(self):
        fetch = AsyncMock(return_value={'classes': ['example.Match'], 'search_options': {'regex': True, 'case_sensitive': True}})
        with patch.object(search_tools, '_get_from_jadx_search', fetch):
            async with Client(jadx_mcp_server.mcp) as client:
                result = await client.call_tool('search_classes_by_keyword', {
                    'search_term': r'\S+[A-Z]', 'regex': True, 'case_sensitive': True})
        self.assertFalse(result.is_error)
        self.assertEqual(fetch.await_args.args[1]['search_term'], r'\S+[A-Z]')
        self.assertEqual(fetch.await_args.args[1]['regex'], 'true')
        self.assertEqual(fetch.await_args.args[1]['case_sensitive'], 'true')

    async def test_search_defaults_keep_literal_insensitive_behavior(self):
        fetch = AsyncMock(return_value={'classes': []})
        with patch.object(search_tools, '_get_from_jadx_search', fetch):
            await search_tools.search_classes_by_keyword('literal')
        self.assertEqual(fetch.await_args.args[1]['regex'], 'false')
        self.assertEqual(fetch.await_args.args[1]['case_sensitive'], 'false')

    async def test_old_plugin_cannot_silently_ignore_requested_options(self):
        fetch = AsyncMock(return_value={'classes': ['incorrect.Match']})
        with patch.object(search_tools, '_get_from_jadx_search', fetch):
            result = await search_tools.search_classes_by_keyword('.*', regex=True)
        self.assertEqual(result['code'], 'unsupported_capability')

    async def test_requested_options_reject_bare_list_success(self):
        with patch.object(search_tools, '_get_from_jadx_search', AsyncMock(return_value=['wrong.Class'])):
            result = await search_tools.search_classes_by_keyword('.*', regex=True)
        self.assertEqual(result['code'], 'unsupported_capability')
    async def test_metadata_tools_forward_overload_descriptor(self):
        from src.server.tools import class_tools
        fetch = AsyncMock(return_value={'methods': [{'descriptor': '(I)V'}]})
        with patch.object(class_tools, 'get_from_jadx', fetch):
            async with Client(jadx_mcp_server.mcp) as client:
                await client.call_tool('get_class_info', {'class_name': 'example.Class'})
                self.assertEqual(fetch.await_args.args, ('class-info', {'class_name': 'example.Class'}))
                await client.call_tool('get_method_signature', {'class_name': 'example.Class',
                    'method_name': 'run', 'method_signature': '(I)V'})
        self.assertEqual(fetch.await_args.args, ('method-signature', {
            'class_name': 'example.Class', 'method_name': 'run', 'method_signature': '(I)V'}))
