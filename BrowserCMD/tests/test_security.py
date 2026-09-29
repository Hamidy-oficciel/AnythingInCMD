import pytest

from browsercmd.security import UrlError, normalize_url, sanitize_terminal_text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://example.com/path", "https://example.com/path"),
        ("example.com", "https://example.com"),
        ("localhost:8080/page", "https://localhost:8080/page"),
        ("about:blank", "about:blank"),
        ("  https://example.com  ", "https://example.com"),
    ],
)
def test_normalizes_supported_urls(value, expected):
    assert normalize_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "data:text/html,hello",
        "file:///etc/passwd",
        "chrome://settings",
        "edge://settings",
        "devtools://devtools",
        "https://user@example.com",
        "https://example.com/with space",
        "https://example.com:99999",
        "",
        "x" * 8193,
    ],
)
def test_rejects_disallowed_or_malformed_urls(value):
    with pytest.raises(UrlError):
        normalize_url(value)


def test_sanitizer_strips_terminal_controls_from_malicious_title():
    title = "safe\x1b[31mred\x1b]0;owned title\x07\x9b2J\x00"
    assert sanitize_terminal_text(title) == "safered"