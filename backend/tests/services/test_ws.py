import asyncio
import uuid

from app.services.ws import ConnectionManager


class FakeWS:
    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[dict] = []
        self.accepted = False
        self.fail = fail

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        if self.fail:
            raise RuntimeError("dead socket")
        self.sent.append(message)


def test_dispatch_broadcast_reaches_all_connections() -> None:
    async def scenario() -> None:
        m = ConnectionManager()
        m.bind_loop()
        a, b = FakeWS(), FakeWS()
        await m.connect_dispatch(a)  # type: ignore[arg-type]
        await m.connect_dispatch(b)  # type: ignore[arg-type]

        m.notify_dispatch({"type": "order_confirmed", "order_id": "x"})
        await asyncio.sleep(0.05)

        assert a.sent == [{"type": "order_confirmed", "order_id": "x"}]
        assert b.sent == a.sent

    asyncio.run(scenario())


def test_driver_broadcast_is_scoped_to_driver() -> None:
    async def scenario() -> None:
        m = ConnectionManager()
        m.bind_loop()
        d1, d2 = uuid.uuid4(), uuid.uuid4()
        ws1, ws2 = FakeWS(), FakeWS()
        await m.connect_driver(d1, ws1)  # type: ignore[arg-type]
        await m.connect_driver(d2, ws2)  # type: ignore[arg-type]

        m.notify_driver(d1, {"type": "route_assigned"})
        await asyncio.sleep(0.05)

        assert ws1.sent == [{"type": "route_assigned"}]
        assert ws2.sent == []

    asyncio.run(scenario())


def test_dead_connections_are_dropped() -> None:
    async def scenario() -> None:
        m = ConnectionManager()
        m.bind_loop()
        good, bad = FakeWS(), FakeWS(fail=True)
        await m.connect_dispatch(good)  # type: ignore[arg-type]
        await m.connect_dispatch(bad)  # type: ignore[arg-type]

        m.notify_dispatch({"n": 1})
        await asyncio.sleep(0.05)

        assert good.sent == [{"n": 1}]
        assert bad not in m._dispatch  # noqa: SLF001

    asyncio.run(scenario())


def test_notify_without_loop_is_a_noop() -> None:
    m = ConnectionManager()
    # never bound - must not raise
    m.notify_dispatch({"x": 1})
    m.notify_driver(uuid.uuid4(), {"x": 1})
