from __future__ import annotations

import itertools
import math
from collections import defaultdict
from copy import deepcopy
from typing import Iterable

import numpy as np


def _group_values(rows, key_fn):
    grouped = defaultdict(list)
    for row in rows:
        grouped[key_fn(row)].append(float(row["score"]))
    return grouped


def normalize_scores(rows: list[dict], method: str = "robust_zscore") -> dict:
    if method not in {"zscore", "robust_zscore"}:
        raise ValueError("Unsupported normalization method")
    if not rows:
        return {"method": method, "scores": []}

    all_scores = np.asarray([float(r["score"]) for r in rows], dtype=float)
    global_mean = float(all_scores.mean())
    global_std = float(all_scores.std(ddof=0)) or 1.0

    by_judge = _group_values(rows, lambda r: r["judge_id"])
    params = {}
    for judge_id, values in by_judge.items():
        arr = np.asarray(values, dtype=float)
        if method == "zscore":
            center = float(arr.mean())
            scale = float(arr.std(ddof=0)) or 1.0
        else:
            center = float(np.median(arr))
            mad = float(np.median(np.abs(arr - center)))
            scale = 1.4826 * mad
            if scale <= 1e-12:
                scale = float(arr.std(ddof=0)) or 1.0
        params[judge_id] = {"center": center, "scale": scale}

    out = []
    for row in rows:
        p = params[row["judge_id"]]
        z = (float(row["score"]) - p["center"]) / p["scale"]
        normalized = global_mean + z * global_std
        normalized = max(min(normalized, float(all_scores.max())), float(all_scores.min()))
        new_row = dict(row)
        new_row["normalized_score"] = float(normalized)
        out.append(new_row)

    return {
        "method": method,
        "scores": out,
        "judge_parameters": params,
        "global_mean": global_mean,
        "global_std": global_std,
    }


def aggregate_rankings(rows: list[dict], criterion_weights: dict[str, float], score_key: str = "normalized_score") -> list[dict]:
    if not rows:
        return []

    weight_sum = float(sum(criterion_weights.values()))
    if weight_sum <= 0:
        raise ValueError("Criterion weights must sum to a positive value")

    by_evaluation = defaultdict(list)
    for row in rows:
        by_evaluation[(row["judge_id"], row["submission_id"])].append(row)

    submission_judge_scores = defaultdict(list)
    for (judge_id, submission_id), eval_rows in by_evaluation.items():
        numerator = 0.0
        denom = 0.0
        for row in eval_rows:
            weight = float(criterion_weights.get(str(row["criterion_id"]), 0.0))
            if weight <= 0:
                continue
            numerator += weight * float(row.get(score_key, row["score"]))
            denom += weight
        if denom:
            submission_judge_scores[submission_id].append(numerator / denom)

    result = []
    for submission_id, scores in submission_judge_scores.items():
        values = np.asarray(scores, dtype=float)
        result.append(
            {
                "submission_id": submission_id,
                "score": float(values.mean()),
                "judge_count": int(values.size),
                "std_dev": float(values.std(ddof=0)),
            }
        )

    return sorted(result, key=lambda x: (-x["score"], str(x["submission_id"])))


def _ranking_map(ranking: list[dict]) -> dict[str, int]:
    return {str(row["submission_id"]): index + 1 for index, row in enumerate(ranking)}


def bootstrap_stability(rows: list[dict], criterion_weights: dict[str, float], iterations: int = 500, seed: int | None = None) -> dict:
    judges = sorted({str(row["judge_id"]) for row in rows})
    submissions = sorted({str(row["submission_id"]) for row in rows})
    if not judges or not submissions:
        return {"iterations": 0, "rank1_frequency": {}, "rank_distribution": {}}

    rng = np.random.default_rng(seed)
    by_judge = defaultdict(list)
    for row in rows:
        by_judge[str(row["judge_id"])].append(row)

    rank1 = defaultdict(int)
    rank_distribution = defaultdict(lambda: defaultdict(int))

    for _ in range(iterations):
        sampled_judges = rng.choice(judges, size=len(judges), replace=True)
        sampled_rows = []
        for judge_id in sampled_judges:
            sampled_rows.extend(deepcopy(by_judge[str(judge_id)]))
        normalized = normalize_scores(sampled_rows, "robust_zscore")["scores"]
        ranking = aggregate_rankings(normalized, criterion_weights)
        for rank, item in enumerate(ranking, start=1):
            sid = str(item["submission_id"])
            rank_distribution[sid][rank] += 1
            if rank == 1:
                rank1[sid] += 1

    total = float(iterations)
    rank1_frequency = {sid: count / total for sid, count in rank1.items()}
    distribution = {
        sid: {str(rank): count / total for rank, count in ranks.items()}
        for sid, ranks in rank_distribution.items()
    }
    return {
        "iterations": iterations,
        "rank1_frequency": rank1_frequency,
        "rank_distribution": distribution,
    }


def influence_analysis(rows: list[dict], criterion_weights: dict[str, float]) -> dict:
    baseline = aggregate_rankings(normalize_scores(rows)["scores"], criterion_weights)
    if not baseline:
        return {"baseline": [], "judges": []}
    base_map = _ranking_map(baseline)
    winner = str(baseline[0]["submission_id"])
    judges = sorted({str(row["judge_id"]) for row in rows})
    results = []

    for judge_id in judges:
        remaining = [r for r in rows if str(r["judge_id"]) != judge_id]
        ranking = aggregate_rankings(normalize_scores(remaining)["scores"], criterion_weights)
        current_map = _ranking_map(ranking)
        max_movement = 0
        for sid, base_rank in base_map.items():
            if sid in current_map:
                max_movement = max(max_movement, abs(base_rank - current_map[sid]))
        new_winner = str(ranking[0]["submission_id"]) if ranking else None
        results.append(
            {
                "judge_id": judge_id,
                "winner_changed": new_winner != winner,
                "new_winner": new_winner,
                "max_rank_movement": int(max_movement),
                "evaluations_removed": len(rows) - len(remaining),
            }
        )

    return {
        "baseline_winner": winner,
        "baseline": baseline,
        "judges": sorted(results, key=lambda x: (-x["max_rank_movement"], x["judge_id"])),
    }


def minimum_flip_set(rows: list[dict], criterion_weights: dict[str, float], max_coalition: int = 3) -> dict:
    judges = sorted({str(row["judge_id"]) for row in rows})
    baseline = aggregate_rankings(normalize_scores(rows)["scores"], criterion_weights)
    if not baseline:
        return {"minimum_size": None, "coalition": None, "baseline_winner": None, "tested_sizes": []}
    winner = str(baseline[0]["submission_id"])
    tested = []

    for size in range(1, min(max_coalition, len(judges)) + 1):
        tested.append(size)
        for coalition in itertools.combinations(judges, size):
            removed = set(coalition)
            remaining = [r for r in rows if str(r["judge_id"]) not in removed]
            ranking = aggregate_rankings(normalize_scores(remaining)["scores"], criterion_weights)
            if ranking and str(ranking[0]["submission_id"]) != winner:
                return {
                    "baseline_winner": winner,
                    "minimum_size": size,
                    "coalition": list(coalition),
                    "new_winner": str(ranking[0]["submission_id"]),
                    "tested_sizes": tested,
                    "model": "judge-removal coalition",
                }

    return {
        "baseline_winner": winner,
        "minimum_size": None,
        "coalition": None,
        "new_winner": None,
        "tested_sizes": tested,
        "model": "judge-removal coalition",
    }


def rubric_sensitivity(rows: list[dict], criterion_weights: dict[str, float], delta: float = 0.05) -> dict:
    keys = list(criterion_weights.keys())
    baseline = aggregate_rankings(normalize_scores(rows)["scores"], criterion_weights)
    baseline_winner = str(baseline[0]["submission_id"]) if baseline else None
    scenarios = []

    for target in keys:
        for direction in ("increase", "decrease"):
            weights = dict(criterion_weights)
            if direction == "increase":
                available = [k for k in keys if k != target and weights[k] > 0]
                if not available:
                    continue
                take = min(delta, sum(weights[k] for k in available))
                weights[target] += take
                remaining = sum(weights[k] for k in available)
                for k in available:
                    weights[k] -= take * (weights[k] / remaining)
            else:
                take = min(delta, weights[target] - 1e-6)
                if take <= 0:
                    continue
                weights[target] -= take
                others = [k for k in keys if k != target]
                if others:
                    total = sum(weights[k] for k in others)
                    for k in others:
                        weights[k] += take * (weights[k] / total)

            ranking = aggregate_rankings(normalize_scores(rows)["scores"], weights)
            new_winner = str(ranking[0]["submission_id"]) if ranking else None
            scenarios.append(
                {
                    "criterion_id": target,
                    "direction": direction,
                    "winner": new_winner,
                    "winner_changed": new_winner != baseline_winner,
                    "weights": weights,
                }
            )

    return {
        "baseline_winner": baseline_winner,
        "delta": delta,
        "scenarios": scenarios,
        "winner_change_count": sum(1 for s in scenarios if s["winner_changed"]),
    }


def score_drift(rows: list[dict]) -> dict:
    ordered = sorted(rows, key=lambda r: (r.get("queue_position", 0), r.get("submitted_at", "")))
    if len(ordered) < 4:
        return {"available": False, "reason": "Not enough evaluations"}
    positions = np.asarray([float(r.get("queue_position", i + 1)) for i, r in enumerate(ordered)], dtype=float)
    scores = np.asarray([float(r["score"]) for r in ordered], dtype=float)
    slope = float(np.polyfit(positions, scores, 1)[0]) if len(ordered) >= 2 else 0.0
    q = np.array_split(scores, 4)
    means = [float(x.mean()) for x in q if len(x)]
    return {
        "available": True,
        "slope_per_position": slope,
        "quartile_means": means,
        "drift_range": max(means) - min(means) if means else 0.0,
    }


def calibration_analysis(rows: list[dict], anchors: list[dict]) -> dict:
    anchor_lookup = {(str(a["submission_id"]), str(a["criterion_id"])): (float(a["target_score"]), float(a.get("tolerance", 0.5))) for a in anchors}
    deviations = defaultdict(list)
    for row in rows:
        key = (str(row["submission_id"]), str(row["criterion_id"]))
        if key in anchor_lookup:
            target, tolerance = anchor_lookup[key]
            deviations[str(row["judge_id"])].append(
                {
                    "observed": float(row["score"]),
                    "target": target,
                    "deviation": float(row["score"]) - target,
                    "outside_tolerance": abs(float(row["score"]) - target) > tolerance,
                }
            )
    result = {}
    for judge_id, values in deviations.items():
        result[judge_id] = {
            "anchor_count": len(values),
            "mean_deviation": float(np.mean([v["deviation"] for v in values])),
            "outside_tolerance_count": sum(1 for v in values if v["outside_tolerance"]),
        }
    return result


def blindness_scan(submission: dict, identity_strings: Iterable[str]) -> dict:
    text_fields = [submission.get("name", ""), submission.get("tagline", ""), submission.get("description", ""), submission.get("repository_url", ""), submission.get("live_url", ""), submission.get("demo_video_url", "")]
    text = "\n".join(str(x) for x in text_fields).lower()
    matches = sorted({s for s in identity_strings if s and str(s).lower() in text})
    return {
        "leakage_detected": bool(matches),
        "matches": matches,
    }
