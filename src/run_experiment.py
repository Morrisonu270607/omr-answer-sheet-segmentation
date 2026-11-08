"""Run the compact course-design experiment.

Protocol
--------
* 6 validation sheets select one parameter set per method.
* The selected parameters are frozen and evaluated once on the 6 test sheets.
* Metrics: pixel P/R/F1/IoU, bubble P/R/F1, answer accuracy, runtime.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from omr.evaluation import aggregate, evaluate_prediction, load_gt  # noqa: E402
from omr.segmentation import (  # noqa: E402
    predict_baseline_cc,
    predict_global_roi,
    predict_proposed,
    to_gray,
)

DATA = ROOT / "data"
RESULTS = ROOT / "results"


def load_rows() -> list[dict]:
    with (DATA / "index.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_cache(rows: list[dict]) -> list[dict]:
    cache = []
    for r in rows:
        gray = to_gray(Image.open(ROOT / r["image"]))
        gt = load_gt(ROOT / r["annotation"], ROOT / r["mask"])
        cache.append({**r, "gray": gray, "gt": gt})
    return cache


def score(rows: list[dict]) -> tuple:
    agg = aggregate(rows)
    return (agg["answer_accuracy"], agg["bubble_f1"], agg["pixel_f1"])


def evaluate_method(cache: list[dict], method: str, params: dict) -> list[dict]:
    out = []
    for item in cache:
        if method == "baseline_cc":
            pred = predict_baseline_cc(item["gray"], **params)
        elif method == "global_roi":
            pred = predict_global_roi(item["gray"], **params)
        elif method == "proposed":
            pred = predict_proposed(item["gray"], **params)
        else:
            raise ValueError(method)
        out.append(evaluate_prediction(pred, item["gt"]))
    return out


def tune(cache: list[dict]) -> dict:
    # The preferred setting is first, so ties keep the simpler / default value.
    cc_grid = [
        {"min_area": 110, "max_area": 1400},
        {"min_area": 90, "max_area": 1400},
        {"min_area": 130, "max_area": 1400},
        {"min_area": 110, "max_area": 1200},
    ]
    global_grid = [{"threshold": t} for t in (0.42, 0.38, 0.46, 0.34, 0.50)]
    proposed_grid = [
        {"delta": d, "threshold": t}
        for d in (10, 8, 12, 14)
        for t in (0.40, 0.36, 0.44, 0.32, 0.48)
    ]

    best = {}
    for method, grid in [
        ("baseline_cc", cc_grid),
        ("global_roi", global_grid),
        ("proposed", proposed_grid),
    ]:
        best_score = None
        best_params = None
        for params in grid:
            rows = evaluate_method(cache, method, params)
            s = score(rows)
            if best_score is None or s > best_score:
                best_score, best_params = s, params
        best[method] = {"params": best_params, "val": best_score}
        print(method, best_params, tuple(round(x, 4) for x in best_score))
    return best


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    rows = load_rows()
    val_rows = [r for r in rows if r["split"] == "val"]
    test_rows = [r for r in rows if r["split"] == "test"]
    val_cache = load_cache(val_rows)
    test_cache = load_cache(test_rows)

    tuned = tune(val_cache)
    (RESULTS / "tuned_params.json").write_text(
        json.dumps(tuned, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    methods = [
        ("baseline_cc", "基线：全局 Otsu + 连通域"),
        ("global_roi", "对照：全局 Otsu + 选项区域覆盖率"),
        ("proposed", "改进：局部自适应 + 形态学 + 覆盖率"),
    ]
    all_test_rows = []
    metric_rows = []
    for method, label in methods:
        params = tuned[method]["params"]
        test_metrics = evaluate_method(test_cache, method, params)
        for r in test_metrics:
            r["method"] = method
            r["method_label"] = label
        all_test_rows.extend(test_metrics)

        agg = aggregate(test_metrics)
        metric_rows.append({"method": method, "label": label, "split": "test", "group": "all", **agg})
        for group in ("clean", "light", "hard"):
            sub = [r for r in test_metrics if r["group"] == group]
            metric_rows.append(
                {"method": method, "label": label, "split": "test", "group": group, **aggregate(sub)}
            )
        print(
            f"{method:12s} test  pixelF1={agg['pixel_f1']:.4f}  "
            f"bubbleF1={agg['bubble_f1']:.4f}  answer={agg['answer_accuracy']:.4f}  "
            f"time={agg['time_ms']:.1f}ms"
        )

    fields = [
        "method",
        "label",
        "split",
        "group",
        "n_images",
        "pixel_precision",
        "pixel_recall",
        "pixel_f1",
        "pixel_iou",
        "bubble_precision",
        "bubble_recall",
        "bubble_f1",
        "answer_accuracy",
        "blank_rate",
        "time_ms",
    ]
    with (RESULTS / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in metric_rows:
            w.writerow({k: r.get(k, "") for k in fields})

    per_fields = [
        "method",
        "method_label",
        "id",
        "group",
        "pixel_precision",
        "pixel_recall",
        "pixel_f1",
        "pixel_iou",
        "bubble_precision",
        "bubble_recall",
        "bubble_f1",
        "answer_accuracy",
        "blank_count",
        "time_ms",
    ]
    with (RESULTS / "per_image.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=per_fields)
        w.writeheader()
        for r in all_test_rows:
            w.writerow({k: r.get(k, "") for k in per_fields})

    lines = ["# Experiment summary", "", "Test split only; parameters selected on the validation split.", ""]
    lines.append("| Method | Pixel F1 | Bubble F1 | Answer Acc. | Time (ms) |")
    lines.append("|---|---:|---:|---:|---:|")
    for m in metric_rows:
        if m["group"] != "all":
            continue
        lines.append(
            f"| {m['label']} | {m['pixel_f1']:.4f} | {m['bubble_f1']:.4f} | "
            f"{m['answer_accuracy']:.4f} | {m['time_ms']:.1f} |"
        )
    lines += ["", "## Per group (bubble F1 / answer accuracy)", ""]
    lines.append("| Method | clean | light | hard |")
    lines.append("|---|---:|---:|---:|")
    for method, label in methods:
        cells = []
        for group in ("clean", "light", "hard"):
            m = next(
                x for x in metric_rows if x["method"] == method and x["group"] == group
            )
            cells.append(f"{m['bubble_f1']:.3f} / {m['answer_accuracy']:.3f}")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    (RESULTS / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
