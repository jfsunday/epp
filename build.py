#!/usr/bin/env python3
"""Build standalone E++ executables for Linux and Windows.

Usage:
    python build.py          # Build for the current platform
    python build.py --clean  # Clean build artifacts before building

The resulting binary lands in dist/epp (Linux) or dist/epp.exe (Windows).
No Python installation needed on the target machine.
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
VENV_PYTHON = ROOT / ".venv" / ("Scripts" if platform.system() == "Windows" else "bin") / "python3"

# All epp sub-modules that PyInstaller must bundle
HIDDEN_IMPORTS = [
    "epp",
    "epp.main",
    "epp.lexer",
    "epp.tokens",
    "epp.parser",
    "epp.ast_nodes",
    "epp.interpreter",
    "epp.environment",
    "epp.errors",
    "epp.builtins",
    "epp.visuals",
    "epp.game",
    "epp.webserver",
    "epp.database",
    # stdlib modules that might not be auto-detected
    "tkinter",
    "sqlite3",
    "http.server",
    "json",
    "math",
    "random",
    "datetime",
    "threading",
    "csv",
    "statistics",
    "urllib.parse",
]


def ensure_pyinstaller():
    """Install PyInstaller into the venv if missing."""
    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    try:
        subprocess.run(
            [python, "-c", "import PyInstaller"],
            check=True, capture_output=True,
        )
        print("[ok] PyInstaller already installed")
    except subprocess.CalledProcessError:
        print("[..] Installing PyInstaller...")
        subprocess.run(
            [python, "-m", "pip", "install", "pyinstaller"],
            check=True,
        )
        print("[ok] PyInstaller installed")
    return python


def clean():
    """Remove previous build artifacts."""
    for d in (BUILD, DIST, ROOT / "__pycache__"):
        if d.exists():
            shutil.rmtree(d)
            print(f"[ok] Removed {d.relative_to(ROOT)}")
    spec = ROOT / "epp.spec"
    if spec.exists():
        spec.unlink()
        print("[ok] Removed epp.spec")


def build(python: str):
    """Run PyInstaller to create the standalone binary."""
    cmd = [
        python, "-m", "PyInstaller",
        "--onefile",
        "--name", "epp",
        "--clean",
        # Entry point
        str(ROOT / "epp" / "__main__.py"),
    ]

    # Add hidden imports
    for mod in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", mod])

    # Add the project root to the Python path so epp package is found
    cmd.extend(["--paths", str(ROOT)])

    # Set working directory for correct module resolution
    print(f"\n[..] Building E++ for {platform.system()} ({platform.machine()})...")
    subprocess.run(cmd, check=True, cwd=str(ROOT))

    # Show result
    if platform.system() == "Windows":
        binary = DIST / "epp.exe"
    else:
        binary = DIST / "epp"

    if binary.exists():
        size_mb = binary.stat().st_size / (1024 * 1024)
        print(f"\n{'=' * 50}")
        print(f"  Built: {binary}")
        print(f"  Size:  {size_mb:.1f} MB")
        print(f"  Run:   {binary} examples/hello.epp")
        print(f"{'=' * 50}")
    else:
        print("\n[!!] Build failed — no binary found in dist/", file=sys.stderr)
        sys.exit(1)


def main():
    if "--clean" in sys.argv:
        clean()

    python = ensure_pyinstaller()
    build(python)


if __name__ == "__main__":
    main()
