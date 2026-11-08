"""Generate the compact 12-image OMR-Sheet dataset."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from omr.dataset import generate_dataset  # noqa: E402


if __name__ == "__main__":
    stats = generate_dataset(out_dir=ROOT, n_images=12, seed=20261108, clean=True)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
