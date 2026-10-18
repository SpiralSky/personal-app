import os
import time

from campus_assistant import service
from campus_assistant.config import Config


def test_unit_text():
    unit = service.unit_text("/repo/.venv/bin/python", service.REPO_ROOT)
    assert "ExecStart=/repo/.venv/bin/python -m campus_assistant.cli serve" in unit
    assert "WantedBy=graphical-session.target" in unit
    assert "KillMode=control-group" in unit and "TasksMax=256" in unit
    assert 'ExecStart="/my repo/python" -m' in service.unit_text("/my repo/python")


def test_unit_path_respects_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert service.unit_path() == tmp_path / "systemd" / "user" / service.UNIT_NAME


def test_ui_state(tmp_path):
    web = tmp_path / "web"
    (web / "src").mkdir(parents=True)
    src = web / "src" / "App.tsx"
    src.write_text("x")
    cfg = Config(data_dir=tmp_path / "data", web_dist=web / "dist")
    assert service.ui_state(cfg) == "missing"
    (web / "dist").mkdir()
    (web / "dist" / "index.html").write_text("<html/>")
    old = time.time() - 100
    os.utime(src, (old, old))
    assert service.ui_state(cfg) == "ok"
    os.utime(src, None)
    os.utime(web / "dist" / "index.html", (old, old))
    assert service.ui_state(cfg) == "stale"


def test_server_running_false_when_nothing_listens(tmp_path):
    assert not service.server_running(Config(data_dir=tmp_path, port=1))
