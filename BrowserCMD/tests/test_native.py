import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_native_build_and_selftest():
    subprocess.run([sys.executable, str(ROOT / "native" / "build.py")], check=True, cwd=ROOT)
    executable = ROOT / "bin" / ("renderer.exe" if os.name == "nt" else "renderer")
    result = subprocess.run(
        [str(executable), "--selftest"], check=True, capture_output=True, text=True, cwd=ROOT
    )
    assert result.stdout == "BrowserCMD renderer self-test: OK\n"