from pathlib import Path


def test_dev_server_script_reloads_current_app_and_checks_health():
    script = Path("scripts/start-dev.ps1")

    assert script.exists()
    content = script.read_text(encoding="utf-8")

    assert "--reload" in content
    assert "app.main:app" in content
    assert "Find-FreePort" in content
    assert "dev-server-$ActualPort.out.log" in content
    assert "dev-server-$ActualPort.err.log" in content
    assert "/health" in content
    assert "WorkingDirectory" in content
