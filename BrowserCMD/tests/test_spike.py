import asyncio
import base64
import json
from pathlib import Path

import pytest
import websockets

from browsercmd.cdp import CDPError
from browsercmd.spike import MAX_CAPTURE_BYTES, _decode_payload, _page_snapshot, capture_page


def test_screencast_payload_requires_bounded_jpeg_data():
    encoded = base64.b64encode(b"\xff\xd8\xffjpeg-data").decode("ascii")
    assert _decode_payload(encoded, "screencast frame", b"\xff\xd8\xff") == b"\xff\xd8\xffjpeg-data"
    with pytest.raises(CDPError):
        _decode_payload("not-base64", "screencast frame", b"\xff\xd8\xff")
    with pytest.raises(CDPError):
        _decode_payload("YQ==", "screencast frame", b"\xff\xd8\xff")
    with pytest.raises(CDPError):
        _decode_payload("A" * (MAX_CAPTURE_BYTES * 2 + 1), "screencast frame", b"\xff\xd8\xff")


def test_page_snapshot_requires_bounded_value_shape():
    class FakeCDP:
        async def command(self, *_args, **_kwargs):
            return {"result": {"value": {"title": "Example", "runs": []}}}

    snapshot = asyncio.run(_page_snapshot(FakeCDP(), 1))
    assert snapshot["title"] == "Example"


def test_page_snapshot_rejects_javascript_exception():
    class FakeCDP:
        async def command(self, *_args, **_kwargs):
            return {"exceptionDetails": {"text": "failed"}}

    with pytest.raises(CDPError):
        asyncio.run(_page_snapshot(FakeCDP(), 1))


def test_capture_pipeline_writes_all_diagnostic_artifacts(monkeypatch, tmp_path: Path):
    jpeg = b"\xff\xd8\xfffake-jpeg"
    png = b"\x89PNG\r\n\x1a\nfake-png"
    commands = []

    class FakeBrowser:
        browser_name = "Edge"
        protocol_version = "1.3"
        page_websocket = "ws://127.0.0.1:9222/devtools/page/test"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class FakeCDP:
        frame_count = 1

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def command(self, method, _params=None, **_kwargs):
            commands.append(method)
            if method == "Page.captureScreenshot":
                return {"data": base64.b64encode(png).decode("ascii")}
            if method == "Runtime.evaluate":
                if _params["expression"] == "document.readyState":
                    return {"result": {"value": "complete"}}
                return {"result": {"value": {"title": "Example", "runs": []}}}
            return {}

        async def wait_for_event(self, method, **_kwargs):
            assert method == "Page.screencastFrame"
            return {"params": {"data": base64.b64encode(jpeg).decode("ascii")}}

        def clear_events(self):
            commands.append("clear_events")

        def reset_frame_count(self):
            self.frame_count = 0

    async def connect(_uri):
        return FakeCDP()

    monkeypatch.setattr("browsercmd.spike.BrowserSession", FakeBrowser)
    monkeypatch.setattr("browsercmd.spike.CDPConnection.connect", connect)
    report = asyncio.run(capture_page("https://example.com", tmp_path, sample_seconds=0))

    assert Path(report["page_png"]).read_bytes() == png
    assert Path(report["screencast_jpeg"]).read_bytes() == jpeg
    snapshot = json.loads(Path(report["snapshot_json"]).read_text(encoding="utf-8"))
    assert snapshot["title"] == "Example"
    assert "Page.navigate" in commands
    assert "Page.stopScreencast" in commands
    assert "clear_events" in commands
    assert "Page.stopScreencast" in commands


def test_capture_pipeline_over_real_local_websocket(monkeypatch, tmp_path: Path):
    async def scenario():
        jpeg = b"\xff\xd8\xfflocal-jpeg"
        png = b"\x89PNG\r\n\x1a\nlocal-png"
        commands = []

        async def cdp_handler(websocket):
            streaming = False

            async def emit_frame():
                await websocket.send(json.dumps({
                    "method": "Page.screencastFrame",
                    "params": {"sessionId": len(commands), "data": base64.b64encode(jpeg).decode("ascii")},
                }))

            async for raw in websocket:
                message = json.loads(raw)
                method = message["method"]
                commands.append(method)
                params = message.get("params", {})
                if method == "Runtime.evaluate" and params.get("expression") == "document.readyState":
                    result = {"result": {"value": "complete"}}
                elif method == "Runtime.evaluate":
                    result = {"result": {"value": {"title": "Local", "runs": []}}}
                elif method == "Page.captureScreenshot":
                    result = {"data": base64.b64encode(png).decode("ascii")}
                else:
                    result = {}
                await websocket.send(json.dumps({"id": message["id"], "result": result}))
                if method == "Page.startScreencast":
                    streaming = True
                    await emit_frame()
                elif method == "Page.stopScreencast":
                    streaming = False
                elif method == "Page.screencastFrameAck" and streaming:
                    await asyncio.sleep(0.005)
                    await emit_frame()

        async with websockets.serve(cdp_handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]

            class FakeBrowser:
                browser_name = "Fake"
                protocol_version = "1.3"
                page_websocket = f"ws://127.0.0.1:{port}/devtools/page/fake"

                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    return None

            monkeypatch.setattr("browsercmd.spike.BrowserSession", FakeBrowser)
            report = await capture_page(
                "https://example.com", tmp_path, sample_seconds=0.05
            )

        assert Path(report["page_png"]).read_bytes() == png
        assert Path(report["screencast_jpeg"]).read_bytes() == jpeg
        snapshot = json.loads(Path(report["snapshot_json"]).read_text(encoding="utf-8"))
        assert snapshot["title"] == "Local"
        assert "Page.screencastFrameAck" in commands
        assert "Page.stopScreencast" in commands
        assert report["screencast_frame_count"] >= 2
        assert report["frame_sample_elapsed_seconds"] > 0
        assert report["observed_frame_event_rate_hz"] > 0

    asyncio.run(scenario())