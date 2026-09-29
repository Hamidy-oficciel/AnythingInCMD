import asyncio
import json

from browsercmd.cdp import CDPConnection


class FakeWebSocket:
    def __init__(self, fail_ack=False):
        self.incoming = asyncio.Queue()
        self.acknowledged = asyncio.Event()
        self.closed = False
        self.fail_ack = fail_ack

    async def send(self, raw):
        message = json.loads(raw)
        if message["method"] == "Page.screencastFrameAck":
            self.acknowledged.set()
            if self.fail_ack:
                await self.incoming.put(
                    json.dumps({"id": message["id"], "error": {"message": "ack failed"}})
                )
                return
        await self.incoming.put(json.dumps({"id": message["id"], "result": {"ok": True}}))

    async def __aiter__(self):
        while True:
            message = await self.incoming.get()
            if message is None:
                return
            yield message

    async def close(self):
        self.closed = True
        await self.incoming.put(None)

    async def emit(self, message):
        await self.incoming.put(json.dumps(message))


def test_cdp_command_and_screencast_ack():
    async def scenario():
        socket = FakeWebSocket()
        connection = CDPConnection(socket)
        try:
            assert await connection.command("Runtime.enable") == {"ok": True}
            await socket.emit(
                {
                    "method": "Page.screencastFrame",
                    "params": {"sessionId": 7, "data": "jpeg"},
                }
            )
            event = await connection.wait_for_event("Page.screencastFrame")
            await asyncio.wait_for(socket.acknowledged.wait(), timeout=1)
            assert event["params"]["sessionId"] == 7
            assert connection.frame_count == 1
        finally:
            await connection.close()
        assert socket.closed

    asyncio.run(scenario())


def test_cdp_surfaces_screencast_ack_failure():
    async def scenario():
        socket = FakeWebSocket(fail_ack=True)
        connection = CDPConnection(socket)
        await socket.emit(
            {"method": "Page.screencastFrame", "params": {"sessionId": 9}}
        )
        await asyncio.wait_for(socket.acknowledged.wait(), timeout=1)
        deadline = asyncio.get_running_loop().time() + 1
        while connection._reader_error is None and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.01)
        try:
            await connection.command("Runtime.enable")
        except Exception as error:
            assert "ack failed" in str(error)
        else:
            raise AssertionError("connection accepted a command after ack failure")
        try:
            await connection.next_event(timeout=0.1)
        except Exception as error:
            assert "ack failed" in str(error)
        else:
            raise AssertionError("acknowledgment failure was not surfaced")
        await connection.close()

    asyncio.run(scenario())