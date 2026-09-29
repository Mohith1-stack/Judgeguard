from __future__ import annotations

from math import isfinite


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if isfinite(parsed) else default


def _expertise_fit(judge: dict, target_tags: set[str]) -> float:
    provided = {str(x).strip().lower() for x in judge.get("expertise", []) if str(x).strip()}
    if not target_tags:
        return 0.5 if not provided else 0.5
    if not provided:
        return 0.0
    return _clamp(len(target_tags & provided) / len(target_tags | provided))


def _target_priority(
    project: dict,
    rank: int,
    rank1_probability: float,
    coverage: float,
    *,
    top_score: float,
    score_spread: float,
    fragile: bool,
) -> dict:
    """Compute a transparent review-priority heuristic.

    This is a decision-support score, not a probability and not a claim of
    expected statistical information gain. The components deliberately come
    from Step 13 outputs so the reason for a recommendation is inspectable.
    """
    rank1_uncertainty = _clamp(1.0 - abs(2.0 * _clamp(rank1_probability) - 1.0))
    boundary_closeness = 1.0 if score_spread <= 1e-12 else _clamp(
        1.0 - max(0.0, top_score - _safe_float(project.get("score"))) / score_spread
    )
    coverage_deficit = 1.0 - _clamp(coverage)
    fragility_signal = 1.0 if fragile else 0.0
    rank_factor = 1.0 / max(1, rank)

    priority = (
        0.45 * rank1_uncertainty
        + 0.25 * boundary_closeness
        + 0.15 * coverage_deficit
        + 0.10 * fragility_signal
        + 0.05 * rank_factor
    )
    return {
        "rank": rank,
        "rank1_frequency": _clamp(rank1_probability),
        "rank1_uncertainty": rank1_uncertainty,
        "coverage_frequency": _clamp(coverage),
        "coverage_deficit": coverage_deficit,
        "boundary_closeness": boundary_closeness,
        "fragility_signal": fragility_signal,
        "priority_score": _clamp(priority),
    }


def recommend_next_review(
    rankings: list[dict],
    rank1_frequency: dict[str, float],
    judge_candidates: list[dict],
    evaluated_pairs: set[tuple[str, str]] | None = None,
    *,
    coverage_frequency: dict[str, float] | None = None,
    fragile_submissions: set[str] | None = None,
    excluded_submissions: set[str] | None = None,
    target_rank_limit: int = 5,
    max_candidates: int = 20,
    minimum_priority: float = 0.0,
    target_tags: dict[str, set[str]] | None = None,
) -> dict | None:
    """Select the next independent review from Step 13 uncertainty signals.

    `evaluated_pairs` is retained for compatibility with the earlier helper
    signature. Candidate dictionaries may additionally contain:
      evaluated_submission_ids, conflicted_submission_ids, team_member_submission_ids,
      load_ratio, capacity, expertise, overlap_with_target_panel.
    """
    del evaluated_pairs
    if not rankings:
        return None
    if target_rank_limit < 1:
        raise ValueError("target_rank_limit must be at least 1")
    if max_candidates < 1:
        raise ValueError("max_candidates must be at least 1")

    coverage_frequency = coverage_frequency or {}
    fragile_submissions = {str(x) for x in (fragile_submissions or set())}
    excluded_submissions = {str(x) for x in (excluded_submissions or set())}
    target_tags = target_tags or {}

    considered = rankings[: min(target_rank_limit, len(rankings))]
    top_score = _safe_float(considered[0].get("score"))
    bottom_score = _safe_float(considered[-1].get("score"))
    score_spread = abs(top_score - bottom_score)

    target_options = []
    for rank, project in enumerate(considered, start=1):
        submission_id = str(project["submission_id"])
        if submission_id in excluded_submissions:
            continue
        details = _target_priority(
            project,
            rank,
            _safe_float(rank1_frequency.get(submission_id, 0.0)),
            _safe_float(coverage_frequency.get(submission_id, 0.0)),
            top_score=top_score,
            score_spread=score_spread,
            fragile=submission_id in fragile_submissions,
        )
        if details["priority_score"] + 1e-12 < minimum_priority:
            continue
        target_options.append(
            {
                "submission_id": submission_id,
                "priority": details,
            }
        )

    if not target_options:
        return None

    candidate_results: list[dict] = []
    target_options.sort(
        key=lambda item: (-item["priority"]["priority_score"], item["priority"]["rank"], item["submission_id"])
    )

    for target_option in target_options:
        submission_id = target_option["submission_id"]
        target_candidate_rows = []
        for judge in judge_candidates:
            judge_id = str(judge["judge_id"])
            evaluated = {str(x) for x in judge.get("evaluated_submission_ids", [])}
            conflicts = {str(x) for x in judge.get("conflicted_submission_ids", [])}
            team_membership = {str(x) for x in judge.get("team_member_submission_ids", [])}

            already_reviewed = submission_id in evaluated
            conflict = submission_id in conflicts
            self_review = submission_id in team_membership
            load_ratio = _clamp(_safe_float(judge.get("load_ratio", 0.0)))
            capacity_slack = _clamp(1.0 - load_ratio)
            target_tag_set = {str(x).strip().lower() for x in target_tags.get(submission_id, set()) if str(x).strip()}
            fit_by_submission = judge.get("expertise_fit_by_submission", {}) or {}
            overlap_by_submission = judge.get("overlap_by_submission", {}) or {}
            fit_default = _expertise_fit(judge, target_tag_set)
            fit = _safe_float(fit_by_submission.get(submission_id, judge.get("expertise_fit", fit_default)), 0.5)
            diversity = _clamp(1.0 - _safe_float(overlap_by_submission.get(submission_id, judge.get("overlap_with_target_panel", 0.0))))

            blocked_reason = None
            if already_reviewed:
                blocked_reason = "already_assigned_to_submission"
            elif conflict:
                blocked_reason = "judge_conflict"
            elif self_review:
                blocked_reason = "judge_is_submission_team_member"
            elif _safe_float(judge.get("capacity", 1.0)) <= _safe_float(judge.get("assignment_count", 0)):
                blocked_reason = "capacity_exhausted"

            utility = _clamp(0.45 * _clamp(fit) + 0.30 * capacity_slack + 0.25 * diversity)
            row = {
                "judge_id": judge_id,
                "eligible": blocked_reason is None,
                "blocked_reason": blocked_reason,
                "expertise_fit": _clamp(fit),
                "capacity_slack": capacity_slack,
                "panel_diversity": diversity,
                "load_ratio": load_ratio,
                "assignment_count": int(_safe_float(judge.get("assignment_count", 0))),
                "utility_score": utility,
            }
            target_candidate_rows.append(row)
            if blocked_reason is None:
                gain = _clamp(target_option["priority"]["priority_score"] * utility)
                candidate_results.append(
                    {
                        "submission_id": submission_id,
                        "judge_id": judge_id,
                        "estimated_review_value": gain,
                        "target_priority": target_option["priority"],
                        "judge_utility": row,
                    }
                )

        target_option["candidates"] = sorted(
            target_candidate_rows,
            key=lambda item: (-item["utility_score"], item["judge_id"]),
        )[:max_candidates]

    if candidate_results:
        candidate_results.sort(
            key=lambda item: (
                -item["estimated_review_value"],
                item["target_priority"]["rank"],
                item["submission_id"],
                item["judge_id"],
            )
        )
        selected = candidate_results[0]
        target_priority = selected["target_priority"]
        judge_utility = selected["judge_utility"]
        reason = (
            f"Target {selected['submission_id']} has rank-1 frequency "
            f"{target_priority['rank1_frequency']:.3f}, rank-1 uncertainty "
            f"{target_priority['rank1_uncertainty']:.3f}, and panel coverage "
            f"{target_priority['coverage_frequency']:.3f}. Selected independent judge "
            f"{selected['judge_id']} with expertise fit {judge_utility['expertise_fit']:.3f}, "
            f"capacity slack {judge_utility['capacity_slack']:.3f}, and panel diversity "
            f"{judge_utility['panel_diversity']:.3f}."
        )
        return {
            "model": "stability-guided-independent-review-v2",
            "submission_id": selected["submission_id"],
            "judge_id": selected["judge_id"],
            "expected_gain": selected["estimated_review_value"],
            "estimated_review_value": selected["estimated_review_value"],
            "reason": reason,
            "target_priority": target_priority,
            "judge_utility": judge_utility,
            "target_candidates": [
                {
                    "submission_id": option["submission_id"],
                    "priority": option["priority"],
                    "eligible_judge_count": sum(1 for row in option.get("candidates", []) if row["eligible"]),
                    "candidates": option.get("candidates", []),
                }
                for option in target_options
            ],
            "candidate_count": len(judge_candidates),
            "eligible_candidate_count": len(candidate_results),
            "selection_formula": {
                "target_priority": "0.45*rank1_uncertainty + 0.25*boundary_closeness + 0.15*coverage_deficit + 0.10*fragility_signal + 0.05*(1/rank)",
                "judge_utility": "0.45*expertise_fit + 0.30*capacity_slack + 0.25*panel_diversity",
                "review_value": "target_priority * judge_utility",
            },
            "is_probability": False,
        }

    first = target_options[0]
    return {
        "model": "stability-guided-independent-review-v2",
        "submission_id": first["submission_id"],
        "judge_id": None,
        "expected_gain": first["priority"]["priority_score"],
        "estimated_review_value": first["priority"]["priority_score"],
        "reason": "A high-priority target was identified, but no independent judge is currently eligible after assignment, conflict, self-review, and capacity checks.",
        "target_priority": first["priority"],
        "judge_utility": None,
        "target_candidates": [
            {
                "submission_id": option["submission_id"],
                "priority": option["priority"],
                "eligible_judge_count": sum(1 for row in option.get("candidates", []) if row["eligible"]),
                "candidates": option.get("candidates", []),
            }
            for option in target_options
        ],
        "candidate_count": len(judge_candidates),
        "eligible_candidate_count": 0,
        "selection_formula": {
            "target_priority": "0.45*rank1_uncertainty + 0.25*boundary_closeness + 0.15*coverage_deficit + 0.10*fragility_signal + 0.05*(1/rank)",
            "judge_utility": "0.45*expertise_fit + 0.30*capacity_slack + 0.25*panel_diversity",
            "review_value": "target_priority * judge_utility",
        },
        "is_probability": False,
    }
