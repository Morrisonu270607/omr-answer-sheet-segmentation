"""Project-wide constants and the canonical answer-sheet layout."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
IMAGE_DIR = DATA_DIR / "images"
MASK_DIR = DATA_DIR / "masks"
ANNOTATION_DIR = DATA_DIR / "annotations"
RESULTS_DIR = ROOT / "results"
FIGURE_DIR = ROOT / "docs" / "figures"

# A4 at 150 dpi.  The synthetic photos are already cropped and aligned.
WIDTH = 1240
HEIGHT = 1754

N_QUESTIONS = 20
OPTIONS = "ABCD"
ROW0 = 350
ROW_H = 58
Q_X = 110
OPT_X = (300, 430, 560, 690)
BUBBLE_R = 18
GT_R = 17          # radius of a filled option region in the ground truth
ROI_R = 15         # inner radius used to measure pencil coverage

GROUPS = ("clean", "light", "hard")
GROUP_CN = {"clean": "清晰组", "light": "光照不均组", "hard": "低对比/噪声组"}

# Fonts available on the build machine.  Noto Sans SC is used for the rendered
# dataset (open font); Microsoft YaHei bold is used only for headings.
FONT_REGULAR = Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
FONT_SONG = Path(r"C:\Windows\Fonts\simsun.ttc")

BUBBLES = []
for _q in range(1, N_QUESTIONS + 1):
    for _oi, _opt in enumerate(OPTIONS):
        BUBBLES.append(
            {
                "q": _q,
                "opt": _opt,
                "oi": _oi,
                "cx": OPT_X[_oi],
                "cy": ROW0 + (_q - 1) * ROW_H,
            }
        )

BUBBLE_INDEX = {(b["q"], b["opt"]): i for i, b in enumerate(BUBBLES)}
BUBBLE_Q = [b["q"] for b in BUBBLES]
BUBBLE_OPT = [b["opt"] for b in BUBBLES]
BUBBLE_CX = [b["cx"] for b in BUBBLES]
BUBBLE_CY = [b["cy"] for b in BUBBLES]


def bubble_center(q: int, opt: str) -> tuple[int, int]:
    """Return the canonical centre of a bubble."""
    b = BUBBLES[BUBBLE_INDEX[(q, opt)]]
    return b["cx"], b["cy"]
