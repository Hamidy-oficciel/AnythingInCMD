"""Bounded asyncio WebSocket client for Chrome DevTools Protocol."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any

import websockets


MAX_CDP_MESSAGE_BYTES = 32 * 1024 * 1024
MAX_PENDING_COMMANDS = 64
MAX_QUEUED_EVENTS = 16


class CDPError(RuntimeError):
    """Raised for CDP transport, protocol, or command failures."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CDPError("CDP message contains a duplicate key.")
        result[key] = value
    return result


class CDPConnection:
    def __init__(self, websocket: Any):
        self._websocket = websocket
        self._next_id = 0
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._events: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=MAX_QUEUED_EVENTS
        )
        self._send_lock = asyncio.Lock()
        self._background: set[asyncio.Task[dict[str, Any]]] = set()
        self._reader_error: CDPError | None = None
        self._closed = False
        self.frame_count = 0
        self._reader_task = asyncio.create_task(self._read_messages())

    @classmethod
    async def connect(cls, uri: str) -> CDPConnection:
        try:
            websocket = await websockets.connect(
                uri,
                origin=None,
                max_size=MAX_CDP_MESSAGE_BYTES,
                open_timeout=10,
                close_timeout=2,
                ping_interval=20,
            )
        except (OSError, TimeoutError, websockets.WebSocketException) as error:
            raise CDPError(f"Could not connect to the browser's CDP endpoint: {error}") from error
        return cls(websocket)

    async def command(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        if self._reader_error is not None:
            raise self._reader_error
        if self._closed:
            raise self._reader_error or CDPError("The CDP connection is closed.")
        if len(self._pending) >= MAX_PENDING_COMMANDS:
            raise CDPError("Too many pending CDP commands.")

        self._next_id += 1
        command_id = self._next_id
        future = asyncio.get_running_loop().create_future()
        self._pending[command_id] = future
        message = {"id": command_id, "method": method, "params": params or {}}
        encoded = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_CDP_MESSAGE_BYTES:
            self._pending.pop(command_id, None)
            raise CDPError("CDP command exceeds the message-size limit.")
        try:
            async with self._send_lock:
                await self._websocket.send(encoded)
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError as error:
            raise CDPError(f"Timed out waiting for CDP command {method}.") from error
        except OSError as error:
            raise CDPError(f"Could not send CDP command {method}.") from error
        finally:
            self._pending.pop(command_id, None)

    async def next_event(self, *, timeout: float = 10.0) -> dict[str, Any]:
        if self._reader_error is not None:
            raise self._reader_error
        try:
            return await asyncio.wait_for(self._events.get(), timeout=timeout)
        except asyncio.TimeoutError as error:
            if self._reader_error is not None:
                raise self._reader_error from error
            raise CDPError("Timed out waiting for a browser event.") from error

    async def wait_for_event(
        self, method: str, *, timeout: float = 10.0
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise CDPError(f"Timed out waiting for browser event {method}.")
            event = await self.next_event(timeout=remaining)
            if event.get("method") == method:
                return event

    def clear_events(self) -> None:
        while not self._events.empty():
            with suppress(asyncio.QueueEmpty):
                self._events.get_nowait()

    def reset_frame_count(self) -> None:
        self.frame_count = 0

    @property
    def reader_error(self) -> CDPError | None:
        return self._reader_error

    async def _read_messages(self) -> None:
        try:
            async for raw in self._websocket:
                if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_CDP_MESSAGE_BYTES:
                    raise CDPError("Browser sent an invalid or oversized CDP message.")
                try:
                    message = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
                except (json.JSONDecodeError, CDPError) as error:
                    raise CDPError("Browser sent malformed CDP JSON.") from error
                if not isinstance(message, dict):
                    raise CDPError("Browser sent a non-object CDP message.")
                if isinstance(message.get("id"), int):
                    future = self._pending.get(message["id"])
                    if future is None or future.done():
                        continue
                    if "error" in message:
                        error = message["error"]
                        text = error.get("message", "command failed") if isinstance(error, dict) else "command failed"
                        future.set_exception(CDPError(str(text)[:500]))
                    else:
                        result = message.get("result", {})
                        if not isinstance(result, dict):
                            future.set_exception(CDPError("Browser returned an invalid command result."))
                        else:
                            future.set_result(result)
                    continue
                method = message.get("method")
                params = message.get("params", {})
                if not isinstance(method, str) or not isinstance(params, dict):
                    raise CDPError("Browser sent an invalid CDP event.")
                if method == "Page.screencastFrame":
                    self.frame_count += 1
                    session_id = params.get("sessionId")
                    if isinstance(session_id, int):
                        task = asyncio.create_task(
                            self.command(
                                "Page.screencastFrameAck",
                                {"sessionId": session_id},
                                timeout=5,
                            )
                        )
                        self._background.add(task)
                        task.add_done_callback(self._background_finished)
                self._queue_latest({"method": method, "params": params})
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._reader_error = error if isinstance(error, CDPError) else CDPError(
                f"CDP connection failed: {error}"
            )
        finally:
            self._closed = True
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(self._reader_error or CDPError("CDP connection closed."))

    def _background_finished(self, task: asyncio.Task[dict[str, Any]]) -> None:
        self._background.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None and self._reader_error is None:
            self._reader_error = error if isinstance(error, CDPError) else CDPError(
                f"CDP background command failed: {error}"
            )

    def _queue_latest(self, event: dict[str, Any]) -> None:
        if self._events.full():
            with suppress(asyncio.QueueEmpty):
                self._events.get_nowait()
        self._events.put_nowait(event)

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
        for task in tuple(self._background):
            task.cancel()
        if self._background:
            await asyncio.gather(*self._background, return_exceptions=True)
        with suppress(Exception):
            await self._websocket.close()
        if not self._reader_task.done():
            self._reader_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._reader_task

    async def __aenter__(self) -> CDPConnection:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()