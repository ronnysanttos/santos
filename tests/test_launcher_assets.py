from __future__ import annotations

from pathlib import Path

from ia_financeira.assets.paths import icon_path


def test_app_icon_files_exist():
    repo = Path(__file__).resolve().parents[1]
    assert (repo / "assets" / "ia_financeira.ico").is_file()
    assert (repo / "assets" / "ia_financeira.png").is_file()
    assert (repo / "src" / "ia_financeira" / "assets" / "ia_financeira.ico").is_file()
    assert (repo / "scripts" / "launch_ia_financeira.bat").is_file()
    assert (repo / "scripts" / "install_desktop_shortcut.ps1").is_file()


def test_icon_path_resolver():
    path = icon_path()
    assert path is not None
    assert path.suffix.lower() == ".ico"
    assert path.is_file()
