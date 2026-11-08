"""Metrics for pixel segmentation, bubble detection and answer recognition."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from .config import N_QUESTIONS, OPTIONS, ROOT
from .segmentation import Prediction


def load_gt(annotation_path: str | Path, mask_path: str | Path) -> dict:
    ann = json.loads(Path(annotation_path).read_text(encoding="utf-8"))
    mask = np.asarray(Image.open(mask_path).convert("L"), dtype=np.uint8) > 127
    positives = np.zeros((N_QUESTIONS, len(OPTIONS)), dtype=bool)
    answers: dict[int, str] = {}
    for q_s, opt in ann["answers"].items():
        q = int(q_s)
        answers[q] = opt
        positives[q - 1, OPTIONS.index(opt)] = True
    return {
        "id": ann["id"],
        "group": ann["group"],
        "mask": mask,
        "positives": positives,
        "answers": answers,
        "annotation": ann,
    }


def pixel_metrics(pred_mask: np.ndarray, gt_mask: np.ndarray) -> dict:
    pred = pred_mask > 127
    gt = gt_mask.astype(bool) if gt_mask.dtype == bool else gt_mask > 127
    tp = int(np.logical_and(pred, gt).sum())
    fp = int(np.logical_and(pred, ~gt).sum())
    fn = int(np.logical_and(~pred, gt).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    union = tp + fp + fn
    iou = tp / union if union else 1.0
    return {
        "pixel_tp": tp,
        "pixel_fp": fp,
        "pixel_fn": fn,
        "pixel_precision": precision,
        "pixel_recall": recall,
        "pixel_f1": f1,
        "pixel_iou": iou,
    }


def evaluate_prediction(pred: Prediction, gt: dict) -> dict:
    pixel = pixel_metrics(pred.mask, gt["mask"])
    p = pred.positives.ravel()
    g = gt["positives"].ravel()
    tp = int(np.logical_and(p, g).sum())
    fp = int(np.logical_and(p, ~g).sum())
    fn = int(np.logical_and(~p, g).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    correct = sum(1 for q in range(1, N_QUESTIONS + 1) if pred.answers.get(q, "") == gt["answers"][q])
    blank = sum(1 for q in range(1, N_QUESTIONS + 1) if not pred.answers.get(q, ""))
    return {
        "id": gt["id"],
        "group": gt["group"],
        **pixel,
        "bubble_tp": tp,
        "bubble_fp": fp,
        "bubble_fn": fn,
        "bubble_precision": precision,
        "bubble_recall": recall,
        "bubble_f1": f1,
        "answer_correct": correct,
        "answer_accuracy": correct / N_QUESTIONS,
        "blank_count": blank,
        "pred_positive": int(p.sum()),
        "gt_positive": int(g.sum()),
        "time_ms": pred.time_ms,
        "candidates": pred.candidates,
    }


def aggregate(rows: list[dict]) -> dict:
    if not rows:
        return {}
    out = {
        "n_images": len(rows),
        "pixel_precision": float(np.mean([r["pixel_precision"] for r in rows])),
        "pixel_recall": float(np.mean([r["pixel_recall"] for r in rows])),
        "pixel_f1": float(np.mean([r["pixel_f1"] for r in rows])),
        "pixel_iou": float(np.mean([r["pixel_iou"] for r in rows])),
        "bubble_precision": float(
            sum(r["bubble_tp"] for r in rows)
            / max(1, sum(r["bubble_tp"] + r["bubble_fp"] for r in rows))
        ),
        "bubble_recall": float(
            sum(r["bubble_tp"] for r in rows)
            / max(1, sum(r["bubble_tp"] + r["bubble_fn"] for r in rows))
        ),
        "answer_accuracy": float(np.mean([r["answer_accuracy"] for r in rows])),
        "blank_rate": float(np.mean([r["blank_count"] / N_QUESTIONS for r in rows])),
        "time_ms": float(np.mean([r["time_ms"] for r in rows])),
    }
    bp = out["bubble_precision"]
    br = out["bubble_recall"]
    out["bubble_f1"] = 2 * bp * br / (bp + br) if bp + br else 0.0
    return out
