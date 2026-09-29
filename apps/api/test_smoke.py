from app.engine.assignment import build_assignment_plan


def test_assignment_plan():
    submissions = [
        {"id": "p1", "team_id": "t1", "track_id": "track-a", "tech_tags": ["python"]},
        {"id": "p2", "team_id": "t2", "track_id": "track-b", "tech_tags": ["web"]},
    ]
    judges = [
        {"id": "j1", "capacity": 2, "expertise": ["python"]},
        {"id": "j2", "capacity": 2, "expertise": ["web"]},
    ]
    result = build_assignment_plan(submissions, judges, {("j1", "t1")}, 1, seed=42)
    assert result["review_count"] == 2
    assert all(x["queue_position"] >= 1 for x in result["assignments"])
