import asyncio

import pytest

from browsercmd.security import UrlError
from browsercmd.cdp import CDPError
from browsercmd.terminal import (
    MAX_RENDER_LINES,
    MAX_PAGE_LINKS,
    TerminalBrowserError,
    format_page,
    page_payload,
    resolve_user_input,
    search_url,
)


def test_resolves_queries_to_duckduckgo_and_domain_inputs_to_https():
    assert resolve_user_input("cats and dogs") == search_url("cats and dogs")
    assert resolve_user_input("example.org/path") == "https://example.org/path"
    assert resolve_user_input("localhost:8080") == "https://localhost:8080"


def test_rejects_dangerous_explicit_scheme_instead_of_searching_it():
    with pytest.raises(UrlError):
        resolve_user_input("javascript:alert(1)")


def test_search_query_has_a_strict_size_limit():
    with pytest.raises(UrlError):
        search_url("x" * 513)


def test_page_payload_sanitizes_terminal_controls_and_bounds_links():
    payload = {
        "result": {
            "value": {
                "title": "Hi\x1b]0;owned\x07",
                "url": "https://example.org/",
                "text": "first\nsecond\x1b[2J",
                "links": [{"text": "go", "href": "https://example.org/go"}],
                "scrollY": -5,
                "scrollHeight": 300,
            }
        }
    }
    page = page_payload(payload)
    assert page["title"] == "Hi"
    assert page["text"] == "first\nsecond"
    assert page["scrollY"] == 0
    assert page["links"][0]["text"] == "go"

    payload["result"]["value"]["links"] = [{}] * (MAX_PAGE_LINKS + 1)
    with pytest.raises(TerminalBrowserError):
        page_payload(payload)


def test_page_formatter_wraps_readable_text_and_preserves_paragraphs():
    page = {"title": "Example", "url": "https://example.org", "text": "one two three four\n\nend"}
    rendered = format_page(page, 40)
    assert "Example\nhttps://example.org" in rendered
    assert "one two three four\n\nend" in rendered


def test_navigation_waits_for_document_before_reading_text():
    from browsercmd.terminal import TerminalBrowser

    class FakeCDP:
        def __init__(self):
            self.ready_states = iter(("context-lost", "loading", "interactive"))
            self.calls = []

        async def command(self, method, params=None, **_kwargs):
            self.calls.append((method, params))
            if method == "Page.navigate":
                return {"frameId": "main"}
            if params["expression"] == "document.readyState":
                state = next(self.ready_states)
                if state == "context-lost":
                    raise CDPError("execution context was replaced")
                return {"result": {"value": state}}
            return {
                "result": {
                    "value": {
                        "title": "Ready",
                        "url": "https://example.org/",
                        "text": "Page is ready",
                        "links": [],
                    }
                }
            }

    async def scenario():
        browser = TerminalBrowser(timeout=1)
        browser._cdp = FakeCDP()
        page = await browser.navigate("https://example.org")
        assert page["text"] == "Page is ready"
        assert sum(
            call[1] is not None and call[1].get("expression") == "document.readyState"
            for call in browser._cdp.calls
        ) == 3

    asyncio.run(scenario())


def test_page_formatter_bounds_rendered_lines():
    page = {"title": "Long", "url": "https://example.org", "text": "\n".join(["line"] * 1000)}
    assert len(format_page(page).splitlines()) <= MAX_RENDER_LINES + 1
