"""Save games and cross-playthrough progress, stored as JSON in the user's data folder."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from .engine import Meta

SAVE_VERSION = 1


def data_dir() -> Path:
    if os.environ.get("AWATO_DATA_DIR"):
        return Path(os.environ["AWATO_DATA_DIR"])
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "awato"
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "awato"


def _read(name):
    path = data_dir() / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(name, data):
    folder = data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f"{name}.tmp"
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(folder / name)


def save_game(engine):
    _write("save.json", {"version": SAVE_VERSION, "state": engine.state.to_dict()})


def load_game():
    """The saved state dict, or None if there is no usable save."""
    data = _read("save.json")
    if not data or data.get("version") != SAVE_VERSION:
        return None
    return data["state"]


def delete_save():
    (data_dir() / "save.json").unlink(missing_ok=True)


def load_meta() -> Meta:
    data = _read("meta.json") or {}
    return Meta(runs=data.get("runs", 0), endings_seen=list(data.get("endings_seen", [])))


def save_meta(meta: Meta):
    _write("meta.json", asdict(meta))


def load_settings() -> dict:
    return _read("settings.json") or {}


def save_settings(settings: dict):
    _write("settings.json", settings)
