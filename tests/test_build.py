import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the .sh launcher is for Linux")

ROOT = Path(__file__).resolve().parent.parent


def load_build_script():
    spec = importlib.util.spec_from_file_location("build_script", ROOT / "scripts" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sh_launcher_unpacks_once_and_passes_arguments(tmp_path):
    # A stand-in for the PyInstaller folder: a "game" that prints its arguments
    app = tmp_path / "app"
    app.mkdir()
    game = app / "awato"
    game.write_text("#!/bin/sh\necho \"game ran with: $*\"\n")
    game.chmod(0o755)
    out = tmp_path / "AWATO.sh"
    load_build_script().make_sh(app, out)

    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "XDG_CACHE_HOME": str(tmp_path / "cache")}
    first = subprocess.run(["sh", str(out), "--check"], env=env, capture_output=True, text=True, check=True)
    assert "Unpacking" in first.stderr
    assert first.stdout.strip() == "game ran with: --check"

    second = subprocess.run([str(out), "--seed", "3"], env=env, capture_output=True, text=True, check=True)
    assert "Unpacking" not in second.stderr
    assert second.stdout.strip() == "game ran with: --seed 3"
    assert len(list((tmp_path / "cache" / "awato").iterdir())) == 1
