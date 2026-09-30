# BrowserCMD

BrowserCMD is a Windows-first terminal browser. Its full-screen interface has
clickable navigation buttons, an address/search field, scrollable page text,
and clickable page links. An installed system browser runs headless to load
pages. Real-browser use and Windows mouse input have not yet been verified in
this workspace.

## Terminal Browsing

Type a search query or URL into the address field, then click **Go** or press
Enter. Search uses DuckDuckGo. Use the on-screen **Back**, **Forward**,
**Reload**, **Home**, **Links**, **Find**, **Scroll up**, **Scroll down**,
**Help**, and **Quit** buttons. Click a page link in the Links panel to open it.
Find highlights matching page text. Keyboard shortcuts include Ctrl+L to focus
the address field, Ctrl+R to reload, and Ctrl+Q to quit.

The browser is selected Edge-first, launched headless with a temporary profile,
and controlled over loopback CDP. No browser binary is bundled. This is a
text-first terminal UI; multi-tab browsing and pixel rendering are not
implemented yet.

## Run

Requires Python 3.10+ and an installed Edge, Chrome, Chromium, or Brave.

```bat
BrowserCMD.bat
```

You can also open a search directly with `BrowserCMD.bat "cats and dogs"`, or
open a site with `BrowserCMD.bat https://example.org`. To install development
dependencies and run tests, use `python -m pip install -e ".[test]"` and
`python -m pytest`. Diagnostic screenshots remain available with
`python -m browsercmd.cli --capture https://example.org`; files go to
`artifacts/m1/` by default.

## Verification

**VERIFIED in this Linux workspace:** Python 3.14.2; the suite covers URL policy,
DuckDuckGo search resolution, full-screen TUI construction, mouse-enabled
buttons/link actions, keyboard exit, local WebSocket CDP transport, frame
acknowledgment, browser discovery, and temporary-profile cleanup using a fake
browser.

**NOT VERIFIED:** real Edge/Chrome page navigation and search-result use, or
Windows Terminal/conhost mouse behavior. The interface is implemented but its
real-browser experience still needs a Windows run.

See [docs/PLAN.md](docs/PLAN.md) for milestone status,
[docs/PROTOCOL.md](docs/PROTOCOL.md) for the future engine/renderer wire format,
and [docs/DECISIONS.md](docs/DECISIONS.md) for implementation choices.
