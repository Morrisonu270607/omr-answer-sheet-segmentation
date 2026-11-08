"""Synthetic answer-sheet renderer and deterministic degradation pipeline.

The images are *not* photographs.  They are generated from a fixed, known layout
so that every pixel of the filled-option ground truth is exact.  This is
deliberate: the course design studies thresholding and morphology, and a
controlled dataset makes the comparison reproducible and free of annotation
noise.  See ``data/README.md`` for the limitations of this choice.
"""
from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import (
    BUBBLES,
    GROUP_CN,
    GROUPS,
    HEIGHT,
    N_QUESTIONS,
    OPTIONS,
    OPT_X,
    Q_X,
    ROW0,
    ROW_H,
    GT_R,
    BUBBLE_R,
    WIDTH,
    FONT_BOLD,
    FONT_REGULAR,
)

FONT_CACHE: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key not in FONT_CACHE:
        path = FONT_BOLD if bold else FONT_REGULAR
        if not path.exists():
            # Last-resort fallback.  The generated text will be Latin-only.
            FONT_CACHE[key] = ImageFont.load_default()
        else:
            FONT_CACHE[key] = ImageFont.truetype(str(path), size=size)
    return FONT_CACHE[key]


def _paper(rng: np.random.Generator) -> Image.Image:
    """Cream paper with low-frequency mottling and fine grain."""
    base = np.empty((HEIGHT, WIDTH, 3), dtype=np.float32)
    base[..., 0] = 247.0
    base[..., 1] = 244.0
    base[..., 2] = 234.0

    # Low-frequency paper texture: resize a coarse random field.
    small = rng.normal(0.0, 1.0, (max(2, HEIGHT // 48), max(2, WIDTH // 48), 3))
    tex = np.asarray(
        Image.fromarray(np.uint8(np.clip(small * 32 + 128, 0, 255))).resize(
            (WIDTH, HEIGHT), Image.Resampling.BICUBIC
        ),
        dtype=np.float32,
    )
    base += (tex - 128.0) * 0.10
    base += rng.normal(0.0, 2.0, base.shape)
    return Image.fromarray(np.uint8(np.clip(base, 0, 255)), "RGB")


def _draw_pencil(
    overlay: Image.Image,
    cx: int,
    cy: int,
    rng: random.Random,
    strength: float,
) -> None:
    """Draw a graphite-like mark inside a bubble.

    ``strength`` in [0, 1] controls both coverage and darkness.  A light mark is
    intentionally close to the paper intensity so that the hard subset is not
    trivially separable by a global threshold.
    """
    draw = ImageDraw.Draw(overlay)
    r = 14.0
    base_alpha = int(18 + 58 * strength)
    # Irregular graphite base, slightly offset so the mark is not a perfect disk.
    ox = rng.uniform(-1.6, 1.6)
    oy = rng.uniform(-1.6, 1.6)
    d = rng.uniform(0.88, 1.0) * r
    draw.ellipse(
        [cx - d + ox, cy - d + oy, cx + d + ox, cy + d + oy],
        fill=(58, 58, 54, base_alpha),
    )

    # Several parallel / zig-zag strokes, like a real pencil fill.
    n_strokes = rng.randint(5, 8)
    for _ in range(n_strokes):
        y0 = cy + rng.uniform(-11.5, 11.5)
        x0 = cx + rng.uniform(-13.0, -6.0)
        x1 = cx + rng.uniform(6.0, 13.0)
        bend = rng.uniform(-3.0, 3.0)
        alpha = int(70 + 95 * strength)
        width = rng.randint(2, 4)
        draw.line(
            [(x0, y0), ((x0 + x1) / 2, y0 + bend), (x1, y0 + rng.uniform(-2.0, 2.0))],
            fill=(42, 42, 39, alpha),
            width=width,
            joint="curve",
        )

    # Graphite speckle / stipple, including a few pixels just outside the ROI.
    for _ in range(rng.randint(70, 110)):
        ang = rng.uniform(0, 2 * math.pi)
        rad = math.sqrt(rng.random()) * (r + rng.uniform(-1.0, 2.0))
        x = cx + math.cos(ang) * rad + ox
        y = cy + math.sin(ang) * rad + oy
        alpha = int(40 + 130 * strength)
        draw.ellipse(
            [x - 1.0, y - 1.0, x + 1.0, y + 1.0],
            fill=(38, 38, 35, alpha),
        )


def _draw_stray_marks(img: Image.Image, rng: random.Random, n: int) -> Image.Image:
    """A few accidental pencil smudges in the margins."""
    if n <= 0:
        return img
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for _ in range(n):
        if rng.random() < 0.5:
            x = rng.choice([rng.randint(30, 70), rng.randint(990, 1160)])
        else:
            x = rng.randint(70, 980)
        y = rng.randint(300, 1600)
        length = rng.randint(12, 42)
        angle = rng.uniform(-0.5, 0.5)
        draw.line(
            [(x, y), (x + math.cos(angle) * length, y + math.sin(angle) * length)],
            fill=(80, 80, 74, rng.randint(35, 90)),
            width=rng.randint(1, 3),
        )
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def render_sheet(
    answers: dict[int, str],
    strengths: dict[int, float],
    rng: random.Random,
    np_rng: np.random.Generator,
    group: str,
) -> tuple[Image.Image, Image.Image]:
    """Render a clean sheet and its exact filled-region mask."""
    img = _paper(np_rng).convert("RGBA")
    draw = ImageDraw.Draw(img)

    ink = (52, 52, 49, 255)
    muted = (112, 108, 99, 255)
    rule = (202, 197, 186, 255)

    # Header.
    draw.text(
        (WIDTH // 2, 76),
        "图像处理课程小测答题卡",
        font=_font(38, bold=True),
        fill=ink,
        anchor="mm",
    )
    draw.text(
        (WIDTH // 2, 122),
        "20 道单选题 · 每题 1 分 · 满分 20 分",
        font=_font(17),
        fill=muted,
        anchor="mm",
    )
    draw.line([(80, 150), (WIDTH - 80, 150)], fill=rule, width=2)

    draw.text((85, 176), "学院：________________", font=_font(17), fill=ink)
    draw.text((520, 176), "专业：________________", font=_font(17), fill=ink)
    draw.text((905, 176), "班级：____________", font=_font(17), fill=ink)
    draw.text((85, 214), "学号：________________", font=_font(17), fill=ink)
    draw.text((520, 214), "姓名：________________", font=_font(17), fill=ink)
    draw.text((905, 214), "试卷：A 卷", font=_font(17), fill=ink)
    draw.text(
        (85, 252),
        "填涂说明：请用 2B 铅笔将所选选项涂满、涂黑；每题只有一个正确答案。",
        font=_font(15),
        fill=muted,
    )
    draw.line([(80, 286), (WIDTH - 80, 286)], fill=rule, width=2)

    # Table header.
    header_y = 318
    draw.text((Q_X, header_y), "题号", font=_font(17, bold=True), fill=ink, anchor="mm")
    for oi, opt in enumerate(OPTIONS):
        draw.text((OPT_X[oi], header_y), opt, font=_font(17, bold=True), fill=ink, anchor="mm")
    draw.text((892, header_y), "得分", font=_font(17, bold=True), fill=ink, anchor="mm")
    draw.line([(80, 342), (980, 342)], fill=rule, width=2)

    # Rows and printed bubbles.
    for q in range(1, N_QUESTIONS + 1):
        cy = ROW0 + (q - 1) * ROW_H
        if q > 1:
            draw.line([(80, cy - ROW_H // 2), (980, cy - ROW_H // 2)], fill=rule, width=1)
        draw.text((Q_X, cy), f"{q:02d}", font=_font(18), fill=ink, anchor="mm")
        for oi, opt in enumerate(OPTIONS):
            cx = OPT_X[oi]
            draw.ellipse(
                [cx - BUBBLE_R, cy - BUBBLE_R, cx + BUBBLE_R, cy + BUBBLE_R],
                outline=(126, 121, 112, 255),
                width=2,
            )
            draw.text((cx, cy), opt, font=_font(13), fill=(130, 125, 116, 255), anchor="mm")

    # Scoring box.
    draw.rectangle([(840, 342), (1130, 1510)], outline=rule, width=2)
    draw.text((985, 372), "阅卷区", font=_font(17, bold=True), fill=muted, anchor="mm")
    draw.text((985, 430), "答对题数：________", font=_font(15), fill=muted, anchor="mm")
    draw.text((985, 480), "得    分：________", font=_font(15), fill=muted, anchor="mm")
    draw.line([(840, 1510), (1130, 1510)], fill=rule, width=2)
    draw.text(
        (WIDTH // 2, 1635),
        "请保持卡面清洁，不要折叠；修改时请用橡皮擦干净。",
        font=_font(14),
        fill=muted,
        anchor="mm",
    )
    draw.text(
        (WIDTH // 2, 1690),
        "图像处理课程设计 · 自建 OMR-Sheet 数据集",
        font=_font(12),
        fill=(150, 145, 136, 255),
        anchor="mm",
    )

    # Pencil marks on an overlay, so their alpha is independent of the print.
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    for q in range(1, N_QUESTIONS + 1):
        opt = answers[q]
        cx, cy = OPT_X[OPTIONS.index(opt)], ROW0 + (q - 1) * ROW_H
        _draw_pencil(overlay, cx, cy, rng, strengths[q])
    img = Image.alpha_composite(img, overlay).convert("RGB")

    # A few stray marks in the margins; deliberately excluded from the mask.
    stray = 1 if group == "light" else (2 if group == "hard" else 0)
    if stray:
        img = _draw_stray_marks(img, rng, stray)

    # Exact mask: a disk around every selected option.
    mask = Image.new("L", (WIDTH, HEIGHT), 0)
    mdraw = ImageDraw.Draw(mask)
    for q, opt in answers.items():
        cx, cy = OPT_X[OPTIONS.index(opt)], ROW0 + (q - 1) * ROW_H
        mdraw.ellipse([cx - GT_R, cy - GT_R, cx + GT_R, cy + GT_R], fill=255)
    return img, mask


def degrade(
    img: Image.Image,
    group: str,
    rng: np.random.Generator,
) -> Image.Image:
    """Photometric degradation: illumination, shadow, blur, noise, JPEG."""
    arr = np.asarray(img, dtype=np.float32)
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    xn = xx / (WIDTH - 1)
    yn = yy / (HEIGHT - 1)

    if group == "clean":
        light = 1.00 - 0.10 * xn - 0.035 * yn + 0.012 * np.sin(2 * np.pi * (1.1 * xn + 0.2))
        blur_radius = 0.55
        noise_sigma = 2.0
        jpeg_quality = 95
        texture = 1.5
    elif group == "light":
        light = 1.02 - 0.26 * xn - 0.05 * yn + 0.020 * np.sin(2 * np.pi * (1.7 * xn + 0.4))
        # A soft diagonal shadow across the middle of the sheet.
        sx, sy = 0.47, 0.43
        shadow = np.exp(-(((xn - sx) ** 2) / (2 * 0.20**2) + ((yn - sy) ** 2) / (2 * 0.42**2)))
        light -= 0.13 * shadow
        blur_radius = 1.0
        noise_sigma = 4.0
        jpeg_quality = 91
        texture = 3.0
    else:
        light = 1.04 - 0.34 * xn - 0.07 * yn + 0.025 * np.sin(2 * np.pi * (1.3 * xn + 0.1))
        sx, sy = 0.55, 0.38
        shadow = np.exp(-(((xn - sx) ** 2) / (2 * 0.26**2) + ((yn - sy) ** 2) / (2 * 0.55**2)))
        light -= 0.24 * shadow
        # Low-frequency blotches, like a phone photo under mixed lighting.
        blotch = np.asarray(
            Image.fromarray(
                np.uint8(
                    np.clip(
                        rng.normal(0.0, 1.0, (max(2, HEIGHT // 60), max(2, WIDTH // 60))) * 40 + 128,
                        0,
                        255,
                    )
                )
            ).resize((WIDTH, HEIGHT), Image.Resampling.BICUBIC),
            dtype=np.float32,
        )
        light -= (blotch - 128.0) / 255.0 * 0.10
        blur_radius = 1.45
        noise_sigma = 6.5
        jpeg_quality = 86
        texture = 4.5

    light = np.clip(light, 0.50, 1.06)
    # Mild warm cast and vignetting.
    arr[..., 0] *= light * 1.012
    arr[..., 1] *= light * 1.000
    arr[..., 2] *= light * 0.982
    vignette = 1.0 - 0.10 * ((xn - 0.5) ** 2 + (yn - 0.5) ** 2) * 4.0
    arr *= vignette[..., None]

    # Fine paper grain, so a smoothed image is not artificially clean.
    arr += rng.normal(0.0, texture, arr.shape[:2])[..., None]

    img2 = Image.fromarray(np.uint8(np.clip(arr, 0, 255)), "RGB")
    if blur_radius > 0:
        img2 = img2.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    arr2 = np.asarray(img2, dtype=np.float32)
    arr2 += rng.normal(0.0, noise_sigma, arr2.shape)
    img2 = Image.fromarray(np.uint8(np.clip(arr2, 0, 255)), "RGB")
    return img2


def _make_answers(rng: random.Random) -> dict[int, str]:
    return {q: rng.choice(OPTIONS) for q in range(1, N_QUESTIONS + 1)}


def _make_strengths(rng: random.Random, group: str) -> dict[int, float]:
    if group == "clean":
        lo, hi = 0.60, 0.95
    elif group == "light":
        lo, hi = 0.38, 0.82
    else:
        lo, hi = 0.16, 0.52
    return {q: rng.uniform(lo, hi) for q in range(1, N_QUESTIONS + 1)}


def generate_dataset(
    out_dir: str | Path | None = None,
    n_images: int = 30,
    seed: int = 20261108,
    clean: bool = False,
) -> dict:
    """Generate images, masks, annotations and a stratified split."""
    root = Path(out_dir) if out_dir else Path(__file__).resolve().parents[2]
    image_dir = root / "data" / "images"
    mask_dir = root / "data" / "masks"
    ann_dir = root / "data" / "annotations"
    for d in (image_dir, mask_dir, ann_dir):
        d.mkdir(parents=True, exist_ok=True)
        if clean:
            for p in d.glob("*"):
                if p.is_file():
                    p.unlink()

    index_rows = []
    for i in range(n_images):
        image_id = f"S{i + 1:02d}"
        group = GROUPS[i % len(GROUPS)]
        rng = random.Random(seed + i * 97)
        np_rng = np.random.default_rng(seed + i * 97 + 1)
        answers = _make_answers(rng)
        strengths = _make_strengths(rng, group)
        clean_img, mask = render_sheet(answers, strengths, rng, np_rng, group)
        img = degrade(clean_img, group, np_rng)

        img_path = image_dir / f"{image_id}.jpg"
        mask_path = mask_dir / f"{image_id}.png"
        img.save(img_path, quality=(95 if group == "clean" else 91 if group == "light" else 86))
        mask.save(mask_path)

        ann = {
            "id": image_id,
            "group": group,
            "group_cn": GROUP_CN[group],
            "seed": seed + i * 97,
            "size": [WIDTH, HEIGHT],
            "answers": {str(q): a for q, a in answers.items()},
            "strengths": {str(q): round(s, 4) for q, s in strengths.items()},
            "bubbles": [
                {"q": b["q"], "opt": b["opt"], "cx": b["cx"], "cy": b["cy"]} for b in BUBBLES
            ],
            "image": f"data/images/{image_id}.jpg",
            "mask": f"data/masks/{image_id}.png",
        }
        (ann_dir / f"{image_id}.json").write_text(
            json.dumps(ann, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        index_rows.append(
            {
                "id": image_id,
                "group": group,
                "image": f"data/images/{image_id}.jpg",
                "mask": f"data/masks/{image_id}.png",
                "annotation": f"data/annotations/{image_id}.json",
            }
        )

    # Stratified split: 2 validation + 2 test images per group for the compact
    # 12-image course-design dataset.
    split: dict[str, str] = {}
    for gi, group in enumerate(GROUPS):
        ids = [r["id"] for r in index_rows if r["group"] == group]
        random.Random(seed + 500 + gi).shuffle(ids)
        n_val = 2 if len(ids) <= 5 else (3 if group in ("clean", "light") else 4)
        for image_id in ids[:n_val]:
            split[image_id] = "val"
        for image_id in ids[n_val:]:
            split[image_id] = "test"

    for row in index_rows:
        row["split"] = split[row["id"]]
    index_rows.sort(key=lambda r: r["id"])
    with (root / "data" / "index.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id", "group", "split", "image", "mask", "annotation"]
        )
        writer.writeheader()
        writer.writerows(index_rows)

    (root / "data" / "splits.json").write_text(
        json.dumps(split, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    stats = {
        "n_images": len(index_rows),
        "n_questions_per_image": N_QUESTIONS,
        "n_filled_marks": len(index_rows) * N_QUESTIONS,
        "n_bubbles": len(index_rows) * len(BUBBLES),
        "groups": {g: sum(1 for r in index_rows if r["group"] == g) for g in GROUPS},
        "splits": {
            "val": sum(1 for r in index_rows if r["split"] == "val"),
            "test": sum(1 for r in index_rows if r["split"] == "test"),
        },
        "size": [WIDTH, HEIGHT],
    }
    (root / "data" / "dataset_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return stats


if __name__ == "__main__":
    print(json.dumps(generate_dataset(clean=True), ensure_ascii=False, indent=2))
