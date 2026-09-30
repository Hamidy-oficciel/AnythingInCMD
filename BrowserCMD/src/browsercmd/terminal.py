"""Text-first interactive browser controls rendered directly in the terminal."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import textwrap
from typing import Any
from urllib.parse import quote_plus, urlsplit

from browsercmd.browser import BrowserSession
from browsercmd.cdp import CDPConnection, CDPError
from browsercmd.security import UrlError, normalize_url, sanitize_terminal_text


MAX_PAGE_TEXT = 120_000
MAX_PAGE_LINKS = 300
MAX_LINK_TEXT = 240
MAX_RENDER_LINES = 240
SEARCH_BASE_URL = "https://html.duckduckgo.com/html/?q="

PAGE_SCRIPT = r"""(() => {
  const body = document.body;
  const links = Array.from(document.querySelectorAll('a[href]')).slice(0, 300).map(a => ({
    text: (a.innerText || a.getAttribute('aria-label') || '').trim().slice(0, 240),
    href: a.href.slice(0, 8192)
  }));
  return {
    title: document.title.slice(0, 4096),
    url: location.href.slice(0, 8192),
    text: (body ? body.innerText : '').slice(0, 120000),
    links,
    scrollY,
    scrollHeight: document.documentElement.scrollHeight
  };
})()"""


class TerminalBrowserError(RuntimeError):
    """An expected page or browser-control error suitable for terminal display."""


def search_url(query: str) -> str:
    normalized = " ".join(query.split())
    if not normalized:
        raise UrlError("Enter a search query.")
    if len(normalized) > 512:
        raise UrlError("Search query is too long (maximum 512 characters).")
    return SEARCH_BASE_URL + quote_plus(normalized, safe="")


def resolve_user_input(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise UrlError("Enter a URL or search query.")
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", candidate):
        return normalize_url(candidate)
    if any(character.isspace() for character in candidate):
        return search_url(candidate)

    try:
        parsed = urlsplit("https://" + candidate)
        hostname = parsed.hostname or ""
        parsed.port
    except ValueError:
        hostname = ""
    looks_like_host = "." in hostname or hostname.lower() == "localhost"
    if not looks_like_host:
        try:
            ipaddress.ip_address(hostname)
            looks_like_host = True
        except ValueError:
            pass
    return normalize_url(candidate) if looks_like_host else search_url(candidate)


def page_payload(result: dict[str, Any]) -> dict[str, Any]:
    if "exceptionDetails" in result:
        raise TerminalBrowserError("The browser could not read page text.")
    remote = result.get("result", {})
    value = remote.get("value") if isinstance(remote, dict) else None
    if not isinstance(value, dict):
        raise TerminalBrowserError("The browser returned an invalid text page.")
    title = value.get("title", "")
    url = value.get("url", "")
    page_text = value.get("text", "")
    links = value.get("links", [])
    if not all(isinstance(field, str) for field in (title, url, page_text)):
        raise TerminalBrowserError("The browser returned invalid page fields.")
    if len(page_text) > MAX_PAGE_TEXT or len(links) > MAX_PAGE_LINKS:
        raise TerminalBrowserError("The browser exceeded the page text or link limit.")
    if any(not isinstance(link, dict) or not isinstance(link.get("href"), str) or
           not isinstance(link.get("text", ""), str) for link in links):
        raise TerminalBrowserError("The browser returned an invalid page link.")
    return {
        "title": sanitize_terminal_text(title, 512),
        "url": sanitize_terminal_text(url, 2048),
        "text": _sanitize_multiline(page_text),
        "links": [
            {
                "text": sanitize_terminal_text(link.get("text", ""), MAX_LINK_TEXT),
                "href": sanitize_terminal_text(link["href"], 2048),
            }
            for link in links
        ],
        "scrollY": max(0, int(value.get("scrollY", 0) or 0)),
        "scrollHeight": max(0, int(value.get("scrollHeight", 0) or 0)),
    }


def _sanitize_multiline(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in value.split("\n"):
        safe = sanitize_terminal_text(line, MAX_PAGE_TEXT)
        safe = safe.replace("\t", "    ")
        lines.append(safe)
    return "\n".join(lines)[:MAX_PAGE_TEXT]


def format_page(snapshot: dict[str, Any], columns: int = 80) -> str:
    width = max(40, min(160, columns))
    title = snapshot["title"] or "Untitled page"
    url = snapshot["url"]
    output = [title, url, "-" * min(width, 72), ""]
    for source_line in snapshot["text"].splitlines():
        if not source_line:
            output.append("")
            continue
        output.extend(
            textwrap.wrap(
                source_line,
                width=width,
                replace_whitespace=True,
                drop_whitespace=True,
                break_long_words=True,
                break_on_hyphens=False,
            ) or [""]
        )
        if len(output) >= MAX_RENDER_LINES:
            output.append("[Page text truncated. Use :scroll down or :find <text>.]")
            break
    return "\n".join(output)


class TerminalBrowser:
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._browser: BrowserSession | None = None
        self._cdp: CDPConnection | None = None
        self.snapshot: dict[str, Any] = {"title": "Start page", "url": "about:blank", "text": "", "links": []}
        self._history: list[str] = []
        self._history_index = -1

    async def __aenter__(self) -> TerminalBrowser:
        self._browser = BrowserSession()
        self._browser.__enter__()
        try:
            self._cdp = await CDPConnection.connect(self._browser.page_websocket)
            await self._cdp.command("Page.enable")
            await self._cdp.command("Runtime.enable")
            return self
        except Exception:
            self._browser.close()
            self._browser = None
            raise

    async def __aexit__(self, *_exc: object) -> None:
        if self._cdp is not None:
            await self._cdp.close()
            self._cdp = None
        if self._browser is not None:
            self._browser.close()
            self._browser = None

    async def _evaluate(self, expression: str) -> dict[str, Any]:
        if self._cdp is None:
            raise TerminalBrowserError("Browser connection is closed.")
        result = await self._cdp.command(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": False},
            timeout=min(self.timeout, 20.0),
        )
        return result

    async def refresh(self) -> dict[str, Any]:
        result = await self._evaluate(PAGE_SCRIPT)
        self.snapshot = page_payload(result)
        return self.snapshot

    async def _wait_for_document(self) -> None:
        deadline = asyncio.get_running_loop().time() + min(self.timeout, 20.0)
        while asyncio.get_running_loop().time() < deadline:
            try:
                result = await self._evaluate("document.readyState")
            except CDPError:
                await asyncio.sleep(0.1)
                continue
            remote = result.get("result", {})
            state = remote.get("value") if isinstance(remote, dict) else None
            if state in {"interactive", "complete"}:
                return
            await asyncio.sleep(0.1)
        raise TerminalBrowserError("Timed out waiting for the page to finish loading.")

    async def navigate(self, url: str, *, add_history: bool = True) -> dict[str, Any]:
        if self._cdp is None:
            raise TerminalBrowserError("Browser connection is closed.")
        safe_url = normalize_url(url)
        result = await self._cdp.command(
            "Page.navigate", {"url": safe_url}, timeout=min(self.timeout, 20.0)
        )
        if result.get("errorText"):
            raise TerminalBrowserError(sanitize_terminal_text(str(result["errorText"]), 512))
        await self._wait_for_document()
        if add_history:
            del self._history[self._history_index + 1:]
            self._history.append(safe_url)
            self._history_index = len(self._history) - 1
        return await self.refresh()

    async def reload(self) -> dict[str, Any]:
        if self._cdp is None:
            raise TerminalBrowserError("Browser connection is closed.")
        await self._cdp.command("Page.reload", {"ignoreCache": False})
        await self._wait_for_document()
        return await self.refresh()

    async def go_history(self, offset: int) -> dict[str, Any]:
        index = self._history_index + offset
        if not 0 <= index < len(self._history):
            raise TerminalBrowserError("No page in that history direction.")
        self._history_index = index
        return await self.navigate(self._history[index], add_history=False)

    async def follow_link(self, number: int) -> dict[str, Any]:
        if not 1 <= number <= len(self.snapshot["links"]):
            raise TerminalBrowserError("Link number is not on this page.")
        link = self.snapshot["links"][number - 1]
        try:
            url = normalize_url(link["href"])
        except UrlError as error:
            raise TerminalBrowserError(str(error)) from error
        return await self.navigate(url)

    async def scroll(self, direction: str) -> dict[str, Any]:
        amount = "Math.max(200, Math.floor(innerHeight * 0.8))"
        delta = amount if direction == "down" else f"-({amount})"
        await self._evaluate(f"window.scrollBy({{top: {delta}, behavior: 'instant'}})")
        await asyncio.sleep(0.15)
        return await self.refresh()
