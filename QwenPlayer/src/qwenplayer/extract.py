"""Resolve a YouTube URL into stream metadata (in-process, no temp JSON files)."""

from __future__ import annotations

import argparse
import sys

from qwenplayer.player import play
from qwenplayer.streams import StreamError, extract_streams


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qwenplayer",
                                     description="Watch YouTube videos inside your terminal.")
    parser.add_argument("url", nargs="?", help="YouTube URL (prompted if omitted)")
    parser.add_argument("--mode", choices=["half", "ascii", "color"], default="half",
                        help="render mode (default: half-block)")
    parser.add_argument("--height", type=int, default=360,
                        help="maximum source height (default: 360)")
    args = parser.parse_args(argv)

    url = args.url
    try:
        if not url:
            print("YouTube URL: ", end="", file=sys.stderr, flush=True)
            url = input().strip()
        stream = extract_streams(url, max_height=args.height)
    except (EOFError, KeyboardInterrupt):
        print("Cancelled.", file=sys.stderr)
        return 0
    except StreamError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"Now playing: {stream.title} ({stream.width}x{stream.height} @ {stream.fps:.0f} fps)",
          file=sys.stderr, flush=True)
    try:
        return play(stream, mode=args.mode)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
