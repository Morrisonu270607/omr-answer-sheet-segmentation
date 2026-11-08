"""Classical segmentation baselines and the proposed OMR pipeline.

Everything here is NumPy + Pillow.  No OpenCV / scikit-image dependency is
required, which makes the project easy to run on a clean Windows machine.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw

from .config import (
    BUBBLES,
    BUBBLE_CX,
    BUBBLE_CY,
    BUBBLE_OPT,
    BUBBLE_Q,
    GT_R,
    HEIGHT,
    N_QUESTIONS,
    OPTIONS,
    ROI_R,
    WIDTH,
)


@dataclass
class Prediction:
    name: str
    mask: np.ndarray                 # uint8, 0/255: filled-option regions
    ink_mask: np.ndarray             # bool: thresholded ink (for visualisation)
    fills: np.ndarray                # (20, 4) coverage / score
    positives: np.ndarray            # (20, 4) bool
    answers: dict[int, str]
    candidates: int = 0
    time_ms: float = 0.0
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Basic image operations
# ---------------------------------------------------------------------------
def to_gray(img: Image.Image | np.ndarray) -> np.ndarray:
    if isinstance(img, Image.Image):
        return np.asarray(img.convert("L"), dtype=np.uint8)
    arr = np.asarray(img)
    if arr.ndim == 2:
        return arr.astype(np.uint8)
    return np.asarray(Image.fromarray(arr.astype(np.uint8)).convert("L"), dtype=np.uint8)


def otsu_threshold(gray: np.ndarray) -> tuple[int, float]:
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    total = hist.sum()
    if total == 0:
        return 127, 0.0
    omega = np.cumsum(hist)
    mu = np.cumsum(hist * np.arange(256))
    mu_t = mu[-1]
    valid = (omega > 0) & (omega < total)
    if not np.any(valid):
        return 127, 0.0
    denom = omega * (total - omega)
    sigma_b = np.zeros(256, dtype=np.float64)
    sigma_b[valid] = (mu_t * omega[valid] - mu[valid] * total) ** 2 / denom[valid]
    t = int(np.argmax(sigma_b))
    return t, float(sigma_b[t])


def box_blur(img: np.ndarray, k: int = 45) -> np.ndarray:
    """Mean filter using an integral image (O(HW), independent of k)."""
    if k % 2 == 0:
        k += 1
    p = k // 2
    a = np.pad(img.astype(np.float64), ((p, p), (p, p)), mode="reflect")
    ii = np.cumsum(np.cumsum(a, axis=0), axis=1)
    ii = np.pad(ii, ((1, 0), (1, 0)))
    out = ii[k:, k:] - ii[:-k, k:] - ii[k:, :-k] + ii[:-k, :-k]
    return out / float(k * k)


def _shift_bool(a: np.ndarray, dy: int, dx: int, fill: bool = False) -> np.ndarray:
    h, w = a.shape
    out = np.full_like(a, fill, dtype=bool)
    ys0, ys1 = max(0, dy), min(h, h + dy)
    xs0, xs1 = max(0, dx), min(w, w + dx)
    if ys0 >= ys1 or xs0 >= xs1:
        return out
    out[ys0:ys1, xs0:xs1] = a[ys0 - dy : ys1 - dy, xs0 - dx : xs1 - dx]
    return out


def dilate(a: np.ndarray, r: int = 1) -> np.ndarray:
    out = np.zeros_like(a, dtype=bool)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= _shift_bool(a, dy, dx, False)
    return out


def erode(a: np.ndarray, r: int = 1) -> np.ndarray:
    return ~dilate(~a, r)


def close(a: np.ndarray, r: int = 1) -> np.ndarray:
    return erode(dilate(a, r), r)


def open_(a: np.ndarray, r: int = 1) -> np.ndarray:
    return dilate(erode(a, r), r)


# ---------------------------------------------------------------------------
# Region-of-interest measurement
# ---------------------------------------------------------------------------
_DISK_CACHE: dict[int, np.ndarray] = {}


def disk(r: int) -> np.ndarray:
    if r not in _DISK_CACHE:
        yy, xx = np.ogrid[-r : r + 1, -r : r + 1]
        _DISK_CACHE[r] = (xx * xx + yy * yy) <= r * r
    return _DISK_CACHE[r]


def roi_fill(binary: np.ndarray, r: int = ROI_R) -> np.ndarray:
    d = disk(r)
    out = np.zeros((N_QUESTIONS, len(OPTIONS)), dtype=np.float64)
    for b in BUBBLES:
        q, oi, cx, cy = b["q"], b["oi"], b["cx"], b["cy"]
        sub = binary[cy - r : cy + r + 1, cx - r : cx + r + 1]
        out[q - 1, oi] = float(sub[d].mean())
    return out


def answers_from_fills(fills: np.ndarray, threshold: float) -> tuple[np.ndarray, dict[int, str]]:
    positives = fills >= threshold
    answers: dict[int, str] = {}
    for q in range(1, N_QUESTIONS + 1):
        row = fills[q - 1]
        if positives[q - 1].any():
            answers[q] = OPTIONS[int(np.argmax(row))]
        else:
            answers[q] = ""
    return positives, answers


def regions_from_positives(positives: np.ndarray, r: int = GT_R) -> np.ndarray:
    img = Image.new("L", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(img)
    for b in BUBBLES:
        if positives[b["q"] - 1, b["oi"]]:
            cx, cy = b["cx"], b["cy"]
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    return np.asarray(img, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Run-length connected components (fast enough in pure Python)
# ---------------------------------------------------------------------------
def components(mask: np.ndarray) -> list[dict]:
    """8-connected components using row runs + union-find.

    Returns a list of dictionaries with area, centroid, bounding box and
    bbox fill ratio.  This avoids a per-pixel Python BFS on a 1240x1754 image.
    """
    parent: list[int] = []
    stats: list[list[float]] = []  # area, sumx, sumy, minx, maxx, miny, maxy
    prev: list[tuple[int, int, int]] = []

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for y in range(mask.shape[0]):
        row = mask[y]
        if not row.any():
            prev = []
            continue
        d = np.diff(np.r_[False, row, False].astype(np.int8))
        starts = np.flatnonzero(d == 1)
        ends = np.flatnonzero(d == -1)
        cur: list[tuple[int, int, int]] = []
        for x0, x1 in zip(starts.tolist(), ends.tolist()):
            length = x1 - x0
            idx = len(stats)
            parent.append(idx)
            stats.append(
                [
                    float(length),
                    float((x0 + x1 - 1) * length / 2.0),
                    float(y * length),
                    float(x0),
                    float(x1 - 1),
                    float(y),
                    float(y),
                ]
            )
            cur.append((x0, x1, idx))

        # Union with overlapping runs in the previous row.
        i = j = 0
        while i < len(prev) and j < len(cur):
            px0, px1, pi = prev[i]
            cx0, cx1, ci = cur[j]
            if px1 <= cx0:
                i += 1
            elif cx1 <= px0:
                j += 1
            else:
                union(pi, ci)
                if px1 < cx1:
                    i += 1
                else:
                    j += 1
        prev = cur

    grouped: dict[int, list[float]] = {}
    for i, s in enumerate(stats):
        r = find(i)
        if r not in grouped:
            grouped[r] = [0.0, 0.0, 0.0, 1e18, -1.0, 1e18, -1.0]
        g = grouped[r]
        g[0] += s[0]
        g[1] += s[1]
        g[2] += s[2]
        g[3] = min(g[3], s[3])
        g[4] = max(g[4], s[4])
        g[5] = min(g[5], s[5])
        g[6] = max(g[6], s[6])

    out = []
    for area, sx, sy, x0, x1, y0, y1 in grouped.values():
        w = x1 - x0 + 1
        h = y1 - y0 + 1
        out.append(
            {
                "area": area,
                "cx": sx / area,
                "cy": sy / area,
                "x0": x0,
                "x1": x1,
                "y0": y0,
                "y1": y1,
                "w": w,
                "h": h,
                "bbox_fill": area / (w * h) if w * h else 0.0,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Methods
# ---------------------------------------------------------------------------
def predict_global_roi(gray: np.ndarray, threshold: float = 0.42) -> Prediction:
    t0 = time.perf_counter()
    t, _ = otsu_threshold(gray)
    ink = gray < t
    fills = roi_fill(ink)
    positives, answers = answers_from_fills(fills, threshold)
    mask = regions_from_positives(positives)
    return Prediction(
        name="global_roi",
        mask=mask,
        ink_mask=ink,
        fills=fills,
        positives=positives,
        answers=answers,
        candidates=int(positives.sum()),
        time_ms=(time.perf_counter() - t0) * 1000.0,
        meta={"otsu": t},
    )


def predict_proposed(
    gray: np.ndarray,
    delta: float = 10.0,
    threshold: float = 0.40,
    close_r: int = 1,
    open_r: int = 1,
    background_k: int = 45,
) -> Prediction:
    t0 = time.perf_counter()
    bg = box_blur(gray, background_k)
    diff = bg - gray.astype(np.float64)
    ink = diff > delta
    if close_r > 0:
        ink = close(ink, close_r)
    if open_r > 0:
        ink = open_(ink, open_r)
    fills = roi_fill(ink)
    positives, answers = answers_from_fills(fills, threshold)
    mask = regions_from_positives(positives)
    return Prediction(
        name="proposed",
        mask=mask,
        ink_mask=ink,
        fills=fills,
        positives=positives,
        answers=answers,
        candidates=int(positives.sum()),
        time_ms=(time.perf_counter() - t0) * 1000.0,
        meta={"delta": delta, "threshold": threshold, "background_k": background_k},
    )


def predict_proposed_no_morph(
    gray: np.ndarray, delta: float = 10.0, threshold: float = 0.40
) -> Prediction:
    p = predict_proposed(gray, delta=delta, threshold=threshold, close_r=0, open_r=0)
    p.name = "proposed_no_morph"
    return p


def predict_baseline_cc(
    gray: np.ndarray,
    min_area: int = 110,
    max_area: int = 1400,
    match_radius: float = 26.0,
) -> Prediction:
    """Naive baseline: global Otsu + connected components + area/aspect filter."""
    t0 = time.perf_counter()
    t, _ = otsu_threshold(gray)
    ink = gray < t
    comps = components(ink)

    fills = np.zeros((N_QUESTIONS, len(OPTIONS)), dtype=np.float64)
    positives = np.zeros_like(fills, dtype=bool)
    best_area = np.zeros_like(fills, dtype=np.float64)
    mask_img = Image.new("L", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(mask_img)
    n_candidates = 0

    for c in comps:
        area = c["area"]
        w, h = c["w"], c["h"]
        if not (min_area <= area <= max_area):
            continue
        if not (8 <= w <= 58 and 8 <= h <= 58):
            continue
        aspect = w / h
        if not (0.40 <= aspect <= 2.50):
            continue
        if c["bbox_fill"] < 0.12:
            continue

        n_candidates += 1
        # The component is a detection; draw its fitted disk for the output mask.
        cx, cy = c["cx"], c["cy"]
        draw.ellipse([cx - GT_R, cy - GT_R, cx + GT_R, cy + GT_R], fill=255)

        # Match to the nearest bubble centre for answer assignment.
        best_i, best_d = -1, 1e9
        for i, (bx, by) in enumerate(zip(BUBBLE_CX, BUBBLE_CY)):
            d = (bx - cx) ** 2 + (by - cy) ** 2
            if d < best_d:
                best_d, best_i = d, i
        if best_d <= match_radius**2 and best_i >= 0:
            q = BUBBLE_Q[best_i]
            oi = OPTIONS.index(BUBBLE_OPT[best_i])
            positives[q - 1, oi] = True
            if area > best_area[q - 1, oi]:
                best_area[q - 1, oi] = area
                fills[q - 1, oi] = area

    answers: dict[int, str] = {}
    for q in range(1, N_QUESTIONS + 1):
        if positives[q - 1].any():
            answers[q] = OPTIONS[int(np.argmax(best_area[q - 1]))]
        else:
            answers[q] = ""

    return Prediction(
        name="baseline_cc",
        mask=np.asarray(mask_img, dtype=np.uint8),
        ink_mask=ink,
        fills=fills,
        positives=positives,
        answers=answers,
        candidates=n_candidates,
        time_ms=(time.perf_counter() - t0) * 1000.0,
        meta={"otsu": t, "n_components": len(comps)},
    )
