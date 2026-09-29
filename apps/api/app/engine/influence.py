from __future__ import annotations

import itertools
from collections import defaultdict
from typing import Iterable

from app.engine.normalization import normalize_by_judge_criterion


def _rank_map(ranking: list[dict]) -> dict[str, int]:
    return {str(item["submission_id"]): index + 1 for index, item in enumerate(ranking)}


def _rank_from_judge_scores(
    judge_scores: dict[str, dict[str, float]],
    removed_judges: set[str] | None = None,
) -> list[dict]:
    removed = removed_judges or set()
    by_submission: dict[str, list[tuple[str, float]]] = defaultdict(list)

    for judge_id, project_scores in judge_scores.items():
        if judge_id in removed:
            continue
        for submission_id, score in project_scores.items():
            by_submission[submission_id].append((judge_id, float(score)))

    ranking: list[dict] = []
    for submission_id, values in by_submission.items():
        scores = [score for _, score in values]
        score = sum(scores) / len(scores)
        ranking.append(
            {
                "submission_id": submission_id,
                "score": float(score),
                "judge_count": len(scores),
                "std_dev": float(_population_std(scores)),
            }
        )

    return sorted(
        ranking,
        key=lambda item: (-item["score"], str(item["submission_id"])),
    )


def _population_std(values: Iterable[float]) -> float:
    values = list(values)
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


def _winner_and_margin(ranking: list[dict]) -> tuple[str | None, float]:
    if not ranking:
        return None, 0.0
    if len(ranking) == 1:
        return str(ranking[0]["submission_id"]), 0.0
    return (
        str(ranking[0]["submission_id"]),
        float(ranking[0]["score"] - ranking[1]["score"]),
    )


def _rank_movement(
    baseline: list[dict],
    counterfactual: list[dict],
) -> tuple[int, list[str]]:
    base = _rank_map(baseline)
    current = _rank_map(counterfactual)
    max_movement = 0
    affected: list[str] = []

    for submission_id, base_rank in base.items():
        if submission_id not in current:
            affected.append(submission_id)
            continue
        movement = abs(base_rank - current[submission_id])
        if movement > 0:
            affected.append(submission_id)
        max_movement = max(max_movement, movement)

    return max_movement, affected


def build_influence_graph(
    judge_scores: dict[str, dict[str, float]],
    influence_by_judge: dict[str, dict],
) -> dict:
    judge_nodes = []
    submission_ids: set[str] = set()
    edges = []

    for judge_id in sorted(judge_scores):
        metrics = influence_by_judge.get(judge_id, {})
        judge_nodes.append(
            {
                "id": f"judge:{judge_id}",
                "type": "judge",
                "judge_id": judge_id,
                "influence": metrics.get("mean_abs_project_score_delta", 0.0),
                "winner_changed": bool(metrics.get("winner_changed", False)),
                "max_rank_movement": int(metrics.get("max_rank_movement", 0)),
            }
        )
        for submission_id, score in sorted(judge_scores[judge_id].items()):
            submission_ids.add(submission_id)
            edges.append(
                {
                    "source": f"judge:{judge_id}",
                    "target": f"submission:{submission_id}",
                    "judge_id": judge_id,
                    "submission_id": submission_id,
                    "score": float(score),
                }
            )

    nodes = judge_nodes + [
        {
            "id": f"submission:{submission_id}",
            "type": "submission",
            "submission_id": submission_id,
        }
        for submission_id in sorted(submission_ids)
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def analyze_influence(
    rows: list[dict],
    criterion_weights: dict[str, float],
    *,
    normalization_method: str = "robust_zscore",
    min_observations: int = 3,
    clip: bool = True,
    max_coalition: int = 3,
    max_exact_judges: int = 40,
    max_reported_coalitions: int = 10,
) -> dict:
    if not rows:
        raise ValueError("No evaluation rows supplied")
    if max_coalition < 1:
        raise ValueError("max_coalition must be at least 1")
    if max_exact_judges < 1:
        raise ValueError("max_exact_judges must be at least 1")

    normalized = normalize_by_judge_criterion(
        rows,
        method=normalization_method,
        min_observations=min_observations,
        clip=clip,
    )
    judge_scores = _judge_project_scores(normalized["scores"], criterion_weights)
    judges = sorted(judge_scores)

    baseline = _rank_from_judge_scores(judge_scores)
    baseline_winner, baseline_margin = _winner_and_margin(baseline)
    baseline_scores = {
        str(item["submission_id"]): float(item["score"])
        for item in baseline
    }

    influence_by_judge: dict[str, dict] = {}
    for judge_id in judges:
        counterfactual = _rank_from_judge_scores(
            judge_scores,
            removed_judges={judge_id},
        )
        new_winner, new_margin = _winner_and_margin(counterfactual)
        max_movement, affected = _rank_movement(baseline, counterfactual)

        project_deltas = []
        for submission_id, base_score in baseline_scores.items():
            counter = next(
                (
                    item["score"]
                    for item in counterfactual
                    if str(item["submission_id"]) == submission_id
                ),
                None,
            )
            if counter is not None:
                project_deltas.append(abs(base_score - float(counter)))

        assignments = len(judge_scores[judge_id])
        mean_abs_delta = (
            sum(project_deltas) / len(project_deltas)
            if project_deltas
            else 0.0
        )

        influence_by_judge[judge_id] = {
            "judge_id": judge_id,
            "assignment_count": assignments,
            "assignment_share": assignments / max(1, sum(len(x) for x in judge_scores.values())),
            "winner_changed": new_winner != baseline_winner,
            "counterfactual_winner": new_winner,
            "baseline_margin": baseline_margin,
            "counterfactual_margin": new_margin,
            "margin_change": float(new_margin - baseline_margin),
            "max_rank_movement": int(max_movement),
            "affected_submission_count": len(affected),
            "unrated_submission_ids": [
                submission_id
                for submission_id in affected
                if submission_id not in _rank_map(counterfactual)
            ],
            "mean_abs_project_score_delta": float(mean_abs_delta),
        }

    total_judges = len(judges)
    single_flips = [
        data for data in influence_by_judge.values() if data["winner_changed"]
    ]

    search_mode = "exact"
    candidate_judges = judges
    if len(judges) > max_exact_judges:
        search_mode = "screened"
        candidate_judges = [
            item["judge_id"]
            for item in sorted(
                influence_by_judge.values(),
                key=lambda item: (
                    -int(item["winner_changed"]),
                    -int(item["max_rank_movement"]),
                    -float(item["mean_abs_project_score_delta"]),
                    item["judge_id"],
                ),
            )[:max_exact_judges]
        ]

    tested_sizes: list[int] = []
    tested_combinations = 0
    minimum_size: int | None = None
    minimum_coalitions: list[list[str]] = []
    minimum_new_winners: set[str] = set()

    for size in range(1, min(max_coalition, len(candidate_judges)) + 1):
        tested_sizes.append(size)
        for coalition in itertools.combinations(candidate_judges, size):
            tested_combinations += 1
            counterfactual = _rank_from_judge_scores(
                judge_scores,
                removed_judges=set(coalition),
            )
            new_winner, _ = _winner_and_margin(counterfactual)
            if new_winner != baseline_winner:
                minimum_size = size
                minimum_coalitions.append(list(coalition))
                if new_winner:
                    minimum_new_winners.add(new_winner)
                if len(minimum_coalitions) >= max_reported_coalitions:
                    break
        if minimum_size is not None or len(minimum_coalitions) >= max_reported_coalitions:
            break

    critical_judges = sorted(
        {
            judge_id
            for coalition in minimum_coalitions
            for judge_id in coalition
        }
    )

    influence_order = sorted(
        influence_by_judge.values(),
        key=lambda item: (
            -int(item["winner_changed"]),
            -int(item["max_rank_movement"]),
            -float(item["mean_abs_project_score_delta"]),
            item["judge_id"],
        ),
    )

    report = {
        "model": "frozen-normalization-judge-removal-v1",
        "normalization": {
            "method": normalization_method,
            "min_observations": min_observations,
            "clip": clip,
        },
        "baseline": {
            "winner": baseline_winner,
            "winner_margin": baseline_margin,
            "ranking": baseline,
        },
        "judges": influence_order,
        "attack_surface": {
            "judge_count": total_judges,
            "single_judge_flip_count": len(single_flips),
            "single_judge_flip_rate": len(single_flips) / max(1, total_judges),
            "minimum_flip_size": minimum_size,
            "minimum_flip_coalitions": minimum_coalitions,
            "critical_judges": critical_judges,
            "new_winners_under_minimum_flip": sorted(minimum_new_winners),
            "search_mode": search_mode,
            "candidate_judge_count": len(candidate_judges),
            "tested_coalition_sizes": tested_sizes,
            "tested_combinations": tested_combinations,
            "max_coalition": max_coalition,
            "exact_search_limit": max_exact_judges,
        },
        "graph": build_influence_graph(judge_scores, influence_by_judge),
        "diagnostics": {
            "evaluation_rows": len(rows),
            "judge_count": total_judges,
            "submission_count": len(baseline),
            "single_judge_winner_flip": len(single_flips) > 0,
            "highest_rank_movement": max(
                (item["max_rank_movement"] for item in influence_by_judge.values()),
                default=0,
            ),
            "normalization_diagnostics": normalized.get("diagnostics", {}),
        },
    }
    return report
