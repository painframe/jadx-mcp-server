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
