"""Full-screen, mouse-clickable terminal browser interface."""

from __future__ import annotations

import asyncio
import re
from typing import Any, Coroutine

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, Layout, ScrollOffsets
from prompt_toolkit.layout.containers import DynamicContainer, HSplit, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Button, Frame, Label, TextArea

from browsercmd.cdp import CDPError
from browsercmd.security import UrlError, sanitize_terminal_text
from browsercmd.terminal import (
    MAX_PAGE_LINKS,
    TerminalBrowser,
    TerminalBrowserError,
    format_page,
    resolve_user_input,
)


HELP_TEXT = (
    "Type a search or URL in the address field. Click Go or press Enter.\n"
    "Page links are clickable in the Links panel. Use the toolbar to navigate.\n"
    "Keyboard: Ctrl+L focuses the address field, Ctrl+R reloads, Ctrl+Q quits."
)


class TerminalBrowserUI:
    def __init__(
        self,
        browser: TerminalBrowser,
        initial_input: str | None = None,
        *,
        input=None,
        output=None,
    ):
        self.browser = browser
        self.status = "Ready"
        self.help_visible = False
        self.links_expanded = False
        self.find_mode = False
        self.find_query = ""
        self._tasks: set[asyncio.Task[Any]] = set()
        self.application: Application | None = None
        self.address = TextArea(
            text=initial_input or "",
            multiline=False,
            wrap_lines=False,
            accept_handler=self._accept_address,
            prompt=" Search or enter URL: ",
            style="class:address",
            focus_on_click=True,
        )
        self.page_window = Window(
            FormattedTextControl(self._page_fragments),
            wrap_lines=True,
            always_hide_cursor=True,
            style="class:page",
            scroll_offsets=ScrollOffsets(top=2, bottom=2),
        )
        self.link_buttons: list[Button] = []
        self._link_panel: HSplit = HSplit([])
        self._rebuild_links_panel()
        self.buttons = self._make_toolbar()
        self.root = self._make_layout()
        application_options = {}
        if input is not None:
            application_options["input"] = input
        if output is not None:
            application_options["output"] = output
        self.application = Application(
            layout=Layout(self.root, focused_element=self.address),
            key_bindings=self._make_key_bindings(),
            style=Style.from_dict({
                "header": "bg:#171a26 #7aa2f7 bold",
                "tab": "bg:#252a3a #c0caf5 bold",
                "toolbar": "bg:#171a26",
                "button": "bg:#252a3a #c0caf5",
                "button.focused": "bg:#7aa2f7 #0f111a bold",
                "address": "bg:#171a26 #c0caf5",
                "page": "bg:#0f111a #c0caf5",
                "page.title": "#7aa2f7 bold",
                "page.url": "#9ece6a",
                "link": "#7aa2f7 underline",
                "status": "bg:#171a26 #e0af68",
                "footer": "bg:#171a26 #9aa5ce",
            }),
            full_screen=True,
            mouse_support=True,
            enable_page_navigation_bindings=True,
            **application_options,
        )

    def _make_toolbar(self) -> list[Button]:
        return [
            Button("< Back", handler=lambda: self._spawn(self._history(-1)), width=10),
            Button("Forward >", handler=lambda: self._spawn(self._history(1)), width=12),
            Button("Reload", handler=lambda: self._spawn(self._reload()), width=10),
            Button("Home", handler=self._home, width=9),
            Button("Links", handler=self._toggle_links, width=9),
            Button("Find", handler=self._begin_find, width=8),
            Button("Scroll up", handler=lambda: self._spawn(self._scroll("up")), width=11),
            Button("Scroll down", handler=lambda: self._spawn(self._scroll("down")), width=13),
            Button("Help", handler=self._toggle_help, width=8),
            Button("Quit", handler=self._quit, width=8),
        ]

    def _make_layout(self) -> HSplit:
        title = Window(
            FormattedTextControl([("class:header", "  BROWSERCMD   Search and browse in your terminal")]),
            height=1,
        )
        tabs = Window(
            FormattedTextControl(lambda: [("class:tab", f"  1  {self.browser.snapshot.get('title', 'Start page')[:48]}  ")]),
            height=1,
        )
        toolbar = HSplit([
            VSplit(self.buttons[:5], padding=1, style="class:toolbar", height=1),
            VSplit(self.buttons[5:], padding=1, style="class:toolbar", height=1),
        ])
        self.go_button = Button("Go", handler=self._accept_address_button, width=8)
        address_row = VSplit(
            [Label(" Search "), self.address, self.go_button],
            padding=1,
            height=1,
        )
        main_content = VSplit(
            [
                Frame(self.page_window, title="Page", style="class:page"),
                DynamicContainer(self._links_panel),
            ],
            padding=1,
        )
        status = Window(
            FormattedTextControl(lambda: [("class:status", f" {self.status} ")]),
            height=1,
        )
        footer = Window(
            FormattedTextControl([("class:footer", " Enter: open  |  Ctrl+L: address  |  Ctrl+R: reload  |  Ctrl+Q: quit ")]),
            height=1,
        )
        return HSplit([title, tabs, toolbar, address_row, main_content, status, footer])

    def _links_panel(self) -> HSplit:
        if self.help_visible:
            return HSplit([
                Frame(Window(FormattedTextControl(HELP_TEXT), wrap_lines=True), title="Help"),
            ])
        return self._link_panel

    def _rebuild_links_panel(self) -> None:
        links = self.browser.snapshot.get("links", [])
        limit = MAX_PAGE_LINKS if self.links_expanded else 8
        self.link_buttons = [
            Button(
                f"{index:>2}  {self._link_label(link)}",
                handler=lambda number=index: self._spawn(self._follow_link(number)),
                width=32,
            )
            for index, link in enumerate(links[:limit], 1)
        ]
        if not self.link_buttons:
            self.link_buttons = [Button("No links yet", width=32)]
        self._link_panel = HSplit(
            [Frame(HSplit(self.link_buttons), title="Links", style="class:page")],
            width=Dimension(preferred=36, min=24, max=42),
        )

    @staticmethod
    def _link_label(link: dict[str, str]) -> str:
        text = link.get("text") or link.get("href", "")
        return sanitize_terminal_text(text.replace("\n", " "), 26)

    def _page_fragments(self) -> list[tuple[str, str]]:
        if self.help_visible:
            return [("", HELP_TEXT)]
        snapshot = self.browser.snapshot
        if not snapshot.get("text") and snapshot.get("url") == "about:blank":
            return [
                ("class:page.title", "\n  Welcome to BrowserCMD\n\n"),
                ("", "  Search the web or enter a website address above.\n\n"),
                ("", "  Search engine: DuckDuckGo\n"),
                ("", "  Click a page link on the right to open it.\n"),
            ]
        formatted = format_page(snapshot)
        if not self.find_query:
            return [("", formatted)]
        fragments: list[tuple[str, str]] = []
        start = 0
        for match in re.finditer(re.escape(self.find_query), formatted, flags=re.IGNORECASE):
            if match.start() > start:
                fragments.append(("", formatted[start:match.start()]))
            fragments.append(("class:find.match", formatted[match.start():match.end()]))
            start = match.end()
        if start < len(formatted):
            fragments.append(("", formatted[start:]))
        return fragments

    def _make_key_bindings(self) -> KeyBindings:
        bindings = KeyBindings()

        @bindings.add("c-q")
        def quit_app(event) -> None:
            self._quit()

        @bindings.add("c-l")
        def focus_address(event) -> None:
            self.application.layout.focus(self.address)
            self.address.buffer.cursor_position = len(self.address.text)

        @bindings.add("c-r")
        def reload_page(event) -> None:
            self._spawn(self._reload())

        @bindings.add("escape")
        def close_help(event) -> None:
            if self.help_visible:
                self.help_visible = False
                self.application.invalidate()

        return bindings

    def _accept_address(self, buffer) -> bool:
        if self.find_mode:
            self._find(buffer.text)
        else:
            self._spawn(self._navigate(buffer.text))
        return True

    def _accept_address_button(self) -> None:
        if self.find_mode:
            self._find(self.address.text)
        else:
            self._spawn(self._navigate(self.address.text))

    def _begin_find(self) -> None:
        self.find_mode = True
        self.address.text = ""
        self.status = "Type text to find, then press Enter or click Go"
        if self.application is not None:
            self.application.layout.focus(self.address)
        self._invalidate()

    def _find(self, value: str) -> None:
        query = value.strip()
        if not query:
            self.status = "Enter text to find"
            self._invalidate()
            return
        self.find_mode = False
        self.find_query = query[:120]
        count = sum(
            len(list(re.finditer(re.escape(self.find_query), line, re.IGNORECASE)))
            for line in self.browser.snapshot.get("text", "").splitlines()
        )
        self.status = f"Found {count} matches" if count else "No matching text on this page"
        self._invalidate()

    async def _navigate(self, value: str) -> None:
        try:
            self.status = "Loading page..."
            self._invalidate()
            snapshot = await self.browser.navigate(resolve_user_input(value))
            self.address.text = snapshot["url"]
            self.status = f"Loaded {snapshot['url']}"
            self.find_query = ""
            self._rebuild_links_panel()
        except (UrlError, CDPError, TerminalBrowserError, OSError, ValueError) as error:
            self.status = sanitize_terminal_text(str(error), 512)
        self._invalidate()

    async def _history(self, offset: int) -> None:
        try:
            self.status = "Loading history..."
            self.browser.snapshot = await self.browser.go_history(offset)
            self.address.text = self.browser.snapshot["url"]
            self.status = "Ready"
            self._rebuild_links_panel()
        except TerminalBrowserError as error:
            self.status = str(error)
        self._invalidate()

    async def _reload(self) -> None:
        try:
            self.status = "Reloading..."
            self.browser.snapshot = await self.browser.reload()
            self.status = "Page reloaded"
            self._rebuild_links_panel()
        except (CDPError, TerminalBrowserError, OSError) as error:
            self.status = sanitize_terminal_text(str(error), 512)
        self._invalidate()

    async def _scroll(self, direction: str) -> None:
        try:
            self.browser.snapshot = await self.browser.scroll(direction)
            self.status = f"Scrolled {direction}"
            self._rebuild_links_panel()
        except (CDPError, TerminalBrowserError, OSError) as error:
            self.status = sanitize_terminal_text(str(error), 512)
        self._invalidate()

    async def _follow_link(self, number: int) -> None:
        try:
            self.status = f"Opening link {number}..."
            self.browser.snapshot = await self.browser.follow_link(number)
            self.address.text = self.browser.snapshot["url"]
            self.status = "Ready"
            self._rebuild_links_panel()
        except (CDPError, TerminalBrowserError, OSError, ValueError) as error:
            self.status = sanitize_terminal_text(str(error), 512)
        self._invalidate()

    def _home(self) -> None:
        self.browser.snapshot = {"title": "Start page", "url": "about:blank", "text": "", "links": []}
        self.address.text = ""
        self.status = "Start page"
        self.help_visible = False
        self.find_mode = False
        self.find_query = ""
        self._rebuild_links_panel()
        self._invalidate()

    def _toggle_links(self) -> None:
        self.links_expanded = not self.links_expanded
        self._rebuild_links_panel()
        self.status = "Showing all links" if self.links_expanded else "Showing first 8 links"
        self._invalidate()

    def _toggle_help(self) -> None:
        self.help_visible = not self.help_visible
        self._invalidate()

    def _quit(self) -> None:
        if self.application is not None:
            self.application.exit()

    def _spawn(self, coroutine: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._task_done)

    def _task_done(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            self.status = sanitize_terminal_text(str(error), 512)
            self._invalidate()

    def _invalidate(self) -> None:
        if self.application is not None:
            self.application.invalidate()

    async def run(self, initial_input: str | None = None) -> None:
        if initial_input:
            await self._navigate(initial_input)
        await self.application.run_async()


async def run_clickable_terminal(
    initial_input: str | None = None, *, timeout: float = 30.0
) -> int:
    try:
        async with TerminalBrowser(timeout=timeout) as browser:
            interface = TerminalBrowserUI(browser, initial_input)
            await interface.run()
        return 0
    except (CDPError, OSError, RuntimeError) as error:
        print(f"BrowserCMD: {sanitize_terminal_text(str(error), 512)}")
        return 1