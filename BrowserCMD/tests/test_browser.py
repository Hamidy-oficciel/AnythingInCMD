import os
from pathlib import Path

import pytest

from browsercmd.browser import (
    BrowserUnavailable,
    BrowserSession,
    REQUIRED_CDP_METHODS,
    _protocol_methods,
    find_browser,
    validate_websocket_endpoint,
)


def test_browser_discovery_prefers_edge_in_path():
    found = find_browser(
        windows=False,
        which=lambda name: {"msedge": "/opt/edge", "chrome": "/opt/chrome"}.get(name),
    )
    assert found == ("Edge", "/opt/edge")


def test_windows_browser_discovery_prefers_installed_edge(tmp_path: Path):
    edge = tmp_path / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    chrome = tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe"
    edge.parent.mkdir(parents=True)
    chrome.parent.mkdir(parents=True)
    edge.touch()
    chrome.touch()
    found = find_browser(
        windows=True,
        which=lambda _name: None,
        environ={"PROGRAMFILES(X86)": str(tmp_path), "PROGRAMFILES": "", "LOCALAPPDATA": ""},
    )
    assert found == ("Edge", str(edge))


@pytest.mark.parametrize(
    "endpoint",
    [
        "ws://127.0.0.1:9222/devtools/page/abc",
        "ws://localhost:9222/devtools/page/abc",
    ],
)
def test_accepts_same_port_loopback_page_endpoint(endpoint):
    assert validate_websocket_endpoint(endpoint, 9222) == endpoint


@pytest.mark.parametrize(
    "endpoint",
    [
        "ws://192.168.1.2:9222/devtools/page/abc",
        "ws://127.0.0.1:9223/devtools/page/abc",
        "ws://127.0.0.1:9222/devtools/browser/abc",
        "http://127.0.0.1:9222/devtools/page/abc",
    ],
)
def test_rejects_nonlocal_or_wrong_cdp_endpoint(endpoint):
    with pytest.raises(BrowserUnavailable):
        validate_websocket_endpoint(endpoint, 9222)


def test_protocol_checker_uses_cdp_schema_method_names():
    schema = {
        "domains": [
            {"domain": method.split(".")[0], "commands": [{"name": method.split(".")[1]}]}
            for method in REQUIRED_CDP_METHODS
        ]
    }
    assert _protocol_methods(schema) == REQUIRED_CDP_METHODS


def test_devtools_http_requests_use_direct_loopback_without_proxy(monkeypatch):
    observed = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, limit):
            observed["limit"] = limit
            return b'{"ok":true}'

    class FakeConnection:
        def __init__(self, host, port, timeout):
            observed.update(host=host, port=port, timeout=timeout)

        def request(self, method, path):
            observed.update(method=method, path=path)

        def getresponse(self):
            return FakeResponse()

        def close(self):
            observed["closed"] = True

    monkeypatch.setattr("browsercmd.browser.HTTPConnection", FakeConnection)
    session = BrowserSession()
    session.port = 9333
    assert session._get_json("/json/protocol") == {"ok": True}
    assert observed == {
        "host": "127.0.0.1",
        "port": 9333,
        "timeout": 3,
        "method": "GET",
        "path": "/json/protocol",
        "limit": 32 * 1024 * 1024 + 1,
        "closed": True,
    }


@pytest.mark.skipif(os.name == "nt", reason="fake browser fixture uses a POSIX executable")
def test_browser_session_validates_live_protocol_and_cleans_temp_profile(monkeypatch, tmp_path):
    executable = tmp_path / "fake browser"
    executable.write_text(
        """#!/usr/bin/env python3
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

profile = Path(next(arg.split('=', 1)[1] for arg in sys.argv if arg.startswith('--user-data-dir=')))
methods = """ + repr(sorted(REQUIRED_CDP_METHODS)) + """
domains = {}
for method in methods:
    domain, command = method.split('.', 1)
    domains.setdefault(domain, []).append({'name': command})
protocol = json.dumps({'domains': [{'domain': name, 'commands': commands}
                                   for name, commands in domains.items()]}).encode()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/json/protocol':
            payload = protocol
        elif self.path == '/json/version':
            payload = json.dumps({'Protocol-Version': '1.3'}).encode()
        elif self.path == '/json/list':
            payload = json.dumps([{'type': 'page', 'webSocketDebuggerUrl':
                f'ws://127.0.0.1:{server.server_port}/devtools/page/fake'}]).encode()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
    def log_message(self, *_args):
        pass

server = HTTPServer(('127.0.0.1', 0), Handler)
(profile / 'DevToolsActivePort').write_text(
    str(server.server_port) + '\\n/devtools/browser/fake\\n', encoding='ascii')
server.serve_forever()
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setattr("browsercmd.browser.find_browser", lambda: ("Fake", str(executable)))

    with BrowserSession(startup_timeout=5) as session:
        assert session.browser_name == "Fake"
        assert session.protocol_version == "1.3"
        assert session.page_websocket.endswith("/devtools/page/fake")
        profile = Path(session._profile.name)
        assert profile.is_dir()

    assert not profile.exists()