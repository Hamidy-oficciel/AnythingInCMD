from browsercmd.snapshot import SNAPSHOT_SCRIPT


def test_snapshot_script_keeps_dom_collection_bounded():
    assert "MAX_NODES = 5000" in SNAPSHOT_SCRIPT
    assert "MAX_RUNS = 5000" in SNAPSHOT_SCRIPT
    assert "MAX_TEXT = 1000000" in SNAPSHOT_SCRIPT
    assert "getClientRects()" in SNAPSHOT_SCRIPT
    assert "textBytes + boundedText.length > MAX_TEXT" in SNAPSHOT_SCRIPT


def test_snapshot_script_captures_link_and_computed_style_metadata():
    for field in ("color: style.color", "background: style.backgroundColor", "bold:",
                  "italic:", "underline:", "link: Boolean(anchor)", "href:"):
        assert field in SNAPSHOT_SCRIPT