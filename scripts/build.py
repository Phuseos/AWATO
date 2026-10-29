"""Builds a standalone game for the current platform.

    Windows: dist/AWATO.exe  (one file, double-click to play)
    Linux:   dist/AWATO.sh   (one file: launcher script with the game appended)

Needs the build extra: pip install -e ".[build]"
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"

sys.path.insert(0, str(ROOT))
from awato import __version__  # noqa: E402


def pyinstaller(name, onefile):
    sep = os.pathsep
    subprocess.run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--log-level", "WARN", "--console",
        "--name", name,
        "--onefile" if onefile else "--onedir",
        "--distpath", str(BUILD / "dist"),
        "--workpath", str(BUILD / "work"),
        "--specpath", str(BUILD),
        "--paths", str(ROOT),
        "--add-data", f"{ROOT / 'content'}{sep}content",
        "--add-data", f"{ROOT / 'awato' / 'ui' / 'awato.tcss'}{sep}awato/ui",
        # Textual and Rich import some of their modules lazily, which PyInstaller can't see
        "--collect-submodules", "textual",
        "--collect-submodules", "rich",
        str(ROOT / "scripts" / "entry.py"),
    ], check=True, cwd=ROOT)
    return BUILD / "dist" / (f"{name}.exe" if onefile and sys.platform == "win32" else name)


def make_sh(app_dir: Path, out: Path):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        tar.add(app_dir, arcname="awato")
    payload = buffer.getvalue()

    header = (ROOT / "scripts" / "launcher.sh").read_text(encoding="utf-8")
    header = header.replace("@VERSION@", __version__)
    header = header.replace("@BUILD@", hashlib.sha256(payload).hexdigest()[:12])
    header = header.replace("@PAYLOAD_LINE@", str(header.count("\n") + 1))
    assert header.endswith("\n")

    out.write_bytes(header.encode("utf-8") + payload)
    out.chmod(0o755)


def main():
    shutil.rmtree(BUILD, ignore_errors=True)
    DIST.mkdir(exist_ok=True)
    if sys.platform == "win32":
        exe = pyinstaller("AWATO", onefile=True)
        out = DIST / "AWATO.exe"
        shutil.copy2(exe, out)
    elif sys.platform.startswith("linux"):
        app_dir = pyinstaller("awato", onefile=False)
        out = DIST / "AWATO.sh"
        make_sh(app_dir, out)
    else:
        sys.exit(f"No build recipe for {sys.platform} yet")
    print(f"Built {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
