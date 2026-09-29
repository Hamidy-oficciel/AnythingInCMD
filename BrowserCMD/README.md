# BrowserCMD

BrowserCMD is a Windows-first terminal browser project. The current M0 release
is a development scaffold only: it can build and run a native C++17 hello
renderer and Python smoke tests, but it does not launch a browser or render web
pages yet.

## M0 Scaffold

- `native/build.py` builds a small native renderer with source-hash reuse.
- `renderer --selftest` runs a noninteractive build smoke test.
- The Python package starts and reports that browser functionality is not yet
  implemented.
- CI is configured for Windows and Ubuntu.

Browser navigation, terminal rendering, and the product features in the
roadmap are not available in this milestone.

## Development Checks

Requires Python 3.10 or newer and a C++17 compiler (`cl`/MSVC or `g++`). On
Windows, use `py -3` in place of `python` if needed.

```sh
python -m pip install -e ".[test]"
python native/build.py
python bin/renderer --selftest
python -m pytest
```

On Windows the executable is `bin/renderer.exe`.

On Windows, `BrowserCMD.bat [url]` creates a venv, installs the currently empty
runtime requirements, builds the renderer, and starts the scaffold engine. It
does not open the supplied URL because browser support is not implemented.

## Verification

**VERIFIED on Ubuntu with Python 3.14.2 and `g++`:** `python native/build.py`
built the renderer, `bin/renderer --selftest` printed
`BrowserCMD renderer self-test: OK`, and `python -m pytest` reported `3 passed`.

**NOT VERIFIED:** Windows launcher, MSVC build, and Windows terminal behavior;
this workspace is Linux. The Windows CI job is configured but has not been run
from this workspace.

The milestone plan is in [docs/PLAN.md](docs/PLAN.md), wire format in
[docs/PROTOCOL.md](docs/PROTOCOL.md), and implementation choices in
[docs/DECISIONS.md](docs/DECISIONS.md).
# BrowserCMD

BrowserCMD is the browser-based companion concept to YouTubeCMD. It keeps the
same simple workflow: provide a YouTube link, choose a source quality, and
watch the video. Instead of drawing frames as terminal characters, BrowserCMD
shows the actual video in a browser player.

## Concept

- A lightweight local app opens a browser page for playback.
- The page accepts a YouTube URL and offers 360p, 480p, 720p, 1080p, or best
  available quality.
- Video is displayed at its real frame dimensions and adapts when the browser
  window changes size.
- One browser media timeline handles picture and sound together, with play,
  pause, seek, volume, and fullscreen controls.
- Clear status and error messages cover invalid URLs, unavailable formats, and
  missing playback dependencies.

## Proposed Architecture

- A small local Python service validates links and uses `yt-dlp` to inspect
  available streams.
- The browser provides the player UI and native video rendering.
- The local service supplies a browser-playable media stream. If the selected
  YouTube format separates audio and video, the service must mux or synchronize
  them before playback rather than treating them as unrelated players.
- The service listens on localhost and is started and stopped with the app.

## Relationship to YouTubeCMD

YouTubeCMD is the terminal-first player and remains its own project. BrowserCMD
is a separate browser-first direction for users who want full video pixels,
standard browser controls, and synchronized audio without terminal rendering.

This folder currently documents the concept; it does not yet contain a working
browser player.
