# BrowserCMD

BrowserCMD is a Windows-first text browser. Search, page text, links, navigation,
and scrolling are controlled from the terminal; an installed system browser
runs headless only to load the page. Real-browser terminal browsing has not yet
been verified in this workspace.

## Terminal Browsing

Enter a search query or URL. Search uses DuckDuckGo. Page text is wrapped for
the terminal, and page links can be listed and followed by number. The supported
commands are `:links`, `:go NUMBER`, `:back`, `:forward`, `:reload`,
`:scroll up|down`, `:find WORDS`, `:help`, and `:quit`.

The browser is selected Edge-first, launched headless with a temporary profile,
and controlled over loopback CDP. No browser binary is bundled. This is a
text-first terminal UI; pixel rendering and the remaining roadmap features are
not implemented yet.

## Run

Requires Python 3.10+ and an installed Edge, Chrome, Chromium, or Brave.

```sh
python -m pip install -e ".[test]"
python -m browsercmd.cli "cats and dogs"
python -m browsercmd.cli https://example.org
python -m browsercmd.cli --capture https://example.org
python -m pytest
```

On Windows, `BrowserCMD.bat [query or URL]` creates the venv, installs the
bounded runtime dependency, builds the native self-test program, and starts the
terminal session. To save diagnostic PNG/JPEG/JSON files and exit, pass
`--capture URL`; files go to `artifacts/m1/` by default and `--output-dir`
changes the location.

## Verification

**VERIFIED in this Linux workspace:** Python 3.14.2; the suite covers URL policy,
DuckDuckGo search resolution, terminal formatting/commands, local WebSocket CDP
transport, frame acknowledgment, browser discovery, and temporary-profile
cleanup using a fake browser. Running the CLI against the real environment
reports that no supported browser is installed.

**NOT VERIFIED:** real Edge/Chrome page navigation, search-result use, Windows
launcher behavior, or page text from a real browser. The terminal workflow is
implemented but needs that Windows run before it can be claimed as working.

See [docs/PLAN.md](docs/PLAN.md) for milestone status,
[docs/PROTOCOL.md](docs/PROTOCOL.md) for the future engine/renderer wire format,
and [docs/DECISIONS.md](docs/DECISIONS.md) for implementation choices.
