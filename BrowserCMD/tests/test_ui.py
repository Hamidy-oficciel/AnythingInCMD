import asyncio
from types import SimpleNamespace

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.mouse_events import MouseEventType
from prompt_toolkit.output import DummyOutput

from browsercmd.terminal import search_url
from browsercmd.ui import TerminalBrowserUI


class FakeBrowser:
    def __init__(self):
        self.snapshot = {"title": "Start page", "url": "about:blank", "text": "", "links": []}
        self.visited = []

    async def navigate(self, url):
        self.visited.append(url)
        self.snapshot = {
            "title": "Results", "url": url, "text": "Found a result",
            "links": [{"text": "First result", "href": "https://example.org/"}],
        }
        return self.snapshot

    async def follow_link(self, number):
        assert number == 1
        self.snapshot = {
            "title": "Example", "url": "https://example.org/", "text": "Example page", "links": [],
        }
        return self.snapshot

    async def go_history(self, _offset):
        return self.snapshot

    async def reload(self):
        return self.snapshot


def test_full_screen_ui_enables_mouse_and_builds_clickable_toolbar():
    ui = TerminalBrowserUI(FakeBrowser())
    assert ui.application.full_screen
    assert ui.application.mouse_support()
    assert [button.text for button in ui.buttons] == [
        "< Back", "Forward >", "Reload", "Home", "Links", "Find",
        "Scroll up", "Scroll down", "Help", "Quit"
    ]
    assert ui.address.accept_handler is not None


def test_mouse_up_event_invokes_visible_button_handler():
    ui = TerminalBrowserUI(FakeBrowser())
    fragments = ui.buttons[4]._get_text_fragments()
    mouse_handler = next(fragment[2] for fragment in fragments if len(fragment) == 3)
    mouse_handler(SimpleNamespace(event_type=MouseEventType.MOUSE_UP))
    assert ui.links_expanded


def test_find_button_focuses_field_and_highlights_matches():
    ui = TerminalBrowserUI(FakeBrowser())
    ui.browser.snapshot["text"] = "Find this word, then this word again."
    ui.buttons[5].handler()
    assert ui.find_mode
    ui.address.text = "word"
    assert ui._accept_address(ui.address.buffer)
    assert ui.status == "Found 2 matches"
    fragments = ui._page_fragments()
    assert sum(style == "class:find.match" for style, _text in fragments) == 2


def test_scroll_button_calls_scroll_and_refreshes_status():
    async def scenario():
        browser = FakeBrowser()
        directions = []

        async def scroll(direction):
            directions.append(direction)
            return browser.snapshot

        browser.scroll = scroll
        ui = TerminalBrowserUI(browser)
        ui.buttons[6].handler()
        await asyncio.gather(*tuple(ui._tasks))
        assert directions == ["up"]
        assert ui.status == "Scrolled up"

    asyncio.run(scenario())


def test_clickable_link_button_follows_browser_link():
    async def scenario():
        browser = FakeBrowser()
        ui = TerminalBrowserUI(browser)
        browser.snapshot["links"] = [{"text": "First result", "href": "https://example.org/"}]
        ui._rebuild_links_panel()
        ui.link_buttons[0].handler()
        await asyncio.gather(*tuple(ui._tasks))
        assert browser.snapshot["url"] == "https://example.org/"
        assert ui.status == "Ready"

    asyncio.run(scenario())


def test_search_button_and_input_submit_use_duckduckgo():
    async def scenario():
        browser = FakeBrowser()
        ui = TerminalBrowserUI(browser)
        ui.address.text = "cats and dogs"
        ui.go_button.handler()
        await asyncio.gather(*tuple(ui._tasks))
        assert browser.visited == [search_url("cats and dogs")]
        ui.address.text = "birds"
        assert ui._accept_address(ui.address.buffer)
        await asyncio.gather(*tuple(ui._tasks))
        assert browser.visited[-1] == search_url("birds")

    asyncio.run(scenario())


def test_terminal_application_exits_with_ctrl_q():
    async def scenario():
        with create_pipe_input() as terminal_input:
            terminal_input.send_bytes(b"\x11")
            ui = TerminalBrowserUI(
                FakeBrowser(),
                input=terminal_input,
                output=DummyOutput(),
            )
            await ui.application.run_async()

    asyncio.run(scenario())