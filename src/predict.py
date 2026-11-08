"""Predict one aligned answer sheet with the proposed pipeline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from omr.config import BUBBLES, HEIGHT, N_QUESTIONS, OPTIONS, WIDTH  # noqa: E402
from omr.segmentation import predict_proposed, to_gray  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Recognise a filled OMR answer sheet.")
    parser.add_argument("--image", required=True, help="aligned image, 1240x1754 px")
    parser.add_argument("--out", default=str(ROOT / "results" / "predictions"))
    parser.add_argument("--delta", type=float, default=10.0)
    parser.add_argument("--threshold", type=float, default=0.40)
    args = parser.parse_args()

    path = Path(args.image)
    image = Image.open(path).convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        raise SystemExit(
            f"Expected {WIDTH}x{HEIGHT} px after cropping/alignment, got {image.size}. "
            "See README section '适用范围'."
        )

    pred = predict_proposed(to_gray(image), delta=args.delta, threshold=args.threshold)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    Image.fromarray(pred.mask, "L").save(out_dir / f"{stem}_mask.png")

    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    for b in BUBBLES:
        if pred.positives[b["q"] - 1, b["oi"]]:
            cx, cy = b["cx"], b["cy"]
            draw.ellipse([cx - 23, cy - 23, cx + 23, cy + 23], outline=(220, 40, 40), width=4)
    overlay.save(out_dir / f"{stem}_overlay.png")

    ans = " ".join(
        f"{q}:{pred.answers.get(q, '?') or '-'}" for q in range(1, N_QUESTIONS + 1)
    )
    print("answers:", ans)
    print("positive bubbles:", int(pred.positives.sum()))
    print("saved:", out_dir / f"{stem}_mask.png")
    print("saved:", out_dir / f"{stem}_overlay.png")
    print("options:", OPTIONS)


if __name__ == "__main__":
    main()
