"""Playback loop: ffmpeg raw-video pipe -> terminal renderer, ffplay for audio.

Same concept as the native C++ player, but 100% Python - nothing to compile.
Requires only ffmpeg/ffplay on PATH.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

from qwenplayer.input_controller import (
    KEY_LEFT, KEY_MODE, KEY_PAUSE, KEY_QUALITY_DOWN, KEY_QUALITY_UP,
    KEY_RESTART, KEY_RIGHT, create_key_input,
)
from qwenplayer.renderer import render_frame
from qwenplayer.streams import StreamInfo

MAX_FPS = 30.0
SEEK_STEP = 5.0
MODES = ("half", "ascii", "color")


def _require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise RuntimeError(f"{binary} was not found on PATH. Install FFmpeg and try again.")
    return path


def terminal_size() -> tuple[int, int]:
    try:
        size = os.get_terminal_size()
        return max(20, size.columns), max(6, size.lines)
    except OSError:
        return 80, 24


def render_dimensions(stream: StreamInfo, cols: int, rows: int, mode: str, quality: float):
    """Fit the video into the terminal while preserving aspect ratio."""
    max_w = max(1, int(cols * quality))
    usable_rows = max(1, rows - 2)
    pixel_rows = usable_rows if mode == "ascii" else usable_rows * 2
    max_h = max(1, int(pixel_rows * quality))
    cell_aspect = 0.5 if mode == "ascii" else 1.0
    target = (stream.width / max(1, stream.height)) / cell_aspect
    if max_w / max_h > target:
        h = max_h
        w = max(1, round(h * target))
    else:
        w = max_w
        h = max(1, round(w / target))
    return min(w, max_w), min(h, max_h)


def video_filter(w: int, h: int, mode: str, fps: float) -> str:
    fmt = "rgb24" if mode == "color" else "gray"
    return (f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=fast_bilinear,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps={fps:.3f},format={fmt}")


def start_video(ffmpeg: str, stream: StreamInfo, position: float,
                w: int, h: int, mode: str, fps: float) -> subprocess.Popen:
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
           "-ss", f"{max(0.0, position):.3f}", "-i", stream.video_url,
           "-an", "-vf", video_filter(w, h, mode, fps),
           "-pix_fmt", "rgb24" if mode == "color" else "gray",
           "-f", "rawvideo", "pipe:1"]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL)


def start_audio(ffplay: str, stream: StreamInfo, position: float, volume: int):
    if not stream.audio_url:
        return None
    cmd = [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet",
           "-volume", str(volume), "-ss", f"{max(0.0, position):.3f}", "-i", stream.audio_url]
    try:
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    except OSError:
        return None


def read_exact(pipe, count: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < count:
        chunk = pipe.read(count - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def clock(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def fit(text: str, width: int) -> str:
    text = "".join(ch if ch.isprintable() or ch == " " else " " for ch in text)
    return text[:width].ljust(width)


def play(stream: StreamInfo, mode: str = "half", quality: float = 1.0,
         volume: int = 80, out=None) -> int:
    out = out or sys.stdout
    ffmpeg = _require("ffmpeg")
    ffplay = shutil.which("ffplay") or ""
    key_input = create_key_input()
    fps = max(1.0, min(MAX_FPS, stream.fps or 25.0))
    interval = 1.0 / fps
    paused = False
    position = 0.0
    started = time.perf_counter()
    frame_interval = interval
    rendered = 0
    fps_started = started
    measured_fps = 0.0

    cols, rows = terminal_size()
    w, h = render_dimensions(stream, cols, rows, mode, quality)
    channels = 3 if mode == "color" else 1
    video = start_video(ffmpeg, stream, position, w, h, mode, fps)
    audio = start_audio(ffplay, stream, position, volume) if ffplay else None

    def restart(at: float):
        nonlocal video, audio, position, started, w, h, frame_interval
        if video:
            video.kill()
        if audio:
            audio.kill()
        cols, rows = terminal_size()
        w, h = render_dimensions(stream, cols, rows, mode, quality)
        frame_interval = 1.0 / fps
        video = start_video(ffmpeg, stream, at, w, h, mode, fps)
        audio = start_audio(ffplay, stream, at, volume) if ffplay else None
        position = at
        started = time.perf_counter()

    def current_position() -> float:
        if paused:
            return position
        return position + (time.perf_counter() - started)

    try:
        out.write("\x1b[2J\x1b[H\x1b[?25l")
        while True:
            key = key_input.get_key()
            if key == KEY_MODE:
                mode = MODES[(MODES.index(mode) + 1) % len(MODES)]
                channels = 3 if mode == "color" else 1
                restart(current_position())
            elif key in (KEY_LEFT, KEY_RIGHT):
                delta = -SEEK_STEP if key == KEY_LEFT else SEEK_STEP
                new_pos = max(0.0, current_position() + delta)
                if stream.duration:
                    new_pos = min(new_pos, max(0.0, stream.duration - 0.5))
                restart(new_pos)
            elif key == KEY_RESTART:
                restart(0.0)
            elif key == KEY_PAUSE:
                if paused:
                    paused = False
                    started = time.perf_counter()
                    if audio:
                        audio.kill()
                        audio = start_audio(ffplay, stream, position, volume) if ffplay else None
                else:
                    position = current_position()
                    paused = True
                    if audio:
                        audio.kill()
                        audio = None
            elif key in (KEY_QUALITY_UP, KEY_QUALITY_DOWN):
                step = 0.25 if key == KEY_QUALITY_UP else -0.25
                quality = max(0.25, min(1.0, quality + step))
                restart(current_position())
            elif key is not None:  # any other key (incl. quit) stops playback
                break

            if video is None or video.stdout is None or video.poll() is not None:
                break
            data = read_exact(video.stdout, w * h * channels)
            if data is None:
                break

            frame = render_frame(data, w, h, channels, mode)
            now = time.perf_counter()
            state = "PAUSED" if paused else "PLAYING"
            total = clock(stream.duration) if stream.duration else "--:--"
            help_text = "[space]=pause m=mode <-/->=seek +/-=quality r=restart q=quit"
            details = (f" {state}  {clock(current_position())}/{total}  "
                       f"{measured_fps:.0f} FPS  Vol {volume}%  {mode.upper()}  "
                       f"Q{int(quality * 100)}%  {w}x{h}  {help_text}")
            status = fit(stream.title, cols) + "\n" + fit(details, cols)
            out.write("\x1b[H" + frame + "\n" + status)
            out.flush()

            rendered += 1
            elapsed_total = now - fps_started
            if elapsed_total >= 1.0:
                measured_fps = rendered / elapsed_total
                rendered = 0
                fps_started = now

            if not paused:
                # Adaptive pacing: speed up when behind, slow down when ahead.
                drift = (time.perf_counter() - now)
                frame_interval = max(1.0 / 60.0, min(1.0, frame_interval + drift * 0.1))
                remaining = frame_interval - (time.perf_counter() - now)
                if remaining > 0:
                    # Poll keys during the wait so input feels responsive.
                    deadline = time.perf_counter() + remaining
                    while time.perf_counter() < deadline:
                        k = key_input.get_key()
                        if k is not None:
                            break
                        time.sleep(min(0.004, max(0.0, deadline - time.perf_counter())))
    finally:
        if video:
            video.kill()
        if audio:
            audio.kill()
        key_input.close()
        out.write("\x1b[0m\x1b[?25h\x1b[J")
        out.flush()
    return 0
