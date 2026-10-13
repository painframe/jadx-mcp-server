"""Opt-in built-image smoke: JADX_TEST_CONTAINER_IMAGE=... unittest discover."""

import asyncio
import os
import shutil
import unittest

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

IMAGE = os.environ.get('JADX_TEST_CONTAINER_IMAGE')
DOCKER = shutil.which('docker')


@unittest.skipUnless(IMAGE and DOCKER, 'requires explicitly supplied built Docker image')
class ContainerTests(unittest.IsolatedAsyncioTestCase):
    async def test_nonroot_install(self):
        process = await asyncio.create_subprocess_exec(DOCKER, 'run', '--rm', '--entrypoint',
            '/opt/venv/bin/python', IMAGE, '-c', 'import os,jadx_mcp_server; print(os.getuid())',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 30)
            self.assertEqual(process.returncode, 0, stderr.decode())
            self.assertEqual(stdout.decode().strip(), '10001')
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    async def test_stdio_handshake(self):
        transport = StdioTransport(command=DOCKER, args=['run', '--rm', '--init', '-i', IMAGE, '--jadx-port', '9'])
        async with Client(transport) as client:
            tools = await client.list_tools()
            self.assertIn('get_class_info', {tool.name for tool in tools})
            result = await client.call_tool('get_class_info', {'class_name': 'example.Class'})
            self.assertEqual(result.data['code'], 'unavailable')
