from __future__ import annotations

from pathlib import Path
import sys


def bootstrap_src_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    return root
