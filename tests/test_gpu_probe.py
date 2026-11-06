"""CPU-only checks for GPU probe argument handling."""

import subprocess
import sys
from pathlib import Path


def test_probe_requires_config() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "gpu_probe.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert "--config" in result.stderr
