"""
PyInstaller packaging script for the RMM agent.
Produces a single-file executable for the current platform.

Usage:
    pip install pyinstaller
    python build.py

Output:
    dist/rmm_agent           (Linux/macOS)
    dist/rmm_agent.exe       (Windows)
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

_HERE = Path(__file__).parent
_DIST = _HERE / "dist"
_BUILD = _HERE / "_build"

# Platform-specific output name
_EXE_NAME = "rmm_agent"

# Files to bundle alongside the binary (copied next to the exe after build)
_BUNDLE_FILES = ["config.ini"]


def _check_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"])


def _pyinstaller_args() -> list:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", _EXE_NAME,
        "--distpath", str(_DIST),
        "--workpath", str(_BUILD),
        "--specpath", str(_BUILD),
        "--clean",
        "--noconfirm",
    ]

    # Hidden imports that PyInstaller misses via static analysis
    hidden = [
        "psutil",
        "requests",
        "configparser",
        "collector",
        "heartbeat",
        "executor",
        "script_runner",
        "terminal_worker",
        "version",
        "updater",
    ]

    if sys.platform == "win32":
        hidden += ["wmi", "win32crypt", "winreg", "win32api", "win32con"]
        # Hide console window on Windows
        args += ["--noconsole"]

    if sys.platform == "darwin":
        hidden += ["plistlib"]

    for h in hidden:
        args += ["--hidden-import", h]

    # Entry point
    args.append(str(_HERE / "rmm_agent.py"))
    return args


def main() -> None:
    print(f"Building RMM agent for {sys.platform}...")
    _check_pyinstaller()

    # Clean previous dist
    if _DIST.exists():
        shutil.rmtree(_DIST)

    args = _pyinstaller_args()
    print("Running:", " ".join(args))
    result = subprocess.run(args, cwd=str(_HERE))
    if result.returncode != 0:
        print("PyInstaller failed.")
        sys.exit(1)

    # Copy config template next to binary
    for fname in _BUNDLE_FILES:
        src = _HERE / fname
        dst = _DIST / fname
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            print(f"Copied {fname} → dist/")

    exe_suffix = ".exe" if sys.platform == "win32" else ""
    exe_path = _DIST / f"{_EXE_NAME}{exe_suffix}"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\nBuild complete: {exe_path}  ({size_mb:.1f} MB)")
        print("Deploy with: copy dist/ to target machine, edit config.ini, run rmm_agent")
    else:
        print("Build failed — binary not found in dist/")
        sys.exit(1)


if __name__ == "__main__":
    main()
