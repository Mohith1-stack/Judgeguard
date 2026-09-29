from app.engine.stability import analyze_stability, bootstrap_panel_stability
from app.engine.normalization import normalize_by_judge_criterion


def stable_rows():
    rows = []
    for judge_id in ("j1", "j2", "j3", "j4"):
        rows.extend(
            [
                {"judge_id": judge_id, "submission_id": "a", "criterion_id": "c1", "score": 5},
                {"judge_id": judge_id, "submission_id": "b", "criterion_id": "c1", "score": 3},
                {"judge_id": judge_id, "submission_id": "c", "criterion_id": "c1", "score": 1},
                {"judge_id": judge_id, "submission_id": "a", "criterion_id": "c2", "score": 5},
                {"judge_id": judge_id, "submission_id": "b", "criterion_id": "c2", "score": 3},
                {"judge_id": judge_id, "submission_id": "c", "criterion_id": "c2", "score": 1},
            ]
        )
    return rows


def sensitivity_rows():
    rows = []
    scores = {
        "a": (4.6, 2.0),
        "b": (2.0, 5.0),
        "c": (3.0, 3.0),
    }
    for judge_id in ("j1", "j2", "j3", "j4"):
        for submission_id, (c1, c2) in scores.items():
            rows.append({"judge_id": judge_id, "submission_id": submission_id, "criterion_id": "c1", "score": c1})
            rows.append({"judge_id": judge_id, "submission_id": submission_id, "criterion_id": "c2", "score": c2})
    return rows


def test_panel_bootstrap_is_deterministic_and_stable():
    normalized = normalize_by_judge_criterion(
        stable_rows(), method="robust_zscore", min_observations=3, clip=True
    )["scores"]
    a = bootstrap_panel_stability(
        normalized,
        {"c1": 0.5, "c2": 0.5},
        iterations=250,
        seed=11,
        top_k=3,
        pairwise_top_n=3,
    )
    b = bootstrap_panel_stability(
        normalized,
        {"c1": 0.5, "c2": 0.5},
        iterations=250,
        seed=11,
        top_k=3,
        pairwise_top_n=3,
    )

    assert a == b
    assert a["baseline"]["winner"] == "a"
    assert a["rank1_frequency"] == {"a": 1.0, "b": 0.0, "c": 0.0}
    assert a["coverage_frequency"] == {"a": 1.0, "b": 1.0, "c": 1.0}
    assert a["top_k_frequency"] == {"a": 1.0, "b": 1.0, "c": 1.0}
    assert a["pairwise_win_probability"]["a|b"]["left_win_probability"] == 1.0
    assert a["diagnostics"]["normalization_frozen"] is True


def test_rubric_sensitivity_preserves_weight_sum_and_detects_flip():
    result = analyze_stability(
        sensitivity_rows(),
        {"c1": 0.5, "c2": 0.5},
        normalization_method="robust_zscore",
        min_observations=3,
        clip=True,
        bootstrap_iterations=150,
        seed=7,
        top_k=2,
        pairwise_top_n=2,
        sensitivity_delta=0.2,
        sensitivity_steps=4,
    )

    assert result["baseline"]["winner"] == "b"
    assert result["rubric_sensitivity"]["diagnostics"]["scenario_count"] == 16
    assert result["rubric_sensitivity"]["diagnostics"]["winner_change_count"] > 0

    for scenario in result["rubric_sensitivity"]["scenarios"]:
        assert abs(sum(scenario["weights"].values()) - 1.0) < 1e-9
        assert all(value >= 0 for value in scenario["weights"].values())
        assert scenario["weights"]["c1"] <= 1.0
        assert scenario["weights"]["c2"] <= 1.0


def test_stability_reports_conditional_coverage_for_sparse_assignments():
    rows = stable_rows()
    rows = [row for row in rows if not (row["judge_id"] == "j4" and row["submission_id"] == "c")]
    normalized = normalize_by_judge_criterion(
        rows, method="robust_zscore", min_observations=3, clip=True
    )["scores"]
    result = bootstrap_panel_stability(
        normalized,
        {"c1": 0.5, "c2": 0.5},
        iterations=300,
        seed=19,
        top_k=3,
        pairwise_top_n=3,
    )

    assert 0 < result["coverage_frequency"]["c"] <= 1
    assert result["coverage_frequency"]["c"] < 1
    assert result["rank_observations"]["c"] < 300
    assert 0 <= result["rank1_frequency"]["c"] <= 1
