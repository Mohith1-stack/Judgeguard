from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import numpy as np

from app.engine.normalization import normalize_by_judge_criterion


def _population_std(values: Iterable[float]) -> float:
    values = [float(value) for value in values]
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5


def _judge_project_scores(
    normalized_rows: list[dict],
    criterion_weights: dict[str, float],
) -> dict[str, dict[str, float]]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in normalized_rows:
        grouped[(str(row["judge_id"]), str(row["submission_id"]))].append(row)

    result: dict[str, dict[str, float]] = defaultdict(dict)
    for (judge_id, submission_id), rows in grouped.items():
        numerator = 0.0
        denominator = 0.0
        for row in rows:
            weight = float(criterion_weights.get(str(row["criterion_id"]), 0.0))
            if weight <= 0:
                continue
            numerator += weight * float(row.get("normalized_score", row["score"]))
            denominator += weight
        if denominator > 0:
            result[judge_id][submission_id] = numerator / denominator

    return {judge: dict(projects) for judge, projects in result.items()}


def _rank_from_project_scores(
    project_scores: dict[str, list[float]],
) -> list[dict]:
    ranking = []
    for submission_id, values in project_scores.items():
        clean = [float(value) for value in values]
        if not clean:
            continue
        ranking.append(
            {
                "submission_id": submission_id,
                "score": float(sum(clean) / len(clean)),
                "judge_count": len(clean),
                "std_dev": float(_population_std(clean)),
            }
        )
    return sorted(ranking, key=lambda item: (-item["score"], str(item["submission_id"])))


def _baseline_ranking(judge_scores: dict[str, dict[str, float]]) -> list[dict]:
    by_submission: dict[str, list[float]] = defaultdict(list)
    for projects in judge_scores.values():
        for submission_id, score in projects.items():
            by_submission[submission_id].append(float(score))
    return _rank_from_project_scores(by_submission)


def _rank_map(ranking: list[dict]) -> dict[str, int]:
    return {str(item["submission_id"]): index + 1 for index, item in enumerate(ranking)}


def _winner_and_margin(ranking: list[dict]) -> tuple[str | None, float]:
    if not ranking:
        return None, 0.0
    if len(ranking) == 1:
        return str(ranking[0]["submission_id"]), 0.0
    return (
        str(ranking[0]["submission_id"]),
        float(ranking[0]["score"] - ranking[1]["score"]),
    )


def _panel_sample_ranking(
    judge_scores: dict[str, dict[str, float]],
    sampled_judges: np.ndarray,
) -> list[dict]:
    project_scores: dict[str, list[float]] = defaultdict(list)
    for judge_id in sampled_judges.tolist():
        for submission_id, score in judge_scores[str(judge_id)].items():
            project_scores[str(submission_id)].append(float(score))
    return _rank_from_project_scores(project_scores)


def _pairwise_stats(
    ranking: list[dict],
    candidate_ids: list[str],
    wins: dict[tuple[str, str], int],
    comparisons: dict[tuple[str, str], int],
) -> None:
    score_lookup = {str(item["submission_id"]): float(item["score"]) for item in ranking}
    present = [submission_id for submission_id in candidate_ids if submission_id in score_lookup]
    for index, left in enumerate(present):
        for right in present[index + 1 :]:
            left_score = score_lookup[left]
            right_score = score_lookup[right]
            if left_score == right_score:
                continue
            pair = (left, right)
            comparisons[pair] += 1
            if left_score > right_score:
                wins[pair] += 1


def bootstrap_panel_stability(
    normalized_rows: list[dict],
    criterion_weights: dict[str, float],
    *,
    iterations: int = 1000,
    seed: int | None = None,
    top_k: int = 3,
    pairwise_top_n: int = 5,
) -> dict:
    """Bootstrap whole judges with replacement while freezing normalization.

    Each sampled judge contributes their complete observed project panel. Rank
    probabilities are conditional on a project appearing in the sampled panel;
    `coverage_frequency` reports how often that happened.
    """
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    if pairwise_top_n < 2:
        raise ValueError("pairwise_top_n must be at least 2")

    judge_scores = _judge_project_scores(normalized_rows, criterion_weights)
    judges = sorted(judge_scores)
    baseline = _baseline_ranking(judge_scores)
    if not judges or not baseline:
        return {
            "model": "frozen-normalization-panel-bootstrap-v1",
            "iterations": 0,
            "seed": seed,
            "baseline": {"ranking": baseline, "winner": baseline[0]["submission_id"] if baseline else None},
            "rank1_frequency": {},
            "rank_distribution": {},
            "top_k_frequency": {},
            "pairwise_win_probability": {},
            "coverage_frequency": {},
            "rank_observations": {},
            "diagnostics": {"judge_count": len(judges), "submission_count": len(baseline)},
        }

    rng = np.random.default_rng(seed)
    rank1_count: dict[str, int] = defaultdict(int)
    rank_observations: dict[str, int] = defaultdict(int)
    rank_sum: dict[str, float] = defaultdict(float)
    rank_sq_sum: dict[str, float] = defaultdict(float)
    rank_distribution_count: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    top_k_count: dict[str, int] = defaultdict(int)
    pairwise_wins: dict[tuple[str, str], int] = defaultdict(int)
    pairwise_comparisons: dict[tuple[str, str], int] = defaultdict(int)

    candidate_ids = [str(item["submission_id"]) for item in baseline[: max(2, pairwise_top_n)]]

    for _ in range(iterations):
        sampled_judges = rng.choice(judges, size=len(judges), replace=True)
        ranking = _panel_sample_ranking(judge_scores, sampled_judges)
        for rank, item in enumerate(ranking, start=1):
            submission_id = str(item["submission_id"])
            rank_observations[submission_id] += 1
            rank_sum[submission_id] += rank
            rank_sq_sum[submission_id] += rank * rank
            rank_distribution_count[submission_id][rank] += 1
            if rank == 1:
                rank1_count[submission_id] += 1
            if rank <= top_k:
                top_k_count[submission_id] += 1
        _pairwise_stats(ranking, candidate_ids, pairwise_wins, pairwise_comparisons)

    rank1_frequency = {
        submission_id: rank1_count[submission_id] / rank_observations[submission_id]
        for submission_id in sorted(rank_observations)
    }
    coverage_frequency = {
        submission_id: rank_observations[submission_id] / float(iterations)
        for submission_id in sorted(rank_observations)
    }
    top_k_frequency = {
        submission_id: top_k_count[submission_id] / rank_observations[submission_id]
        for submission_id in sorted(rank_observations)
    }
    rank_distribution = {
        submission_id: {
            str(rank): count / rank_observations[submission_id]
            for rank, count in sorted(rank_distribution_count[submission_id].items())
        }
        for submission_id in sorted(rank_observations)
    }
    mean_rank = {
        submission_id: rank_sum[submission_id] / rank_observations[submission_id]
        for submission_id in sorted(rank_observations)
    }
    rank_std_dev = {
        submission_id: max(
            0.0,
            (rank_sq_sum[submission_id] / rank_observations[submission_id])
            - (mean_rank[submission_id] ** 2),
        ) ** 0.5
        for submission_id in sorted(rank_observations)
    }

    pairwise_win_probability = {}
    for (left, right), count in sorted(pairwise_comparisons.items()):
        wins_for_left = pairwise_wins.get((left, right), 0)
        pairwise_win_probability[f"{left}|{right}"] = {
            "left_submission_id": left,
            "right_submission_id": right,
            "left_win_probability": wins_for_left / count,
            "comparison_count": count,
        }

    return {
        "model": "frozen-normalization-panel-bootstrap-v1",
        "iterations": iterations,
        "seed": seed,
        "baseline": {
            "winner": str(baseline[0]["submission_id"]),
            "winner_margin": float(
                baseline[0]["score"] - baseline[1]["score"]
            ) if len(baseline) > 1 else 0.0,
            "ranking": baseline,
        },
        "rank1_frequency": rank1_frequency,
        "rank_distribution": rank_distribution,
        "top_k": top_k,
        "top_k_frequency": top_k_frequency,
        "mean_rank": mean_rank,
        "rank_std_dev": rank_std_dev,
        "coverage_frequency": coverage_frequency,
        "rank_observations": dict(sorted(rank_observations.items())),
        "pairwise_top_n": min(pairwise_top_n, len(baseline)),
        "pairwise_win_probability": pairwise_win_probability,
        "diagnostics": {
            "judge_count": len(judges),
            "submission_count": len(baseline),
            "conditional_rank_probabilities": True,
            "normalization_frozen": True,
        },
    }


def _perturb_weights(
    criterion_weights: dict[str, float],
    target: str,
    delta: float,
    direction: str,
) -> tuple[dict[str, float] | None, float]:
    if target not in criterion_weights:
        return None, 0.0

    weights = {str(key): float(value) for key, value in criterion_weights.items()}
    others = [key for key in weights if key != target and weights[key] > 0]

    if direction == "increase":
        if not others:
            return None, 0.0
        feasible = min(float(delta), sum(weights[key] for key in others))
        if feasible <= 1e-12:
            return None, 0.0
        weights[target] += feasible
        donor_total = sum(weights[key] for key in others)
        for key in others:
            weights[key] -= feasible * (weights[key] / donor_total)
    elif direction == "decrease":
        feasible = min(float(delta), max(0.0, weights[target] - 1e-9))
        if feasible <= 1e-12 or not others:
            return None, 0.0
        weights[target] -= feasible
        recipient_total = sum(weights[key] for key in others)
        for key in others:
            weights[key] += feasible * (weights[key] / recipient_total)
    else:
        raise ValueError("direction must be increase or decrease")

    total = sum(weights.values())
    if total <= 0:
        return None, 0.0
    weights = {key: value / total for key, value in weights.items()}
    return weights, feasible


def _rank_changes(baseline: list[dict], scenario: list[dict]) -> dict:
    base = _rank_map(baseline)
    current = _rank_map(scenario)
    movements = []
    for submission_id in sorted(base):
        if submission_id not in current:
            continue
        movement = current[submission_id] - base[submission_id]
        if movement:
            movements.append(abs(movement))
    return {
        "max_rank_movement": max(movements, default=0),
        "moved_submission_count": len(movements),
    }


def rubric_weight_sensitivity_from_rows(
    normalized_rows: list[dict],
    criterion_weights: dict[str, float],
    *,
    max_delta: float = 0.05,
    steps: int = 4,
) -> dict:
    """Criterion-aware rubric sensitivity using frozen normalized rows."""
    if max_delta <= 0:
        raise ValueError("max_delta must be positive")
    if steps < 1:
        raise ValueError("steps must be at least 1")

    def aggregate(weights: dict[str, float]) -> list[dict]:
        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in normalized_rows:
            grouped[(str(row["judge_id"]), str(row["submission_id"]))].append(row)

        by_submission: dict[str, list[float]] = defaultdict(list)
        for (_judge_id, submission_id), rows in grouped.items():
            numerator = 0.0
            denominator = 0.0
            for row in rows:
                weight = float(weights.get(str(row["criterion_id"]), 0.0))
                if weight <= 0:
                    continue
                numerator += weight * float(row.get("normalized_score", row["score"]))
                denominator += weight
            if denominator > 0:
                by_submission[submission_id].append(numerator / denominator)
        return _rank_from_project_scores(by_submission)

    baseline = aggregate(criterion_weights)
    baseline_winner, baseline_margin = _winner_and_margin(baseline)
    scenarios = []
    max_steps = int(steps)

    for criterion_id in sorted(criterion_weights):
        for direction in ("increase", "decrease"):
            for step in range(1, max_steps + 1):
                requested_delta = max_delta * step / max_steps
                weights, applied_delta = _perturb_weights(
                    criterion_weights,
                    criterion_id,
                    requested_delta,
                    direction,
                )
                if weights is None:
                    continue
                ranking = aggregate(weights)
                winner, margin = _winner_and_margin(ranking)
                movement = _rank_changes(baseline, ranking)
                scenarios.append(
                    {
                        "criterion_id": criterion_id,
                        "direction": direction,
                        "requested_delta": float(requested_delta),
                        "applied_delta": float(applied_delta),
                        "winner": winner,
                        "winner_changed": winner != baseline_winner,
                        "winner_margin": float(margin),
                        "margin_change": float(margin - baseline_margin),
                        "max_rank_movement": movement["max_rank_movement"],
                        "moved_submission_count": movement["moved_submission_count"],
                        "weights": weights,
                    }
                )

    winner_changes = [scenario for scenario in scenarios if scenario["winner_changed"]]
    return {
        "model": "frozen-normalization-rubric-sensitivity-v1",
        "baseline": {
            "winner": baseline_winner,
            "winner_margin": baseline_margin,
            "ranking": baseline,
            "weights": {str(key): float(value) for key, value in criterion_weights.items()},
        },
        "max_delta": max_delta,
        "steps": max_steps,
        "scenarios": scenarios,
        "diagnostics": {
            "criterion_count": len(criterion_weights),
            "scenario_count": len(scenarios),
            "winner_change_count": len(winner_changes),
            "normalization_frozen": True,
        },
    }


def analyze_stability(
    rows: list[dict],
    criterion_weights: dict[str, float],
    *,
    normalization_method: str = "robust_zscore",
    min_observations: int = 3,
    clip: bool = True,
    bootstrap_iterations: int = 1000,
    seed: int | None = 0,
    top_k: int = 3,
    pairwise_top_n: int = 5,
    sensitivity_delta: float = 0.05,
    sensitivity_steps: int = 4,
) -> dict:
    """Run Step 13 ranking stability and rubric sensitivity as one auditable unit."""
    if not rows:
        raise ValueError("No evaluation rows supplied")

    normalized = normalize_by_judge_criterion(
        rows,
        method=normalization_method,
        min_observations=min_observations,
        clip=clip,
    )
    normalized_rows = normalized["scores"]
    stability = bootstrap_panel_stability(
        normalized_rows,
        criterion_weights,
        iterations=bootstrap_iterations,
        seed=seed,
        top_k=top_k,
        pairwise_top_n=pairwise_top_n,
    )
    sensitivity = rubric_weight_sensitivity_from_rows(
        normalized_rows,
        criterion_weights,
        max_delta=sensitivity_delta,
        steps=sensitivity_steps,
    )

    return {
        "model": "JudgeGuard-step13-v1",
        "normalization": {
            "method": normalization_method,
            "min_observations": min_observations,
            "clip": clip,
        },
        "baseline": stability["baseline"],
        "bootstrap": stability,
        "rubric_sensitivity": sensitivity,
        "diagnostics": {
            "evaluation_rows": len(rows),
            "judge_count": len({str(row["judge_id"]) for row in rows}),
            "submission_count": len({str(row["submission_id"]) for row in rows}),
            "normalization": normalized.get("diagnostics", {}),
            "normalization_frozen_across_bootstrap": True,
            "normalization_frozen_across_sensitivity": True,
        },
    }
