from __future__ import annotations

from collections import defaultdict
from math import isfinite
from statistics import mean, median, pstdev


MIN_OBSERVATIONS = 3


def _safe_scale(values: list[float], method: str) -> tuple[float, float, str]:
    """Return center, scale, and center_method for one judge/criterion."""
    if method == "zscore":
        center = mean(values)
        scale = pstdev(values)
        center_method = "mean"
    elif method == "robust_zscore":
        center = median(values)
        deviations = [abs(value - center) for value in values]
        mad = median(deviations)
        scale = 1.4826 * mad
        center_method = "median"
        if scale <= 1e-12:
            scale = pstdev(values)
            center_method = "median_fallback_std"
    else:
        raise ValueError("Unsupported normalization method")

    if scale <= 1e-12:
        scale = 1.0
        center_method = f"{center_method}_unit_scale"

    return float(center), float(scale), center_method


def _global_stats(values: list[float], method: str) -> tuple[float, float]:
    if method == "zscore":
        center = mean(values)
        scale = pstdev(values)
    else:
        center = median(values)
        mad = median([abs(v - center) for v in values])
        scale = 1.4826 * mad
        if scale <= 1e-12:
            scale = pstdev(values)

    if scale <= 1e-12:
        scale = 1.0
    return float(center), float(scale)


def normalize_by_judge_criterion(
    rows: list[dict],
    method: str = "robust_zscore",
    min_observations: int = MIN_OBSERVATIONS,
    clip: bool = True,
) -> dict:
    """Normalize evaluator scales separately for each judge/criterion.

    A judge with fewer than min_observations for a criterion is not given an
    invented calibration. Its original score is preserved and the result
    marks that group as `insufficient_data`.
    """
    if method not in {"zscore", "robust_zscore"}:
        raise ValueError("Unsupported normalization method")
    if min_observations < 2:
        raise ValueError("min_observations must be at least 2")
    if not rows:
        return {
            "method": method,
            "min_observations": min_observations,
            "clip": clip,
            "scores": [],
            "groups": {},
            "global_criteria": {},
            "diagnostics": {"row_count": 0, "normalized_row_count": 0, "insufficient_group_count": 0},
        }

    by_criterion: dict[str, list[float]] = defaultdict(list)
    by_group: dict[tuple[str, str], list[float]] = defaultdict(list)

    for row in rows:
        score = float(row["score"])
        if not isfinite(score):
            raise ValueError("Scores must be finite numbers")
        criterion_id = str(row["criterion_id"])
        judge_id = str(row["judge_id"])
        by_criterion[criterion_id].append(score)
        by_group[(judge_id, criterion_id)].append(score)

    global_stats: dict[str, dict] = {}
    for criterion_id, values in by_criterion.items():
        center, scale = _global_stats(values, method)
        global_stats[criterion_id] = {
            "center": center,
            "scale": scale,
            "minimum": min(values),
            "maximum": max(values),
            "count": len(values),
        }

    group_stats: dict[str, dict] = {}
    for (judge_id, criterion_id), values in by_group.items():
        key = f"{judge_id}:{criterion_id}"
        global_stat = global_stats[criterion_id]
        if len(values) < min_observations:
            group_stats[key] = {
                "judge_id": judge_id,
                "criterion_id": criterion_id,
                "count": len(values),
                "status": "insufficient_data",
                "center": None,
                "scale": None,
                "center_method": None,
                "severity_shift": None,
            }
            continue

        center, scale, center_method = _safe_scale(values, method)
        group_stats[key] = {
            "judge_id": judge_id,
            "criterion_id": criterion_id,
            "count": len(values),
            "status": "calibrated",
            "center": center,
            "scale": scale,
            "center_method": center_method,
            "severity_shift": center - global_stat["center"],
        }

    normalized = []
    normalized_count = 0
    insufficient_groups = 0

    for row in rows:
        judge_id = str(row["judge_id"])
        criterion_id = str(row["criterion_id"])
        group = group_stats[f"{judge_id}:{criterion_id}"]
        global_stat = global_stats[criterion_id]
        value = float(row["score"])

        out = dict(row)
        if group["status"] != "calibrated":
            out["normalized_score"] = value
            out["normalization_status"] = "insufficient_data"
            insufficient_groups += 1
        else:
            z = (value - group["center"]) / group["scale"]
            transformed = global_stat["center"] + z * global_stat["scale"]
            if clip:
                transformed = max(global_stat["minimum"], min(transformed, global_stat["maximum"]))
            out["normalized_score"] = float(transformed)
            out["normalization_status"] = "normalized"
            normalized_count += 1

        normalized.append(out)

    return {
        "method": method,
        "min_observations": min_observations,
        "clip": clip,
        "scores": normalized,
        "groups": group_stats,
        "global_criteria": global_stats,
        "diagnostics": {
            "row_count": len(rows),
            "normalized_row_count": normalized_count,
            "insufficient_group_count": len(
                [x for x in group_stats.values() if x["status"] == "insufficient_data"]
            ),
            "insufficient_row_count": sum(
                1 for x in normalized if x["normalization_status"] == "insufficient_data"
            ),
        },
    }


def calibration_metrics(
    rows: list[dict],
    anchors: list[dict] | None = None,
    min_observations: int = MIN_OBSERVATIONS,
) -> dict:
    """Produce criterion-specific evaluator calibration diagnostics."""
    if min_observations < 2:
        raise ValueError("min_observations must be at least 2")

    by_group: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_criterion: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        value = float(row["score"])
        judge_id = str(row["judge_id"])
        criterion_id = str(row["criterion_id"])
        by_group[(judge_id, criterion_id)].append(value)
        by_criterion[criterion_id].append(value)

    metrics = []
    for (judge_id, criterion_id), values in sorted(by_group.items()):
        center = median(values)
        dispersion = pstdev(values) if len(values) > 1 else 0.0
        global_values = by_criterion[criterion_id]
        global_center = median(global_values)
        metrics.append(
            {
                "judge_id": judge_id,
                "criterion_id": criterion_id,
                "observations": len(values),
                "status": "ready" if len(values) >= min_observations else "insufficient_data",
                "median": float(center),
                "mean": float(mean(values)),
                "std_dev": float(dispersion),
                "global_median": float(global_center),
                "severity_shift": float(center - global_center),
                "minimum": float(min(values)),
                "maximum": float(max(values)),
            }
        )

    anchor_results = []
    if anchors:
        target_lookup = {
            (str(anchor["submission_id"]), str(anchor["criterion_id"])): (
                float(anchor["target_score"]),
                float(anchor.get("tolerance", 0.5)),
            )
            for anchor in anchors
        }
        for row in rows:
            key = (str(row["submission_id"]), str(row["criterion_id"]))
            if key not in target_lookup:
                continue
            target, tolerance = target_lookup[key]
            observed = float(row["score"])
            deviation = observed - target
            anchor_results.append(
                {
                    "judge_id": str(row["judge_id"]),
                    "submission_id": str(row["submission_id"]),
                    "criterion_id": str(row["criterion_id"]),
                    "observed": observed,
                    "target": target,
                    "tolerance": tolerance,
                    "deviation": deviation,
                    "outside_tolerance": abs(deviation) > tolerance,
                }
            )

    return {
        "min_observations": min_observations,
        "groups": metrics,
        "anchor_checks": anchor_results,
        "diagnostics": {
            "group_count": len(metrics),
            "ready_group_count": sum(1 for x in metrics if x["status"] == "ready"),
            "insufficient_group_count": sum(1 for x in metrics if x["status"] != "ready"),
            "anchor_check_count": len(anchor_results),
            "anchor_outside_tolerance_count": sum(
                1 for x in anchor_results if x["outside_tolerance"]
            ),
        },
    }


def drift_metrics(rows: list[dict], min_observations: int = MIN_OBSERVATIONS) -> dict:
    """Estimate linear score drift by judge/criterion in queue order."""
    if min_observations < 2:
        raise ValueError("min_observations must be at least 2")

    by_group: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        by_group[(str(row["judge_id"]), str(row["criterion_id"]))].append(row)

    results = []
    for (judge_id, criterion_id), group_rows in sorted(by_group.items()):
        ordered = sorted(
            group_rows,
            key=lambda r: (
                int(r.get("queue_position", 0)),
                str(r.get("submitted_at", "")),
            ),
        )
        scores = [float(r["score"]) for r in ordered]
        n = len(scores)
        if n < min_observations:
            results.append(
                {
                    "judge_id": judge_id,
                    "criterion_id": criterion_id,
                    "observations": n,
                    "status": "insufficient_data",
                    "slope_per_position": None,
                    "first_mean": None,
                    "last_mean": None,
                    "drift_range": None,
                }
            )
            continue

        positions = [
            int(r.get("queue_position", index + 1)) or index + 1
            for index, r in enumerate(ordered)
        ]
        x_bar = mean(positions)
        y_bar = mean(scores)
        denominator = sum((x - x_bar) ** 2 for x in positions)
        slope = 0.0 if denominator <= 1e-12 else sum(
            (x - x_bar) * (y - y_bar) for x, y in zip(positions, scores)
        ) / denominator

        split = max(1, n // 3)
        first = mean(scores[:split])
        last = mean(scores[-split:])

        results.append(
            {
                "judge_id": judge_id,
                "criterion_id": criterion_id,
                "observations": n,
                "status": "ready",
                "slope_per_position": float(slope),
                "first_mean": float(first),
                "last_mean": float(last),
                "drift_range": float(max(scores) - min(scores)),
                "early_late_mean_delta": float(last - first),
            }
        )

    return {
        "groups": results,
        "diagnostics": {
            "group_count": len(results),
            "ready_group_count": sum(1 for x in results if x["status"] == "ready"),
            "insufficient_group_count": sum(1 for x in results if x["status"] != "ready"),
        },
    }
