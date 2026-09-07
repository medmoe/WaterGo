"""In-memory WebSocket connection manager (section 10).

A single process, a dict of live connections - no pub/sub broker at this scale.
Producers are synchronous service code running in a threadpool worker, so
``notify_*`` is sync and hops back onto the event loop via
``loop.call_soon_threadsafe``. If a client isn't connected the event is simply
dropped; clients also poll as a fallback.
"""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any
from uuid import UUID

from fastapi import WebSocket

logger = logging.getLogger("app.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._dispatch: set[WebSocket] = set()
        self._drivers: dict[UUID, set[WebSocket]] = {}

    def bind_loop(self) -> None:
        """Record the running loop (called from the app lifespan)."""
        self._loop = asyncio.get_running_loop()

    # -- connection bookkeeping (called from the websocket endpoints) --------

    async def connect_dispatch(self, ws: WebSocket) -> None:
        await ws.accept()
        self._dispatch.add(ws)

    def disconnect_dispatch(self, ws: WebSocket) -> None:
        self._dispatch.discard(ws)

    async def connect_driver(self, driver_id: UUID, ws: WebSocket) -> None:
        await ws.accept()
        self._drivers.setdefault(driver_id, set()).add(ws)

    def disconnect_driver(self, driver_id: UUID, ws: WebSocket) -> None:
        conns = self._drivers.get(driver_id)
        if conns:
            conns.discard(ws)
            if not conns:
                self._drivers.pop(driver_id, None)

    # -- producers (sync, safe to call from any thread) ---------------------

    def notify_dispatch(self, message: dict[str, Any]) -> None:
        self._schedule(self._broadcast(self._dispatch, message))

    def notify_driver(self, driver_id: UUID, message: dict[str, Any]) -> None:
        conns = self._drivers.get(driver_id)
        if conns:
            self._schedule(self._broadcast(conns, message))

    # -- internals --------------------------------------------------------

    def _schedule(self, coro: Coroutine[Any, Any, None]) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            coro.close()
            return
        try:
            loop.call_soon_threadsafe(lambda: loop.create_task(coro))
        except RuntimeError:
            # loop stopped between the check and the call
            coro.close()

    async def _broadcast(self, conns: set[WebSocket], message: dict[str, Any]) -> None:
        for ws in list(conns):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - drop dead connections
                conns.discard(ws)


manager = ConnectionManager()
