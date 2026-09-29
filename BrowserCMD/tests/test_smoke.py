from browsercmd.cli import main


def test_engine_cli_reports_scaffold_status(capsys):
    assert main([]) == 0
    assert "not implemented yet" in capsys.readouterr().out


def test_engine_cli_accepts_url_without_claiming_navigation(capsys):
    assert main(["https://example.com"]) == 0
    assert "not implemented yet" in capsys.readouterr().out