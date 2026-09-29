from app.engine.statistics import (
    aggregate_rankings,
    bootstrap_stability,
    minimum_flip_set,
    normalize_scores,
    rubric_sensitivity,
)


def sample_rows():
    return [
        {"judge_id": "j1", "submission_id": "p1", "criterion_id": "c1", "score": 5},
        {"judge_id": "j1", "submission_id": "p2", "criterion_id": "c1", "score": 3},
        {"judge_id": "j2", "submission_id": "p1", "criterion_id": "c1", "score": 4},
        {"judge_id": "j2", "submission_id": "p2", "criterion_id": "c1", "score": 2},
        {"judge_id": "j3", "submission_id": "p1", "criterion_id": "c1", "score": 5},
        {"judge_id": "j3", "submission_id": "p2", "criterion_id": "c1", "score": 4},
    ]


def test_normalization():
    result = normalize_scores(sample_rows(), "robust_zscore")
    assert len(result["scores"]) == 6
    assert all("normalized_score" in row for row in result["scores"])


def test_ranking():
    rows = normalize_scores(sample_rows(), "robust_zscore")["scores"]
    ranking = aggregate_rankings(rows, {"c1": 1.0})
    assert ranking[0]["submission_id"] == "p1"


def test_bootstrap():
    result = bootstrap_stability(sample_rows(), {"c1": 1.0}, iterations=100, seed=7)
    assert result["iterations"] == 100
    assert "p1" in result["rank1_frequency"]


def test_flip_set():
    rows = [
        {"judge_id": "j1", "submission_id": "p1", "criterion_id": "c1", "score": 5},
        {"judge_id": "j1", "submission_id": "p2", "criterion_id": "c1", "score": 4},
        {"judge_id": "j2", "submission_id": "p1", "criterion_id": "c1", "score": 5},
        {"judge_id": "j2", "submission_id": "p2", "criterion_id": "c1", "score": 4},
        {"judge_id": "j3", "submission_id": "p1", "criterion_id": "c1", "score": 1},
        {"judge_id": "j3", "submission_id": "p2", "criterion_id": "c1", "score": 5},
    ]
    result = minimum_flip_set(rows, {"c1": 1.0}, max_coalition=3)
    assert "minimum_size" in result


def test_rubric_sensitivity():
    result = rubric_sensitivity(sample_rows(), {"c1": 1.0}, delta=0.05)
    assert "scenarios" in result
