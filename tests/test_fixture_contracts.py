import asyncio
import hashlib
import json
import unittest
import zipfile
from pathlib import Path

from fastmcp import Client

import jadx_mcp_server

FIXTURES = Path(__file__).parent / 'fixtures'


class FixtureContracts(unittest.TestCase):
    def test_donor_archives_are_intact(self):
        for name, digest in json.loads((FIXTURES / 'checksums.json').read_text()).items():
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
        self.assertLessEqual(expected, asyncio.run(listed()))
