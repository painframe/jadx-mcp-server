"""Per-event-loop, per-backend bounded readers and exclusive mutations."""

import asyncio
import weakref

MAX_BACKENDS = 128
MAX_PENDING = 64
MAX_READERS = 16
_gates = weakref.WeakKeyDictionary()


class Gate:
    def __init__(self):
        self.condition = asyncio.Condition()
        self.readers = 0
        self.writer = False
        self.waiting_writers = 0
        self.pending = 0

    async def acquire(self, write: bool) -> bool:
        async with self.condition:
            if self.pending >= MAX_PENDING:
                return False
            self.pending += 1
            self.waiting_writers += int(write)
            try:
                await self.condition.wait_for(lambda: not self.writer and (
                    self.readers == 0 if write else self.readers < MAX_READERS and self.waiting_writers == 0))
                if write:
                    self.writer = True
                else:
                    self.readers += 1
                return True
            finally:
                self.pending -= 1
                self.waiting_writers -= int(write)
                self.condition.notify_all()

    async def release(self, write: bool):
        async with self.condition:
            if write:
                self.writer = False
            else:
                self.readers -= 1
            self.condition.notify_all()


def gate_for(base: str) -> Gate | None:
    loop = asyncio.get_running_loop()
    gates = _gates.setdefault(loop, {})
    if base not in gates:
        if len(gates) >= MAX_BACKENDS:
            inactive = next((key for key, gate in gates.items()
                             if not gate.pending and not gate.readers and not gate.writer), None)
            if inactive is None:
                return None
            del gates[inactive]
        gates[base] = Gate()
    return gates[base]
