import asyncio
import hashlib
import json
import unittest
import zipfile
from pathlib import Path

from fastmcp import Client

import jadx_mcp_server

FIXTURES = Path(__file__).parent / 'fixtures'
# Freeze baseline membership independently: editing a manifest must not weaken coverage.
BASELINE_ARCHIVES = {'jadx-test-library-1.0.0.jar', 'jadx-test-app-1.0.0.apk'}
BASELINE_TOOLS = {
    'fetch_current_class', 'get_selected_text', 'get_method_by_name',
    'get_all_classes', 'get_class_source', 'search_method_by_name',
    'get_methods_of_class', 'search_classes_by_keyword', 'get_fields_of_class',
    'get_smali_of_class', 'get_manifest_component', 'get_android_manifest',
    'get_strings', 'get_all_resource_file_names', 'get_resource_file',
    'get_main_application_classes_names', 'get_main_application_classes_code',
    'get_main_activity_class', 'get_package_tree', 'get_cache_stats', 'clear_cache',
    'rename_class', 'rename_method', 'rename_field', 'rename_package',
    'rename_variable', 'add_comment', 'list_comments', 'debug_get_stack_frames',
    'debug_get_threads', 'debug_get_variables', 'get_xrefs_to_class',
    'get_xrefs_to_method', 'get_xrefs_to_field',
}


class FixtureContracts(unittest.TestCase):
    def test_donor_archives_are_intact(self):
        checksums = json.loads((FIXTURES / 'checksums.json').read_text())
        self.assertEqual(set(checksums), BASELINE_ARCHIVES)
        for name, digest in checksums.items():
            archive = FIXTURES / name
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), digest)
            with zipfile.ZipFile(archive) as opened:
                self.assertIsNone(opened.testzip())
                expected = 'classes.dex' if name.endswith('.apk') else 'com/jadxtest/library/Calculator.class'
                self.assertIn(expected, opened.namelist())

    def test_existing_tools_remain_registered(self):
        async def listed():
            async with Client(jadx_mcp_server.mcp) as client:
                return {tool.name for tool in await client.list_tools()}
        expected = set(json.loads((FIXTURES / 'baseline-tools.json').read_text()))
        self.assertEqual(expected, BASELINE_TOOLS)
        self.assertLessEqual(BASELINE_TOOLS, asyncio.run(listed()))
