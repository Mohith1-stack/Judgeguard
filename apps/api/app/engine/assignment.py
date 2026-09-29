from __future__ import annotations

from collections import defaultdict
import hashlib
import math
import random
import secrets
from dataclasses import dataclass, field
from statistics import fmean
from typing import Iterable


class AssignmentError(ValueError):
    """Raised when a judging assignment plan cannot satisfy hard constraints."""


@dataclass
class _JudgeState:
    id: str
    capacity: int
    expertise: set[str]
    assigned: set[str] = field(default_factory=set)
    track_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    co_review_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))


@dataclass(frozen=True)
class _Submission:
    id: str
    team_id: str | None
    track_id: str | None
    tech_tags: frozenset[str]


def _norm(values: Iterable[object] | None) -> set[str]:
    if not values:
        return set()
    return {str(value).strip().lower() for value in values if str(value).strip()}


def _normalize_conflicts(
    conflicts: Iterable[tuple[str, str] | tuple[str, str, str]],
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Return (judge->team, judge->submission) conflict sets."""
    judge_team: set[tuple[str, str]] = set()
    judge_submission: set[tuple[str, str]] = set()

    for item in conflicts:
        if len(item) == 2:
            a, b = str(item[0]), str(item[1])
            # The database uses (judge_id, team_id); the engine also supports
            # direct submission conflicts for callers that need them.
            judge_team.add((a, b))
        elif len(item) == 3:
            judge_submission.add((str(item[0]), str(item[2])))
        else:
            raise AssignmentError("Conflict tuples must contain 2 or 3 values")

    return judge_team, judge_submission


def _stable_rank(seed: int, judge_id: str, submission_id: str) -> int:
    blob = f"{seed}:{judge_id}:{submission_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(blob).digest()[:8], "big")


def _eligible(
    judge: _JudgeState,
    submission: _Submission,
    judge_team_conflicts: set[tuple[str, str]],
    judge_submission_conflicts: set[tuple[str, str]],
) -> bool:
    if len(judge.assigned) >= judge.capacity:
        return False
    if submission.id in judge.assigned:
        return False
    if submission.team_id and (judge.id, submission.team_id) in judge_team_conflicts:
        return False
    if (judge.id, submission.id) in judge_submission_conflicts:
        return False
    return True


def _candidate_score(
    judge: _JudgeState,
    submission: _Submission,
    *,
    selected_for_submission: list[str],
    total_submissions: int,
    target_reviews: int,
) -> float:
    """Lower is better. Hard constraints are handled separately."""
    capacity_ratio = len(judge.assigned) / max(1, judge.capacity)
    expertise_overlap = len(submission.tech_tags & judge.expertise)
    missing_expertise_ratio = (
        1.0 - (expertise_overlap / max(1, len(submission.tech_tags)))
        if submission.tech_tags
        else 0.0
    )

    pair_overlap = sum(judge.co_review_counts.get(other, 0) for other in selected_for_submission)
    track_count = judge.track_counts.get(submission.track_id or "__none__", 0)
    concentration = track_count / max(1, len(judge.assigned))

    # The score deliberately prioritizes resilience-related properties:
    # workload balance and avoiding repeated judge-pairs. Expertise and track
    # fit are soft preferences, not hard constraints.
    score = 4.0 * capacity_ratio
    score += 3.0 * pair_overlap
    score += 1.5 * concentration
    score += 1.0 * missing_expertise_ratio
    score -= min(1.5, 0.35 * expertise_overlap)
    return score


def _assignment_objective(
    assignments: list[dict],
    judges: dict[str, _JudgeState],
    submissions: list[_Submission],
    reviews_per_submission: int,
) -> tuple[float, dict]:
    total_reviews = len(assignments)
    if total_reviews == 0:
        return math.inf, {}

    loads = [len(j.assigned) for j in judges.values()]
    mean_load = fmean(loads) if loads else 0.0
    load_deviation = fmean(abs(x - mean_load) for x in loads) if loads else 0.0
    max_load = max(loads) if loads else 0

    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    by_submission: dict[str, list[str]] = defaultdict(list)
    for item in assignments:
        by_submission[str(item["submission_id"])].append(str(item["judge_id"]))

    for judge_ids in by_submission.values():
        for i, a in enumerate(sorted(judge_ids)):
            for b in sorted(judge_ids)[i + 1 :]:
                pair_counts[(a, b)] += 1

    max_pair_overlap = max(pair_counts.values(), default=0)
    mean_pair_overlap = fmean(pair_counts.values()) if pair_counts else 0.0

    track_concentrations: list[float] = []
    for judge in judges.values():
        total = len(judge.assigned)
        if total:
            track_concentrations.append(max(judge.track_counts.values(), default=0) / total)
    max_track_concentration = max(track_concentrations, default=0.0)

    # Queue-order exposure: no project should systematically appear at an edge
    # of every judge's queue. We quantify edge exposure after queue construction.
    positions_by_submission: dict[str, list[float]] = defaultdict(list)
    for item in assignments:
        positions_by_submission[str(item["submission_id"])].append(float(item["queue_position"]))

    order_edge_risk_values = []
    for sid, positions in positions_by_submission.items():
        judge_ids = [str(a["judge_id"]) for a in assignments if str(a["submission_id"]) == sid]
        for judge_id, position in zip(judge_ids, positions):
            queue_len = len(judges[judge_id].assigned)
            normalized = (position - 1) / max(1, queue_len - 1)
            order_edge_risk_values.append(1.0 if normalized <= 0.1 or normalized >= 0.9 else 0.0)
    order_edge_risk = fmean(order_edge_risk_values) if order_edge_risk_values else 0.0

    ideal = total_reviews / max(1, len(judges))
    max_load_excess = max(0.0, (max_load - ideal) / max(1.0, ideal))
    pair_overlap_risk = max_pair_overlap / max(1, len(submissions))

    # Structural risk proxy; deliberately not called winner probability.
    structural_risk = min(
        1.0,
        0.45 * max_load_excess
        + 0.35 * pair_overlap_risk
        + 0.15 * max_track_concentration
        + 0.05 * order_edge_risk,
    )

    objective = (
        5.0 * load_deviation
        + 3.5 * max_pair_overlap
        + 1.5 * mean_pair_overlap
        + 1.0 * max_track_concentration
        + 0.5 * order_edge_risk
    )

    diagnostics = {
        "total_assignments": total_reviews,
        "judge_count": len(judges),
        "submission_count": len(submissions),
        "reviews_per_submission": reviews_per_submission,
        "mean_judge_load": round(mean_load, 4),
        "max_judge_load": max_load,
        "min_judge_load": min(loads) if loads else 0,
        "load_deviation": round(load_deviation, 4),
        "max_pair_overlap": max_pair_overlap,
        "mean_pair_overlap": round(mean_pair_overlap, 4),
        "max_track_concentration": round(max_track_concentration, 4),
        "order_edge_risk": round(order_edge_risk, 4),
        "structural_risk": round(structural_risk, 4),
        "structural_integrity": round(1.0 - structural_risk, 4),
        "max_load_excess": round(max_load_excess, 4),
    }
    return objective, diagnostics


def _build_queues(
    assignments: list[dict],
    judges: dict[str, _JudgeState],
    submissions: list[_Submission],
    seed: int,
) -> list[dict]:
    by_judge: dict[str, list[dict]] = defaultdict(list)
    for item in assignments:
        by_judge[str(item["judge_id"])].append(item)

    global_order = sorted(
        [s.id for s in submissions],
        key=lambda sid: _stable_rank(seed, "GLOBAL", sid),
    )
    global_index = {sid: i for i, sid in enumerate(global_order)}
    judge_ids = sorted(by_judge)

    # Counterbalance queue positions: each judge gets a different cyclic shift
    # over a shared randomized project order, then filters to their assignments.
    output: list[dict] = []
    for judge_index, judge_id in enumerate(judge_ids):
        assigned = by_judge[judge_id]
        n = len(global_order)
        shift = (judge_index * max(1, n // max(1, len(judge_ids)))) % max(1, n)
        rotated_rank = {
            sid: (global_index[sid] - shift) % max(1, n)
            for sid in global_order
        }
        ordered = sorted(
            assigned,
            key=lambda item: (rotated_rank[str(item["submission_id"])], _stable_rank(seed, judge_id, str(item["submission_id"]))),
        )
        for position, item in enumerate(ordered, start=1):
            output.append(
                {
                    **item,
                    "queue_position": position,
                }
            )

    return sorted(output, key=lambda item: (str(item["judge_id"]), item["queue_position"]))


def _single_plan(
    submissions: list[_Submission],
    judges_input: list[dict],
    conflicts: Iterable[tuple[str, str] | tuple[str, str, str]],
    reviews_per_submission: int,
    seed: int,
) -> tuple[list[dict], dict]:
    judges: dict[str, _JudgeState] = {}
    for raw in judges_input:
        judge_id = str(raw["id"])
        if judge_id in judges:
            raise AssignmentError(f"Duplicate judge id: {judge_id}")
        capacity = int(raw.get("capacity", reviews_per_submission))
        if capacity < 1:
            raise AssignmentError(f"Judge {judge_id} has invalid capacity")
        judges[judge_id] = _JudgeState(
            id=judge_id,
            capacity=capacity,
            expertise=_norm(raw.get("expertise", [])),
        )

    if not judges:
        raise AssignmentError("No judges configured")
    if not submissions:
        raise AssignmentError("No submitted projects are available")

    judge_team_conflicts, judge_submission_conflicts = _normalize_conflicts(conflicts)

    total_required = len(submissions) * reviews_per_submission
    total_capacity = sum(j.capacity for j in judges.values())
    if total_capacity < total_required:
        raise AssignmentError(
            f"Judge capacity is insufficient: need {total_required} reviews, have {total_capacity}"
        )

    # Most-constrained-first project ordering prevents a late dead end.
    ordered_submissions = []
    for submission in submissions:
        eligible_count = sum(
            _eligible(j, submission, judge_team_conflicts, judge_submission_conflicts)
            for j in judges.values()
        )
        if eligible_count < reviews_per_submission:
            raise AssignmentError(
                f"Submission {submission.id} has only {eligible_count} eligible judges; "
                f"{reviews_per_submission} are required"
            )
        ordered_submissions.append((eligible_count, submission))

    rng = random.Random(seed)
    ordered_submissions.sort(key=lambda pair: (pair[0], rng.random(), pair[1].id))

    assignments: list[dict] = []
    for _, submission in ordered_submissions:
        selected: list[str] = []
        for _ in range(reviews_per_submission):
            candidates: list[tuple[float, float, _JudgeState]] = []
            for judge in judges.values():
                if not _eligible(judge, submission, judge_team_conflicts, judge_submission_conflicts):
                    continue
                score = _candidate_score(
                    judge,
                    submission,
                    selected_for_submission=selected,
                    total_submissions=len(submissions),
                    target_reviews=reviews_per_submission,
                )
                candidates.append((score, rng.random(), judge))

            if not candidates:
                raise AssignmentError(
                    f"No eligible judge remains for submission {submission.id}"
                )

            candidates.sort(key=lambda item: (item[0], item[1], item[2].id))
            judge = candidates[0][2]
            judge.assigned.add(submission.id)
            if submission.track_id:
                judge.track_counts[submission.track_id] += 1
            for other in selected:
                judge.co_review_counts[other] += 1
                judges[other].co_review_counts[judge.id] += 1
            selected.append(judge.id)
            assignments.append(
                {
                    "judge_id": judge.id,
                    "submission_id": submission.id,
                    "track_id": submission.track_id,
                }
            )

    queued = _build_queues(assignments, judges, submissions, seed)
    _, diagnostics = _assignment_objective(
        queued,
        judges,
        submissions,
        reviews_per_submission,
    )
    return queued, diagnostics


def build_assignment_plan(
    submissions: list[dict],
    judges: list[dict],
    conflicts: set[tuple[str, str]] | set[tuple[str, str, str]],
    reviews_per_submission: int,
    seed: int | None = None,
    optimization_restarts: int = 24,
) -> dict:
    """
    Build a constraint-satisfying, resilience-oriented judge assignment plan.

    Hard constraints:
    - every submitted project gets exactly reviews_per_submission judges
    - a judge cannot review a submission twice
    - capacity is respected
    - declared conflicts are respected

    Soft objectives:
    - balance judge workloads
    - minimize repeated judge-pairs
    - reduce single-track concentration
    - favor track/expertise fit
    - counterbalance queue order

    The returned structural_risk is a planning-time proxy, not a claim about
    the final winner or actual post-score influence. Post-score influence is
    calculated by JudgeGuard's integrity engine in later steps.
    """
    if reviews_per_submission < 1:
        raise AssignmentError("reviews_per_submission must be positive")
    if optimization_restarts < 1 or optimization_restarts > 200:
        raise AssignmentError("optimization_restarts must be between 1 and 200")

    normalized_submissions = [
        _Submission(
            id=str(raw["id"]),
            team_id=str(raw["team_id"]) if raw.get("team_id") else None,
            track_id=str(raw["track_id"]) if raw.get("track_id") else None,
            tech_tags=frozenset(_norm(raw.get("tech_tags", []))),
        )
        for raw in submissions
    ]

    ids = [s.id for s in normalized_submissions]
    if len(ids) != len(set(ids)):
        raise AssignmentError("Duplicate submission ids are not allowed")

    actual_seed = int(seed) if seed is not None else secrets.randbits(63)
    best_plan: list[dict] | None = None
    best_diagnostics: dict | None = None
    best_objective = math.inf
    attempted = 0
    failures: list[str] = []

    for restart in range(optimization_restarts):
        restart_seed = (actual_seed + restart * 1_000_003) & ((1 << 63) - 1)
        attempted += 1
        try:
            plan, diagnostics = _single_plan(
                normalized_submissions,
                judges,
                conflicts,
                reviews_per_submission,
                restart_seed,
            )
            # Reconstruct judge state from the plan to score the chosen solution.
            judge_states = {
                str(raw["id"]): _JudgeState(
                    id=str(raw["id"]),
                    capacity=int(raw.get("capacity", reviews_per_submission)),
                    expertise=_norm(raw.get("expertise", [])),
                )
                for raw in judges
            }
            for item in plan:
                judge_states[str(item["judge_id"])].assigned.add(str(item["submission_id"]))
                track_id = item.get("track_id")
                if track_id:
                    judge_states[str(item["judge_id"])].track_counts[str(track_id)] += 1
            objective, diagnostics = _assignment_objective(
                plan,
                judge_states,
                normalized_submissions,
                reviews_per_submission,
            )
            if objective < best_objective:
                best_objective = objective
                best_plan = plan
                best_diagnostics = diagnostics
        except AssignmentError as exc:
            failures.append(str(exc))

    if best_plan is None or best_diagnostics is None:
        reason = failures[0] if failures else "No feasible assignment was found"
        raise AssignmentError(reason)

    load = defaultdict(int)
    for item in best_plan:
        load[str(item["judge_id"])] += 1

    return {
        "seed": actual_seed,
        "optimization_restarts": attempted,
        "assignments": best_plan,
        "judge_load": dict(sorted(load.items())),
        "review_count": len(best_plan),
        "diagnostics": best_diagnostics,
    }
