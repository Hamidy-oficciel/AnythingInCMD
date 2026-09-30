"""BrowserCMD's terminal-first search and text browsing command line."""

from __future__ import annotations

import argparse
import asyncio
import math
from pathlib import Path
import sys

from browsercmd import __version__
from browsercmd.browser import BrowserUnavailable
from browsercmd.cdp import CDPError
from browsercmd.security import UrlError, normalize_url, sanitize_terminal_text
from browsercmd.spike import capture_page
from browsercmd.terminal import run_terminal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search and browse the web from the terminal")
    parser.add_argument(
        "input", nargs="*", help="search query or HTTP(S) URL (omit to start at the search prompt)"
    )
    parser.add_argument(
        "--capture", action="store_true",
        help="save diagnostic PNG, screencast JPEG, and DOM JSON, then exit",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path.cwd() / "artifacts" / "m1",
        help="directory for the PNG, screencast JPEG, and JSON text snapshot",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="navigation timeout in seconds")
    parser.add_argument("--version", action="version", version=f"BrowserCMD {__version__}")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or not 3 <= args.timeout <= 120:
        parser.error("--timeout must be between 3 and 120 seconds")
    user_input = " ".join(args.input).strip() or None
    if not args.capture:
        try:
            return asyncio.run(run_terminal(user_input, timeout=args.timeout))
        except (BrowserUnavailable, CDPError, OSError, RuntimeError) as error:
            print(f"BrowserCMD: {sanitize_terminal_text(str(error))}", file=sys.stderr)
            return 1
    try:
        url = normalize_url(user_input or "about:blank")
        report = asyncio.run(capture_page(url, args.output_dir, args.timeout))
    except (UrlError, BrowserUnavailable, CDPError, OSError, RuntimeError) as error:
        print(f"BrowserCMD: {sanitize_terminal_text(str(error))}", file=sys.stderr)
        return 1
    print("Browser capture saved:")
    print(f"  PNG: {sanitize_terminal_text(report['page_png'])}")
    print(f"  Screencast: {sanitize_terminal_text(report['screencast_jpeg'])}")
    print(f"  Text snapshot: {sanitize_terminal_text(report['snapshot_json'])}")
    if report["frame_sample_elapsed_seconds"] > 0:
        print(
            "  Screencast sample: "
            f"{report['screencast_frame_count']} frames in "
            f"{report['frame_sample_elapsed_seconds']:.3f}s "
            f"({report['observed_frame_event_rate_hz']:.2f} events/s)"
        )
    else:
        print("  Screencast sample: not measured")
    print(
        "BrowserCMD M1 capture complete. The terminal page renderer is not yet implemented."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())