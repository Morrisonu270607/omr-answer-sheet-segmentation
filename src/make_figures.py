"""Build the two figures used in the report and README."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from omr.config import FIGURE_DIR, GROUP_CN  # noqa: E402
from omr.evaluation import load_gt  # noqa: E402
from omr.segmentation import (  # noqa: E402
    predict_baseline_cc,
    predict_global_roi,
    predict_proposed,
    to_gray,
)

FONT = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"
_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(FONT, size=size)
    return _font_cache[size]


def _panel(
    image: Image.Image,
    label: str,
    width: int = 380,
    height: int = 560,
    bg: str = "white",
) -> Image.Image:
    canvas = Image.new("RGB", (width, height + 42), bg)
    show = ImageOps.contain(image.convert("RGB"), (width - 12, height - 12), Image.Resampling.LANCZOS)
    canvas.paste(show, ((width - show.width) // 2, 42 + (height - show.height) // 2))
    d = ImageDraw.Draw(canvas)
    d.text((width // 2, 20), label, font=font(20), fill=(30, 30, 30), anchor="mm")
    d.rectangle([(1, 1), (width - 2, height + 40)], outline=(210, 210, 210), width=1)
    return canvas


def _mask_image(mask, width: int, height: int) -> Image.Image:
    import numpy as np

    arr = (mask > 127).astype("uint8") * 255
    return Image.fromarray(arr, "L").convert("RGB").resize((width, height), Image.Resampling.NEAREST)


def _overlay_answers(image: Image.Image, pred, gt) -> Image.Image:
    from omr.config import BUBBLES

    out = image.copy()
    d = ImageDraw.Draw(out)
    for b in BUBBLES:
        q, oi = b["q"] - 1, b["oi"]
        p = bool(pred.positives[q, oi])
        g = bool(gt["positives"][q, oi])
        if not (p or g):
            continue
        color = (0, 170, 70) if p and g else (220, 40, 40) if p else (30, 90, 230)
        cx, cy = b["cx"], b["cy"]
        d.ellipse([cx - 23, cy - 23, cx + 23, cy + 23], outline=color, width=4)
    return out


def make_dataset_figure(rows: list[dict], out_path: Path) -> None:
    wanted = ["S01", "S02", "S03", "S06"]
    panels = []
    for image_id in wanted:
        r = next(x for x in rows if x["id"] == image_id)
        img = Image.open(ROOT / r["image"])
        panels.append(_panel(img, f"{image_id}  {GROUP_CN[r['group']]}", width=400, height=600))
    canvas = Image.new("RGB", (2 * 400, 2 * 642), "white")
    for i, p in enumerate(panels):
        canvas.paste(p, ((i % 2) * 400, (i // 2) * 642))
    canvas.save(out_path)


def make_comparison_figure(rows: list[dict], tuned: dict, out_path: Path) -> None:
    r = next(x for x in rows if x["id"] == "S09")
    image = Image.open(ROOT / r["image"]).convert("RGB")
    gray = to_gray(image)
    gt = load_gt(ROOT / r["annotation"], ROOT / r["mask"])
    base = predict_baseline_cc(gray, **tuned["baseline_cc"]["params"])
    glob = predict_global_roi(gray, **tuned["global_roi"]["params"])
    prop = predict_proposed(gray, **tuned["proposed"]["params"])

    panels = [
        _panel(image, "（a）输入：hard 组"),
        _panel(_mask_image(gt["mask"], 320, 453), "（b）真值掩膜"),
        _panel(_mask_image(base.mask, 320, 453), "（c）基线：Otsu+连通域"),
        _panel(_mask_image(glob.mask, 320, 453), "（d）对照：Otsu+覆盖率"),
        _panel(_mask_image(prop.mask, 320, 453), "（e）改进方法掩膜"),
        _panel(_overlay_answers(image, prop, gt), "（f）改进方法叠加"),
    ]
    canvas = Image.new("RGB", (3 * 380, 2 * 602), "white")
    for i, p in enumerate(panels):
        canvas.paste(p, ((i % 3) * 380, (i // 3) * 602))
    canvas.save(out_path)


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    with (ROOT / "data" / "index.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    tuned = json.loads((ROOT / "results" / "tuned_params.json").read_text(encoding="utf-8"))
    make_dataset_figure(rows, FIGURE_DIR / "fig_dataset.png")
    make_comparison_figure(rows, tuned, FIGURE_DIR / "fig_comparison.png")
    print("figures written:", FIGURE_DIR)


if __name__ == "__main__":
    main()
