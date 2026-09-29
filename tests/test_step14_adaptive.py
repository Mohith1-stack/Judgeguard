from app.engine.adaptive import recommend_next_review


def _judges():
    return [
        {
            "judge_id": "j1",
            "capacity": 10,
            "assignment_count": 2,
            "load_ratio": 0.2,
            "expertise": ["python", "web"],
            "evaluated_submission_ids": ["x"],
            "conflicted_submission_ids": [],
            "team_member_submission_ids": [],
            "expertise_fit_by_submission": {"a": 0.8, "b": 0.2},
            "overlap_by_submission": {"a": 0.0, "b": 0.0},
        },
        {
            "judge_id": "j2",
            "capacity": 2,
            "assignment_count": 2,
            "load_ratio": 1.0,
            "expertise": ["python"],
            "evaluated_submission_ids": [],
            "conflicted_submission_ids": ["a", "b"],
            "team_member_submission_ids": [],
            "expertise_fit_by_submission": {"a": 1.0, "b": 1.0},
            "overlap_by_submission": {"a": 0.0, "b": 0.0},
        },
        {
            "judge_id": "j3",
            "capacity": 10,
            "assignment_count": 1,
            "load_ratio": 0.1,
            "expertise": ["python"],
            "evaluated_submission_ids": ["a"],
            "conflicted_submission_ids": [],
            "team_member_submission_ids": [],
            "expertise_fit_by_submission": {"a": 1.0, "b": 1.0},
            "overlap_by_submission": {"a": 0.0, "b": 0.0},
        },
    ]


def test_selects_uncertain_target_and_best_independent_judge():
    result = recommend_next_review(
        [
            {"submission_id": "a", "score": 9.0},
            {"submission_id": "b", "score": 8.95},
            {"submission_id": "c", "score": 7.0},
        ],
        {"a": 0.52, "b": 0.48, "c": 0.0},
        _judges(),
        coverage_frequency={"a": 1.0, "b": 0.9, "c": 1.0},
        fragile_submissions={"b"},
        target_tags={"a": {"python", "web"}, "b": {"python"}, "c": {"rust"}},
    )

    assert result is not None
    assert result["submission_id"] == "b"
    assert result["judge_id"] == "j3"
    assert result["estimated_review_value"] > 0
    assert result["is_probability"] is False
    assert 0 <= result["target_priority"]["priority_score"] <= 1
    assert 0 <= result["judge_utility"]["utility_score"] <= 1


def test_hard_exclusions_block_conflict_capacity_and_self_review():
    judges = [
        {
            "judge_id": "conflict",
            "capacity": 10,
            "assignment_count": 1,
            "load_ratio": 0.1,
            "evaluated_submission_ids": [],
            "conflicted_submission_ids": ["a", "b"],
            "team_member_submission_ids": [],
        },
        {
            "judge_id": "member",
            "capacity": 10,
            "assignment_count": 1,
            "load_ratio": 0.1,
            "evaluated_submission_ids": [],
            "conflicted_submission_ids": [],
            "team_member_submission_ids": ["a", "b"],
        },
        {
            "judge_id": "full",
            "capacity": 1,
            "assignment_count": 1,
            "load_ratio": 1.0,
            "evaluated_submission_ids": [],
            "conflicted_submission_ids": [],
            "team_member_submission_ids": [],
        },
    ]
    result = recommend_next_review(
        [{"submission_id": "a", "score": 5.0}, {"submission_id": "b", "score": 4.0}],
        {"a": 0.5, "b": 0.5},
        judges,
        coverage_frequency={"a": 1.0, "b": 1.0},
    )
    assert result is not None
    assert result["judge_id"] is None
    blocked = {row["judge_id"]: row["blocked_reason"] for row in result["target_candidates"][0]["candidates"]}
    assert blocked["conflict"] == "judge_conflict"
    assert blocked["member"] == "judge_is_submission_team_member"
    assert blocked["full"] == "capacity_exhausted"


def test_recommendation_is_deterministic_for_equal_inputs():
    args = dict(
        rankings=[{"submission_id": "a", "score": 5.0}, {"submission_id": "b", "score": 4.9}],
        rank1_frequency={"a": 0.5, "b": 0.5},
        judge_candidates=[
            {"judge_id": "j2", "capacity": 10, "assignment_count": 1, "load_ratio": 0.1, "evaluated_submission_ids": []},
            {"judge_id": "j1", "capacity": 10, "assignment_count": 1, "load_ratio": 0.1, "evaluated_submission_ids": []},
        ],
        coverage_frequency={"a": 1.0, "b": 1.0},
    )
    first = recommend_next_review(**args)
    second = recommend_next_review(**args)
    assert first == second
    assert first["judge_id"] == "j1"


def test_excluded_target_is_not_selected():
    result = recommend_next_review(
        [{"submission_id": "a", "score": 5.0}, {"submission_id": "b", "score": 4.9}],
        {"a": 0.5, "b": 0.5},
        [
            {"judge_id": "j1", "capacity": 10, "assignment_count": 0, "load_ratio": 0.0, "evaluated_submission_ids": []},
        ],
        coverage_frequency={"a": 1.0, "b": 1.0},
        excluded_submissions={"a"},
    )
    assert result["submission_id"] == "b"
