"""Build BrowserCMD's native renderer and reuse it while sources are unchanged."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path


def source_digest(root: Path) -> str:
    native = root / "native"
    digest = hashlib.sha256()
    sources = sorted((native / "src").glob("*.cpp"))
    headers = sorted((native / "src").glob("*.hpp"))
    if not sources:
        raise RuntimeError("No native C++ source files were found.")
    for source in sources + headers:
        digest.update(source.relative_to(root).as_posix().encode("ascii"))
        digest.update(source.read_bytes())
    return digest.hexdigest()


def build_msvc(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["cmd.exe", "/d", "/c", str(root / "native" / "build_msvc.bat")],
        cwd=root,
        check=False,
    )


def build_gxx(root: Path, executable: Path, compiler: str) -> subprocess.CompletedProcess:
    sources = sorted((root / "native" / "src").glob("*.cpp"))
    command = [compiler, "-O2", "-Wall", "-Wextra", "-Werror", "-std=c++17"]
    if os.name == "nt":
        command.append("-static")
    command.extend(str(source) for source in sources)
    command.extend(("-o", str(executable)))
    return subprocess.run(command, cwd=root, check=False)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "bin"
    output_dir.mkdir(exist_ok=True)
    executable = output_dir / ("renderer.exe" if os.name == "nt" else "renderer")
    marker = output_dir / ".renderer-source-hash"
    try:
        digest = source_digest(root)
    except (OSError, RuntimeError) as error:
        print(f"Native build setup failed: {error}", file=sys.stderr)
        return 1

    if executable.exists() and marker.exists() and marker.read_text(encoding="ascii") == digest:
        print(f"Native renderer is up to date: {executable}")
        return 0

    result = None
    vswhere = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / \
        "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if os.name == "nt" and (shutil.which("cl") or vswhere.exists()):
        result = build_msvc(root)
        if result.returncode != 0:
            print("MSVC build failed; trying g++ if available.", file=sys.stderr)

    compiler = shutil.which("g++")
    if result is None or result.returncode != 0:
        if compiler:
            result = build_gxx(root, executable, compiler)
        elif result is None:
            print("No supported C++ compiler found. Install MSVC Build Tools or g++.", file=sys.stderr)
            return 1

    if result is None or result.returncode != 0 or not executable.exists():
        print("Native renderer build failed.", file=sys.stderr)
        return result.returncode if result is not None and result.returncode else 1

    temporary_marker = marker.with_suffix(".tmp")
    temporary_marker.write_text(digest, encoding="ascii")
    temporary_marker.replace(marker)
    print(f"Built native renderer: {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())