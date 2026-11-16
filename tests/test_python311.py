"""Die Cloud-Läufe nutzen Python 3.11: Code darf keine Syntax neuerer Versionen enthalten (z. B. f-Strings über mehrere Zeilen)."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_video_code_laeuft_mit_python_311():
    py = shutil.which("python3.11")
    if not py:
        pytest.skip("python3.11 nicht installiert")
    dateien = [str(p) for p in sorted((ROOT / "cudi_video").rglob("*.py"))] + [str(p) for p in sorted((ROOT / ".github" / "scripts").glob("*.py"))]
    pruef = "import ast, sys\nfor f in sys.argv[1:]:\n    ast.parse(open(f, encoding='utf-8').read(), f)\n"
    lauf = subprocess.run([py, "-S", "-c", pruef, *dateien], capture_output=True, text=True, timeout=120)
    assert lauf.returncode == 0, lauf.stderr[-800:]
