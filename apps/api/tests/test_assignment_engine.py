from app.engine.assignment import AssignmentError, build_assignment_plan


def _submissions(count=8):
    return [
        {
            "id": f"s{i}",
            "team_id": f"t{i}",
            "track_id": "track-a" if i % 2 == 0 else "track-b",
            "tech_tags": ["python"] if i % 2 == 0 else ["rust"],
        }
        for i in range(count)
    ]


def _judges(count=4):
    return [
        {
            "id": f"j{i}",
            "capacity": 8,
            "expertise": ["python"] if i % 2 == 0 else ["rust"],
        }
        for i in range(count)
    ]


def test_assignment_respects_review_count_capacity_and_uniqueness():
    plan = build_assignment_plan(_submissions(), _judges(), set(), 2, seed=7, optimization_restarts=10)
    assert plan["review_count"] == 16
    assert all(v <= 8 for v in plan["judge_load"].values())

    by_submission = {}
    for item in plan["assignments"]:
        by_submission.setdefault(item["submission_id"], []).append(item["judge_id"])

    assert all(len(judges) == 2 for judges in by_submission.values())
    assert all(len(set(judges)) == 2 for judges in by_submission.values())


def test_assignment_respects_conflicts():
    conflicts = {("j0", "t0"), ("j1", "t1")}
    plan = build_assignment_plan(_submissions(), _judges(), conflicts, 2, seed=11)
    pairs = {(item["judge_id"], item["submission_id"]) for item in plan["assignments"]}
    assert ("j0", "s0") not in pairs
    assert ("j1", "s1") not in pairs


def test_assignment_fails_when_capacity_is_insufficient():
    small = [{"id": "j0", "capacity": 2, "expertise": []}]
    try:
        build_assignment_plan(_submissions(3), small, set(), 2, seed=1)
    except AssignmentError as exc:
        assert "capacity is insufficient" in str(exc).lower()
    else:
        raise AssertionError("Expected AssignmentError")


def test_assignment_fails_when_a_project_has_too_few_eligible_judges():
    judges = [
        {"id": "j0", "capacity": 8, "expertise": []},
        {"id": "j1", "capacity": 8, "expertise": []},
    ]
    conflicts = {("j0", "t0"), ("j1", "t0")}
    try:
        build_assignment_plan(_submissions(2), judges, conflicts, 1, seed=3)
    except AssignmentError as exc:
        assert "eligible judges" in str(exc).lower()
    else:
        raise AssertionError("Expected AssignmentError")


def test_assignment_is_reproducible_for_same_seed():
    a = build_assignment_plan(_submissions(), _judges(), set(), 2, seed=123, optimization_restarts=8)
    b = build_assignment_plan(_submissions(), _judges(), set(), 2, seed=123, optimization_restarts=8)
    assert a == b


def test_assignment_diagnostics_expose_structural_risk_without_claiming_winner_probability():
    plan = build_assignment_plan(_submissions(), _judges(), set(), 2, seed=4, optimization_restarts=8)
    diagnostics = plan["diagnostics"]
    assert 0.0 <= diagnostics["structural_risk"] <= 1.0
    assert 0.0 <= diagnostics["structural_integrity"] <= 1.0
    assert "winner" not in diagnostics
    assert "probability" not in diagnostics
