"""System browser discovery and isolated headless process lifecycle."""

from __future__ import annotations

import ctypes
from http.client import HTTPConnection
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from ctypes import wintypes
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import urlsplit


MAX_DEVTOOLS_RESPONSE = 32 * 1024 * 1024
REQUIRED_CDP_METHODS = {
    "Page.enable",
    "Page.navigate",
    "Page.startScreencast",
    "Page.screencastFrameAck",
    "Page.stopScreencast",
    "Page.captureScreenshot",
    "Runtime.enable",
    "Runtime.evaluate",
}

_BROWSER_CANDIDATES = (
    ("Edge", ("msedge", "msedge.exe")),
    ("Chrome", ("chrome", "chrome.exe", "google-chrome", "google-chrome-stable")),
    ("Chromium", ("chromium", "chromium-browser", "chromium.exe")),
    ("Brave", ("brave", "brave.exe", "brave-browser")),
)


class BrowserUnavailable(RuntimeError):
    """Raised when no safe supported browser session can be created."""


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
    )]


class _BasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _WindowsJob:
    _KILL_ON_JOB_CLOSE = 0x00002000

    def __init__(self, process: subprocess.Popen):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32 = kernel32
        self._handle = kernel32.CreateJobObjectW(None, None)
        if not self._handle:
            raise BrowserUnavailable("Could not create a Windows browser process job.")
        limits = _ExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = self._KILL_ON_JOB_CLOSE
        configured = kernel32.SetInformationJobObject(
            self._handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        )
        assigned = configured and kernel32.AssignProcessToJobObject(
            self._handle, wintypes.HANDLE(int(process._handle))
        )
        if not assigned:
            self.close()
            raise BrowserUnavailable(
                "Could not attach the browser to its Windows cleanup job."
            )

    def close(self) -> None:
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


def find_browser(
    *,
    windows: bool | None = None,
    which: Callable[[str], str | None] = shutil.which,
    environ: Mapping[str, str] | None = None,
) -> tuple[str, str] | None:
    is_windows = os.name == "nt" if windows is None else windows
    environment = os.environ if environ is None else environ
    for label, commands in _BROWSER_CANDIDATES:
        for command in commands:
            path = which(command)
            if path:
                return label, path
        if not is_windows:
            continue
        install_dirs = (
            environment.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            environment.get("PROGRAMFILES", r"C:\Program Files"),
            environment.get("LOCALAPPDATA", ""),
        )
        relative_paths = {
            "Edge": (r"Microsoft\Edge\Application\msedge.exe",),
            "Chrome": (r"Google\Chrome\Application\chrome.exe",),
            "Chromium": (r"Chromium\Application\chrome.exe", r"Chromium\chrome.exe"),
            "Brave": (r"BraveSoftware\Brave-Browser\Application\brave.exe",),
        }[label]
        for install_dir in install_dirs:
            if not install_dir:
                continue
            for relative_path in relative_paths:
                candidate = Path(install_dir).joinpath(*relative_path.split("\\"))
                if candidate.is_file():
                    return label, str(candidate)
    return None


def validate_websocket_endpoint(value: str, port: int) -> str:
    try:
        parsed = urlsplit(value)
        endpoint_port = parsed.port
    except ValueError as error:
        raise BrowserUnavailable("The browser returned an invalid CDP endpoint.") from error
    if (
        parsed.scheme != "ws"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or endpoint_port != port
        or not parsed.path.startswith("/devtools/page/")
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise BrowserUnavailable("The browser returned a non-loopback CDP endpoint.")
    return value


def _protocol_methods(protocol: dict) -> set[str]:
    methods: set[str] = set()
    domains = protocol.get("domains")
    if not isinstance(domains, list) or len(domains) > 256:
        raise BrowserUnavailable("The browser returned an invalid CDP protocol schema.")
    for domain in domains:
        if not isinstance(domain, dict):
            continue
        name = domain.get("domain")
        commands = domain.get("commands", [])
        if not isinstance(name, str) or not isinstance(commands, list):
            continue
        for command in commands:
            if isinstance(command, dict) and isinstance(command.get("name"), str):
                methods.add(f"{name}.{command['name']}")
    return methods


class BrowserSession:
    def __init__(self, startup_timeout: float = 15.0):
        self.startup_timeout = startup_timeout
        self.browser_name = ""
        self.browser_path = ""
        self.port = 0
        self.page_websocket = ""
        self.protocol_version = ""
        self._profile: tempfile.TemporaryDirectory | None = None
        self._process: subprocess.Popen | None = None
        self._job: _WindowsJob | None = None

    def __enter__(self) -> BrowserSession:
        found = find_browser()
        if found is None:
            raise BrowserUnavailable(
                "No supported browser found. Install Microsoft Edge, Chrome, Chromium, or Brave."
            )
        self.browser_name, self.browser_path = found
        self._profile = tempfile.TemporaryDirectory(prefix="BrowserCMD-")
        arguments = [
            self.browser_path,
            "--headless=new",
            "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port=0",
            f"--user-data-dir={self._profile.name}",
            "--no-first-run",
            "about:blank",
        ]
        options: dict[str, object] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "shell": False,
            "close_fds": True,
        }
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        else:
            options["start_new_session"] = True
        try:
            self._process = subprocess.Popen(arguments, **options)
            if os.name == "nt":
                self._job = _WindowsJob(self._process)
            self._wait_for_devtools()
            self._load_and_validate_protocol()
            self._find_page_target()
            return self
        except Exception:
            self.close()
            raise

    def _wait_for_devtools(self) -> None:
        assert self._profile is not None and self._process is not None
        active_port = Path(self._profile.name) / "DevToolsActivePort"
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise BrowserUnavailable(f"{self.browser_name} exited during startup.")
            try:
                lines = active_port.read_text(encoding="ascii").splitlines()
                port = int(lines[0])
                if 1 <= port <= 65535:
                    self.port = port
                    return
            except (OSError, ValueError, IndexError):
                pass
            time.sleep(0.05)
        raise BrowserUnavailable(
            f"{self.browser_name} did not publish its DevToolsActivePort in time."
        )

    def _get_json(self, path: str) -> object:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            if response.status != 200:
                raise BrowserUnavailable("The browser rejected a local DevTools request.")
            with response:
                payload = response.read(MAX_DEVTOOLS_RESPONSE + 1)
        except OSError as error:
            raise BrowserUnavailable("Could not read the browser's local DevTools endpoint.") from error
        finally:
            connection.close()
        if len(payload) > MAX_DEVTOOLS_RESPONSE:
            raise BrowserUnavailable("The browser's DevTools response exceeded its size limit.")
        try:
            return json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise BrowserUnavailable("The browser returned malformed DevTools JSON.") from error

    def _load_and_validate_protocol(self) -> None:
        protocol = self._get_json("/json/protocol")
        if not isinstance(protocol, dict):
            raise BrowserUnavailable("The browser returned an invalid CDP protocol schema.")
        methods = _protocol_methods(protocol)
        missing = REQUIRED_CDP_METHODS - methods
        if missing:
            raise BrowserUnavailable(
                "This browser lacks required CDP methods: " + ", ".join(sorted(missing))
            )
        version = self._get_json("/json/version")
        if isinstance(version, dict):
            value = version.get("Protocol-Version", "")
            if isinstance(value, str):
                self.protocol_version = value[:32]

    def _find_page_target(self) -> None:
        targets = self._get_json("/json/list")
        if not isinstance(targets, list) or len(targets) > 128:
            raise BrowserUnavailable("The browser returned an invalid target list.")
        for target in targets:
            if not isinstance(target, dict) or target.get("type") != "page":
                continue
            endpoint = target.get("webSocketDebuggerUrl")
            if isinstance(endpoint, str):
                self.page_websocket = validate_websocket_endpoint(endpoint, self.port)
                return
        raise BrowserUnavailable("The browser did not expose a page target over CDP.")

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is not None and process.poll() is None:
            try:
                if os.name == "nt":
                    process.terminate()
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    if os.name != "nt":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        if self._job is not None:
            self._job.close()
            self._job = None
        if self._profile is not None:
            self._profile.cleanup()
            self._profile = None

    def __exit__(self, *_exc: object) -> None:
        self.close()