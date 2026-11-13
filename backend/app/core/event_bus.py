import asyncio
import json
import logging
from typing import AsyncGenerator, Any

logger = logging.getLogger("aetherpub.event_bus")

class EventBus:
    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    async def subscribe(self) -> AsyncGenerator[str, None]:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        try:
            # Send initial connected ping
            init_msg = json.dumps({"event": "connected", "payload": {"message": "Telemetry stream connected"}})
            yield f"data: {init_msg}\n\n"
            while True:
                data = await q.get()
                yield f"data: {json.dumps(data)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if q in self._subscribers:
                self._subscribers.remove(q)

    async def emit(self, event_type: str, payload: dict[str, Any]):
        message = {"event": event_type, "payload": payload}
        dead_queues = []
        for q in self._subscribers:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                dead_queues.append(q)
            except Exception as e:
                logger.warning(f"Error emitting event to subscriber: {e}")
                dead_queues.append(q)
        for dead in dead_queues:
            if dead in self._subscribers:
                self._subscribers.remove(dead)

event_bus = EventBus()
