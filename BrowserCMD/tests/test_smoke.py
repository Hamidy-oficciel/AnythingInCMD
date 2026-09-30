from browsercmd.cli import main


def test_engine_cli_reports_missing_system_browser(monkeypatch, capsys):
    monkeypatch.setattr("browsercmd.browser.find_browser", lambda: None)
    assert main([]) == 1
    assert "No supported browser found." in capsys.readouterr().out


def test_engine_cli_normalizes_host_input(monkeypatch, capsys, tmp_path):
    observed = {}

    async def capture(url, output_dir, timeout):
        observed.update(url=url, output_dir=output_dir, timeout=timeout)
        return {
            "page_png": "page.png",
            "screencast_jpeg": "frame.jpg",
            "snapshot_json": "snapshot.json",
            "frame_sample_elapsed_seconds": 1.0,
            "screencast_frame_count": 18,
            "observed_frame_event_rate_hz": 18.0,
        }

    monkeypatch.setattr("browsercmd.cli.capture_page", capture)
    assert main(["--capture", "example.com", "--output-dir", str(tmp_path)]) == 0
    assert observed["url"] == "https://example.com"
    assert observed["output_dir"] == tmp_path
    output = capsys.readouterr().out
    assert "Text snapshot: snapshot.json" in output
    assert "18 frames in 1.000s (18.00 events/s)" in output


def test_engine_cli_sanitizes_browser_error_text(monkeypatch, capsys):
    async def malicious_page(*_args):
        raise RuntimeError("bad\x1b]0;owned title\x07\x1b[2J")

    monkeypatch.setattr("browsercmd.cli.capture_page", malicious_page)
    assert main(["--capture", "https://example.com"]) == 1
    output = capsys.readouterr().err
    assert "owned title" not in output
    assert "\x1b" not in output


def test_cli_uses_terminal_session_by_default(monkeypatch):
    observed = {}

    async def run_terminal(value, *, timeout):
        observed.update(value=value, timeout=timeout)
        return 0

    async def capture_page(*_args):
        raise AssertionError("default CLI path must not run diagnostic capture")

    monkeypatch.setattr("browsercmd.cli.run_terminal", run_terminal)
    monkeypatch.setattr("browsercmd.cli.capture_page", capture_page)
    assert main(["cats", "and", "dogs"]) == 0
    assert observed == {"value": "cats and dogs", "timeout": 30.0}