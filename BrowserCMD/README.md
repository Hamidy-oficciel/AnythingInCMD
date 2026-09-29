# BrowserCMD

BrowserCMD is a Windows-first terminal browser project. The M1 browser-capture
path is implemented but has not yet been verified against a real browser in
this workspace. It does not render pages in the terminal yet.

## M1 Capture Spike

The engine code normalizes and restricts top-level URLs, discovers installed
Edge, Chrome, Chromium, or Brave, starts the browser headless with a temporary
profile and loopback-only CDP, checks required CDP methods against
`/json/protocol`, and attempts to capture a PNG, screencast JPEG, and bounded DOM
text/style JSON. The full capture path still requires verification with an
installed supported browser. No browser binary is bundled.

The native renderer remains an M0 hello/self-test executable; terminal page
rendering and the remaining product features are not implemented yet.

## Run

Requires Python 3.10+ and an installed Edge, Chrome, Chromium, or Brave.

```sh
python -m pip install -e ".[test]"
python -m browsercmd.cli https://example.org
python -m pytest
```

Capture files are written to `artifacts/m1/` by default. Change the output path
with `--output-dir`. On Windows, `BrowserCMD.bat [url]` creates the venv,
installs the bounded runtime dependency, builds the native self-test program,
and runs the capture command. The capture is diagnostic output, not a terminal
browser UI.

## Verification

**VERIFIED in this Linux workspace:** Python 3.14.2; all 41 unit tests pass,
including URL policy, mock CDP command/frame acknowledgment, browser discovery,
loopback endpoint validation, snapshot bounds, and sanitized errors. Running
the actual CLI here reports that no supported browser is installed.

**NOT VERIFIED:** launching a real browser, the three M1 site captures and
measured frame rate, Windows launcher/MSVC behavior, or terminal page rendering.

See [docs/PLAN.md](docs/PLAN.md) for milestone status,
[docs/PROTOCOL.md](docs/PROTOCOL.md) for the future engine/renderer wire format,
and [docs/DECISIONS.md](docs/DECISIONS.md) for implementation choices.
