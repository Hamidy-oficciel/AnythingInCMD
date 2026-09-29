"""Unit tests for the pure-Python core (no network, no ffmpeg needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qwenplayer.renderer import render_ascii, render_frame, render_halfblock
from qwenplayer.streams import extract_video_id, validate_youtube_url


def test_valid_watch_url():
    assert validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s") == "dQw4w9WgXcQ"


def test_valid_short_url():
    assert validate_youtube_url("https://youtu.be/dQw4w9WgXcQ")
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ?si=abc") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtu.be/short") is None


def test_valid_watch_url_extra_params():
    assert extract_video_id("https://www.youtube.com/watch?t=42&v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://m.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_invalid_urls():
    assert not validate_youtube_url("https://example.com/watch?v=dQw4w9WgXcQ")
    assert not validate_youtube_url("not a url")
    assert not validate_youtube_url("https://youtube.com/watch?v=short")
    assert not validate_youtube_url("ftp://youtu.be/dQw4w9WgXcQ")


def test_render_ascii_gray():
    px = bytes([0, 255])  # two pixels: black, white
    out = render_ascii(px, 2, 1, 1)
    assert out[0] == "@"   # darkest char
    assert out[-1] == " "  # lightest char


def test_render_halfblock_rows():
    px = bytes([10, 20, 30, 40])  # 1 col x 4 rows gray -> two terminal rows
    out = render_frame(px, 1, 4, 1, "half")
    assert "\u2580" in out
    assert "\x1b[38;2;10;10;10m" in out   # top pixel of first cell
    assert "\x1b[48;2;20;20;20m" in out   # bottom pixel (row 1) as background
    assert "\x1b[38;2;30;30;30m" in out   # top pixel of second cell


def test_render_color_rgb():
    px = bytes([255, 0, 0, 0, 255, 0])
    out = render_frame(px, 1, 2, 3, "color")
    assert "38;2;255;0;0" in out and "48;2;0;255;0" in out


def test_render_rejects_bad_input():
    try:
        render_frame(b"", 1, 1, 1, "half")
        assert False
    except ValueError:
        pass
    try:
        render_frame(b"\x00", 1, 1, 1, "bogus")
        assert False
    except ValueError:
        pass
