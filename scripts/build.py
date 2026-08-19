from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def run(args: list[str]) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def pyinstaller(*args: str) -> None:
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", *args])


def main() -> int:
    for path in (DIST, BUILD):
        if path.exists():
            shutil.rmtree(path)

    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run([sys.executable, "-c", "import tkinter; print('Tk', tkinter.TkVersion)"])

    common = ["--paths", "src"]
    if sys.platform == "win32":
        pyinstaller(
            "--onefile",
            "--windowed",
            "--name",
            "KeplerSet",
            *common,
            "scripts/keplerset_gui_entry.py",
        )
        pyinstaller(
            "--onefile",
            "--console",
            "--name",
            "KeplerSetCLI",
            *common,
            "scripts/keplerset_cli_entry.py",
        )
        print("Built dist/KeplerSet.exe and dist/KeplerSetCLI.exe")
        return 0

    if sys.platform == "darwin":
        # GitHub's macos-14 standard runner is native arm64. --target-arch is
        # explicit so accidental Intel/Rosetta builds fail rather than ship.
        pyinstaller(
            "--onefile",
            "--windowed",
            "--target-arch",
            "arm64",
            "--osx-bundle-identifier",
            "org.keplerset.app",
            "--name",
            "KeplerSet",
            *common,
            "scripts/keplerset_gui_entry.py",
        )
        pyinstaller(
            "--onefile",
            "--console",
            "--target-arch",
            "arm64",
            "--name",
            "KeplerSetCLI",
            *common,
            "scripts/keplerset_cli_entry.py",
        )
        print("Built native arm64 dist/KeplerSet.app and dist/KeplerSetCLI")
        return 0

    raise SystemExit("Executable packaging is supported on Windows and macOS only.")


if __name__ == "__main__":
    raise SystemExit(main())
