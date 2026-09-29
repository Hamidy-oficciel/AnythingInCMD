"""Input URL normalization and top-level scheme policy."""

from __future__ import annotations

import re
from urllib.parse import urlsplit


MAX_URL_LENGTH = 8192
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_HOST_PORT = re.compile(r"^([^:/?#]+):(\d+)(?:[/?#]|$)")
_ALLOWED_SCHEMES = {"http", "https"}
_RESERVED_SCHEMES = {
    "about", "chrome", "data", "devtools", "edge", "file", "http",
    "https", "javascript",
}
_OSC_SEQUENCE = re.compile(r"(?:\x1b\]|\x9d).*?(?:\x07|\x1b\\|\x9c|$)", re.DOTALL)
_CSI_SEQUENCE = re.compile(r"(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]")
_STRING_CONTROL = re.compile(r"(?:\x1b[P^_X]|[\x90\x98\x9e\x9f]).*?(?:\x1b\\|\x9c|$)", re.DOTALL)


class UrlError(ValueError):
    """Raised when a requested top-level URL is invalid or disallowed."""


def sanitize_terminal_text(value: str, max_length: int = 2048) -> str:
    without_controls = _OSC_SEQUENCE.sub("", value)
    without_controls = _CSI_SEQUENCE.sub("", without_controls)
    without_controls = _STRING_CONTROL.sub("", without_controls)
    safe = "".join(
        character
        for character in without_controls
        if not (ord(character) < 0x20 or 0x7F <= ord(character) <= 0x9F)
    )
    return safe[:max(0, max_length)]


def normalize_url(value: str) -> str:
    candidate = value.strip()
    if not candidate or len(candidate) > MAX_URL_LENGTH:
        raise UrlError("Enter a non-empty URL shorter than 8192 characters.")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in candidate):
        raise UrlError("URLs cannot contain control characters.")
    if any(character.isspace() for character in candidate):
        raise UrlError("URLs cannot contain whitespace.")

    if candidate.lower() == "about:blank":
        return "about:blank"

    match = _SCHEME.match(candidate)
    if match and "://" not in candidate:
        host_port = _HOST_PORT.match(candidate)
        is_host_port = host_port and host_port.group(1).lower() not in _RESERVED_SCHEMES
        if not is_host_port:
            raise UrlError("Only http and https URLs are allowed.")
    if "://" not in candidate:
        candidate = "https://" + candidate

    try:
        parsed = urlsplit(candidate)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise UrlError("The URL is malformed.") from error

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UrlError("Only http and https URLs are allowed.")
    if not hostname or parsed.username is not None or parsed.password is not None:
        raise UrlError("The URL must contain a host and cannot contain credentials.")
    if port is not None and not 1 <= port <= 65535:
        raise UrlError("The URL port is out of range.")
    try:
        hostname.encode("idna")
    except UnicodeError as error:
        raise UrlError("The URL host is invalid.") from error
    return candidate