import asyncio
import unittest
from unittest.mock import patch

from src.server import scheduling


class SchedulingTests(unittest.IsolatedAsyncioTestCase):
    async def test_mutation_waits_for_reads_and_blocks_new_reads(self):
        gate = scheduling.Gate()
        self.assertTrue(await gate.acquire(False))
        writer = asyncio.create_task(gate.acquire(True))
        await asyncio.sleep(0)
        reader = asyncio.create_task(gate.acquire(False))
        await asyncio.sleep(0)
        self.assertFalse(writer.done())
        await gate.release(False)
        self.assertTrue(await writer)
        self.assertFalse(reader.done())
        await gate.release(True)
        self.assertTrue(await reader)
        await gate.release(False)

    async def test_cancelled_waiter_and_saturation_leave_gate_usable(self):
        gate = scheduling.Gate()
        await gate.acquire(True)
        waiting = asyncio.create_task(gate.acquire(False))
        await asyncio.sleep(0)
        with patch.object(scheduling, 'MAX_PENDING', 1):
            self.assertFalse(await gate.acquire(False))
        waiting.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiting
        self.assertEqual(gate.pending, 0)
        await gate.release(True)
        self.assertTrue(await gate.acquire(False))
        await gate.release(False)

    async def test_backends_are_independent(self):
        first = scheduling.gate_for('one')
        second = scheduling.gate_for('two')
        await first.acquire(True)
        self.assertTrue(await second.acquire(False))
        await first.release(True)
        await second.release(False)

    async def test_progress_bypasses_writer_waiting_behind_search(self):
        import httpx

        from src.server import config
        active = asyncio.Event()
        finish = asyncio.Event()
        async def handler(request):
            if request.url.path == '/search':
                active.set()
                await finish.wait()
            return httpx.Response(200, json={'state': 'running'})
        real_client = httpx.AsyncClient
        with patch.object(config.httpx, 'AsyncClient', side_effect=lambda **kw: real_client(
                transport=httpx.MockTransport(handler), **kw)):
            search = asyncio.create_task(config.get_from_jadx('search'))
            await active.wait()
            writer = asyncio.create_task(config.get_from_jadx('rename-class'))
            await asyncio.sleep(0)
            progress = await asyncio.wait_for(config.get_search_progress(), .5)
            self.assertEqual(progress['state'], 'running')
            self.assertFalse(writer.done())
            search.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await search
            await asyncio.wait_for(writer, .5)
            gate = scheduling.gate_for(config.JADX_HTTP_BASE)
            self.assertFalse(gate.writer)
            self.assertEqual(gate.readers, 0)
