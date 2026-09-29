"""M1 browser navigation, screencast, screenshot, and bounded DOM capture."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
import time
from typing import Any

from browsercmd.browser import BrowserSession
from browsercmd.cdp import CDPConnection, CDPError
from browsercmd.snapshot import SNAPSHOT_SCRIPT


MAX_CAPTURE_BYTES = 16 * 1024 * 1024


def _decode_payload(value: Any, label: str, expected_signature: bytes) -> bytes:
    if not isinstance(value, str) or len(value) > MAX_CAPTURE_BYTES * 2:
        raise CDPError(f"Browser returned an invalid or oversized {label}.")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise CDPError(f"Browser returned malformed {label} data.") from error
    if len(decoded) > MAX_CAPTURE_BYTES or not decoded.startswith(expected_signature):
        raise CDPError(f"Browser returned an invalid {label} image.")
    return decoded


async def _page_snapshot(cdp: CDPConnection, timeout: float) -> dict[str, Any]:
    result = await cdp.command(
        "Runtime.evaluate",
        {
            "expression": SNAPSHOT_SCRIPT,
            "returnByValue": True,
            "awaitPromise": False,
        },
        timeout=timeout,
    )
    if "exceptionDetails" in result:
        raise CDPError("The browser could not extract the page text snapshot.")
    remote = result.get("result", {})
    value = remote.get("value") if isinstance(remote, dict) else None
    if not isinstance(value, dict) or not isinstance(value.get("runs"), list):
        raise CDPError("The browser returned an invalid page text snapshot.")
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > 8 * 1024 * 1024:
        raise CDPError("The page text snapshot exceeded its size limit.")
    return value


async def _wait_for_document(cdp: CDPConnection, timeout: float) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        try:
            result = await cdp.command(
                "Runtime.evaluate",
                {"expression": "document.readyState", "returnByValue": True},
                timeout=min(3.0, max(0.1, deadline - asyncio.get_running_loop().time())),
            )
            remote = result.get("result", {})
            state = remote.get("value") if isinstance(remote, dict) else None
            if state in {"interactive", "complete"}:
                return
        except CDPError:
            pass
        await asyncio.sleep(0.1)
    raise CDPError("Timed out waiting for the page to finish loading.")


async def _sample_screencast(
    cdp: CDPConnection,
    first_frame: dict[str, Any],
    sample_seconds: float,
) -> tuple[bytes, int, float]:
    params = first_frame.get("params", {})
    latest_jpeg = _decode_payload(params.get("data"), "screencast frame", b"\xff\xd8\xff")
    if sample_seconds == 0:
        return latest_jpeg, cdp.frame_count, 0.0
    start = time.monotonic()
    deadline = start + sample_seconds
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        try:
            event = await asyncio.wait_for(
                cdp.next_event(timeout=sample_seconds + 1), timeout=remaining
            )
        except asyncio.TimeoutError:
            break
        if event.get("method") != "Page.screencastFrame":
            continue
        params = event.get("params", {})
        latest_jpeg = _decode_payload(
            params.get("data"), "screencast frame", b"\xff\xd8\xff"
        )
    elapsed = time.monotonic() - start
    return latest_jpeg, cdp.frame_count, elapsed


async def capture_page(
    url: str,
    output_dir: Path,
    timeout: float = 30.0,
    sample_seconds: float = 1.0,
) -> dict[str, Any]:
    if not 0 <= sample_seconds <= 10:
        raise ValueError("Frame sample duration must be between 0 and 10 seconds.")
    with BrowserSession() as browser:
        async with await CDPConnection.connect(browser.page_websocket) as cdp:
            await cdp.command("Page.enable")
            await cdp.command("Runtime.enable")
            screencast_started = False
            started_at = time.monotonic()
            try:
                await cdp.command(
                    "Page.startScreencast",
                    {
                        "format": "jpeg",
                        "quality": 65,
                        "maxWidth": 1280,
                        "maxHeight": 900,
                        "everyNthFrame": 1,
                    },
                )
                screencast_started = True
                navigation = await cdp.command(
                    "Page.navigate", {"url": url}, timeout=min(timeout, 20.0)
                )
                if navigation.get("errorText"):
                    raise CDPError(str(navigation["errorText"])[:500])
                await _wait_for_document(cdp, timeout)
                await cdp.command("Page.stopScreencast")
                cdp.clear_events()
                cdp.reset_frame_count()
                await cdp.command(
                    "Page.startScreencast",
                    {
                        "format": "jpeg",
                        "quality": 65,
                        "maxWidth": 1280,
                        "maxHeight": 900,
                        "everyNthFrame": 1,
                    },
                )
                first_frame = await cdp.wait_for_event(
                    "Page.screencastFrame", timeout=min(timeout, 10.0)
                )
                jpeg, sampled_frames, sample_elapsed = await _sample_screencast(
                    cdp, first_frame, sample_seconds
                )

                png_result = await cdp.command(
                    "Page.captureScreenshot",
                    {"format": "png", "fromSurface": True, "captureBeyondViewport": False},
                    timeout=min(timeout, 15.0),
                )
                png = _decode_payload(
                    png_result.get("data"),
                    "PNG screenshot",
                    b"\x89PNG\r\n\x1a\n",
                )
                snapshot = await _page_snapshot(cdp, min(timeout, 15.0))
                elapsed = max(0.001, time.monotonic() - started_at)
                output_dir.mkdir(parents=True, exist_ok=True)
                png_path = output_dir / "page.png"
                jpeg_path = output_dir / "screencast.jpg"
                snapshot_path = output_dir / "snapshot.json"
                png_path.write_bytes(png)
                jpeg_path.write_bytes(jpeg)
                snapshot_path.write_text(
                    json.dumps(snapshot, ensure_ascii=True, indent=2) + "\n",
                    encoding="utf-8",
                )
                return {
                    "browser": browser.browser_name,
                    "protocol_version": browser.protocol_version,
                    "url": url,
                    "page_png": str(png_path),
                    "screencast_jpeg": str(jpeg_path),
                    "snapshot_json": str(snapshot_path),
                    "screencast_frame_count": sampled_frames,
                    "frame_sample_elapsed_seconds": round(sample_elapsed, 3),
                    "capture_elapsed_seconds": round(elapsed, 3),
                    "observed_frame_event_rate_hz": round(
                        sampled_frames / sample_elapsed, 2
                    ) if sample_elapsed > 0 else None,
                    "text_run_count": len(snapshot["runs"]),
                }
            finally:
                if screencast_started:
                    try:
                        await cdp.command("Page.stopScreencast", timeout=3)
                    except CDPError:
                        pass