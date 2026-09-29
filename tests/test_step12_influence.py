from app.engine.influence import analyze_influence


def rows_for_single_flip():
    return [
        {"judge_id": "j1", "submission_id": "a", "criterion_id": "c", "score": 1},
        {"judge_id": "j1", "submission_id": "b", "criterion_id": "c", "score": 1},
        {"judge_id": "j1", "submission_id": "c", "criterion_id": "c", "score": 1},
        {"judge_id": "j2", "submission_id": "a", "criterion_id": "c", "score": 1},
        {"judge_id": "j2", "submission_id": "b", "criterion_id": "c", "score": 1},
        {"judge_id": "j2", "submission_id": "c", "criterion_id": "c", "score": 2},
        {"judge_id": "j3", "submission_id": "a", "criterion_id": "c", "score": 2},
        {"judge_id": "j3", "submission_id": "b", "criterion_id": "c", "score": 1},
        {"judge_id": "j3", "submission_id": "c", "criterion_id": "c", "score": 1},
    ]


def rows_for_two_judge_flip():
    return [
        # Two judges favor a, one judge favors b.
        {"judge_id": "j1", "submission_id": "a", "criterion_id": "c", "score": 5},
        {"judge_id": "j1", "submission_id": "b", "criterion_id": "c", "score": 1},
        {"judge_id": "j2", "submission_id": "a", "criterion_id": "c", "score": 5},
        {"judge_id": "j2", "submission_id": "b", "criterion_id": "c", "score": 1},
        {"judge_id": "j3", "submission_id": "a", "criterion_id": "c", "score": 1},
        {"judge_id": "j3", "submission_id": "b", "criterion_id": "c", "score": 5},
    ]


def test_influence_graph_and_single_judge_analysis():
    result = analyze_influence(
        rows_for_single_flip(),
        {"c": 1.0},
        normalization_method="zscore",
        min_observations=2,
        max_coalition=2,
    )

    assert result["baseline"]["winner"] == "a"
    assert result["attack_surface"]["single_judge_flip_count"] >= 1
    assert result["attack_surface"]["minimum_flip_size"] == 1
    assert result["graph"]["node_count"] == 6
    assert result["graph"]["edge_count"] == 9


def test_two_judge_minimum_flip_set():
    result = analyze_influence(
        rows_for_two_judge_flip(),
        {"c": 1.0},
        normalization_method="zscore",
        min_observations=2,
        max_coalition=2,
    )

    assert result["baseline"]["winner"] == "a"
    assert result["attack_surface"]["single_judge_flip_count"] == 0
    assert result["attack_surface"]["minimum_flip_size"] == 2
    assert result["attack_surface"]["minimum_flip_coalitions"]


def test_influence_analysis_is_deterministic():
    a = analyze_influence(
        rows_for_two_judge_flip(),
        {"c": 1.0},
        normalization_method="zscore",
        min_observations=2,
        max_coalition=2,
    )
    b = analyze_influence(
        rows_for_two_judge_flip(),
        {"c": 1.0},
        normalization_method="zscore",
        min_observations=2,
        max_coalition=2,
    )

    assert a["attack_surface"] == b["attack_surface"]
    assert a["baseline"] == b["baseline"]
