"""Non-blocking keyboard input for Windows console and POSIX terminals."""

from __future__ import annotations

import sys

KEY_QUIT = "quit"
KEY_PAUSE = "pause"
KEY_LEFT = "left"
KEY_RIGHT = "right"
KEY_UP = "up"
KEY_DOWN = "down"
KEY_RESTART = "restart"
KEY_QUALITY_UP = "quality_up"
KEY_QUALITY_DOWN = "quality_down"
KEY_MODE = "mode"


class KeyInput:
    def get_key(self) -> str | None:  # pragma: no cover - overridden below
        return None

    def close(self) -> None:
        pass


class WindowsKeyInput(KeyInput):
    def __init__(self) -> None:
        import msvcrt  # noqa: PLC0415 - Windows only

        self._msvcrt = msvcrt

    def get_key(self) -> str | None:
        if not self._msvcrt.kbhit():
            return None
        first = self._msvcrt.getwch()
        if first in ("\x00", "\xe0"):  # extended key prefix
            second = self._msvcrt.getwch()
            return {
                "K": KEY_LEFT, "M": KEY_RIGHT,
                "H": KEY_UP, "P": KEY_DOWN,
            }.get(second)
        if first in ("q", "Q", "\x1b"):
            return KEY_QUIT
        if first in (" ", "p", "P"):
            return KEY_PAUSE
        if first in ("r", "R"):
            return KEY_RESTART
        if first in ("+", "="):
            return KEY_QUALITY_UP
        if first in ("-", "_"):
            return KEY_QUALITY_DOWN
        if first in ("m", "M"):
            return KEY_MODE
        return None


class PosixKeyInput(KeyInput):
    def __init__(self) -> None:
        import termios  # noqa: PLC0415
        import tty  # noqa: PLC0415

        self._fd = sys.stdin.fileno()
        self._old = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        self._termios = termios

    def get_key(self) -> str | None:
        import select  # noqa: PLC0415

        if not select.select([sys.stdin], [], [], 0)[0]:
            return None
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            if select.select([sys.stdin], [], [], 0)[0]:
                seq = sys.stdin.read(1)
                if seq == "[" and select.select([sys.stdin], [], [], 0)[0]:
                    code = sys.stdin.read(1)
                    return {"D": KEY_LEFT, "C": KEY_RIGHT,
                            "A": KEY_UP, "B": KEY_DOWN}.get(code)
            return KEY_QUIT
        return {
            "q": KEY_QUIT, " ": KEY_PAUSE, "p": KEY_PAUSE, "r": KEY_RESTART,
            "+": KEY_QUALITY_UP, "=": KEY_QUALITY_UP, "-": KEY_QUALITY_DOWN,
            "_": KEY_QUALITY_DOWN, "m": KEY_MODE,
        }.get(ch.lower())

    def close(self) -> None:
        self._termios.tcsetattr(self._fd, self._termios.TCSADRAIN, self._old)


def create_key_input() -> KeyInput:
    if sys.platform == "win32":
        return WindowsKeyInput()
    try:
        return PosixKeyInput()
    except (ImportError, OSError, ValueError):
        return KeyInput()
