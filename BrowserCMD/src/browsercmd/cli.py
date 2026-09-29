"""BrowserCMD command-line entry point for the M0 scaffold."""

from __future__ import annotations

import argparse

from browsercmd import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BrowserCMD terminal browser")
    parser.add_argument("url", nargs="?", help="URL to open (browser support is not implemented yet)")
    parser.add_argument("--version", action="version", version=f"BrowserCMD {__version__}")
    parser.parse_args(argv)
    print("BrowserCMD M0 scaffold: browser functionality is not implemented yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())