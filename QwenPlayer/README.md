# QwenPlayer

A simplified, build-free version of YouTubeCMD: watch YouTube videos inside your
terminal (ASCII / half-block / truecolor ANSI), written entirely in Python.

**No C++ compiler, no Visual Studio, no `renderer.exe`, nothing to build.**
If you had the C1083 `crtdbg.h` / `stddef.h` errors building the native renderer,
this folder avoids that whole class of problems by design.

## Requirements (tiny)

| Tool | Size | Needed for |
|------|------|------------|
| Python 3.10+ (Windows: enable "Add to PATH") | installer only, one time | everything |
| `yt-dlp` (`pip install yt-dlp`) | ~5 MB | stream extraction |
| FFmpeg (`ffmpeg` + `ffplay` on PATH) | ~100 MB, likely already installed | video decode + audio |

That's it — total downloads are megabytes, not gigabytes.

## Run

```bat
run.bat                          REM just double-click or run in CMD
run.bat https://youtu.be/dQw4w9WgXcQ
run.bat <url> --mode ascii       REM modes: half (default), ascii, color
```

Or without the batch file:

```bat
pip install yt-dlp
set PYTHONPATH=src
python -m qwenplayer <url>
```

## Controls

| Key | Action |
|-----|--------|
| `space` / `p` | pause / resume |
| `←` / `→` | seek -5s / +5s |
| `+` / `-` | quality (render size) up/down |
| `m` | cycle render mode (half → ascii → color) |
| `r` | restart |
| any other key / `q` | quit (terminal is restored cleanly) |

## How it works (same concept as YouTubeCMD, simpler plumbing)

1. `streams.py` validates the URL and calls `yt-dlp --dump-json` to get direct
   stream URLs + metadata (no temp JSON files, all in-process).
2. `player.py` spawns `ffmpeg -ss <pos> -i <video_url> -vf scale/fps/format ...
   -f rawvideo pipe:1` and reads fixed-size frames straight from the pipe.
3. `renderer.py` converts raw pixels to terminal text (identical algorithm to
   the original C++ renderer: luminance ramp, U+2580 half blocks, 24-bit ANSI).
4. Audio plays through a detached `ffplay -nodisp` process.
5. `input_controller.py` does non-blocking keys with `msvcrt` on Windows and
   `termios` elsewhere; frame pacing adapts to keep sync.

## Differences from the main repo

- No native/C++ component at all (that's the point — zero build steps).
- No venv script, no config.json; sensible defaults + CLI flags instead.
- Volume is fixed at 80% (change `volume=` in `player.play()` if needed).
