"""Asset path helpers (no GUI dependencies)."""

from __future__ import annotations

from pathlib import Path


def icon_path() -> Path | None:
    """Return path to ia_financeira.ico if present."""
    here = Path(__file__).resolve().parent / "ia_financeira.ico"
    if here.exists():
        return here
    root = Path(__file__).resolve().parents[3] / "assets" / "ia_financeira.ico"
    return root if root.exists() else None
