"""Terminal frame renderers: ASCII, half-block grayscale, and truecolor ANSI.

Pure Python port of the original C++ renderer concept - same visual output,
no compilation step involved.
"""

from __future__ import annotations

RAMP = "@%#*+=-:. "
HALF_BLOCK = "\u2580"  # U+2580 UPPER HALF BLOCK (UTF-8: e2 96 80)


def _luminance(px: bytes, offset: int, channels: int) -> int:
    if channels == 1:
        return px[offset]
    return (299 * px[offset] + 587 * px[offset + 1] + 114 * px[offset + 2]) // 1000


def render_ascii(px: bytes, width: int, height: int, channels: int) -> str:
    lines = []
    for row in range(height):
        base = row * width * channels
        chars = [RAMP[_luminance(px, base + col * channels, channels) * 9 // 255]
                 for col in range(width)]
        lines.append("".join(chars))
    return "\n".join(lines)


def render_halfblock(px: bytes, width: int, height: int, channels: int, color: bool) -> str:
    """Two pixel rows per terminal row using the upper-half block glyph."""
    out = []
    for row in range(0, height, 2):
        top_base = row * width * channels
        has_bottom = row + 1 < height
        bottom_base = top_base + width * channels
        line = []
        for col in range(width):
            t = col * channels
            if color:
                tr, tg, tb = px[top_base + t], px[top_base + t + 1], px[top_base + t + 2]
                if has_bottom:
                    br, bg, bb = px[bottom_base + t], px[bottom_base + t + 1], px[bottom_base + t + 2]
                else:
                    br = bg = bb = 0
            else:
                tr = tg = tb = _luminance(px, top_base + t, channels)
                br = bg = bb = _luminance(px, bottom_base + t, channels) if has_bottom else 0
            line.append(f"\x1b[38;2;{tr};{tg};{tb}m\x1b[48;2;{br};{bg};{bb}m{HALF_BLOCK}")
        out.append("".join(line) + "\x1b[0m")
    return "\n".join(out)


def render_frame(px: bytes, width: int, height: int, channels: int, mode: str) -> str:
    if not px or width < 1 or height < 1 or channels not in (1, 3):
        raise ValueError("Invalid frame data")
    if mode == "ascii":
        return render_ascii(px, width, height, channels)
    if mode in ("half", "color"):
        return render_halfblock(px, width, height, channels, color=mode == "color")
    raise ValueError(f"Unknown render mode: {mode}")
