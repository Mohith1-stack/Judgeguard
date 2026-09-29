from apps.api.app.engine.normalization import calibration_metrics, drift_metrics, normalize_by_judge_criterion


def rows():
    data = []
    for judge_id, values_a, values_b in [
        ("j1", [1, 2, 3], [3, 4, 5]),
        ("j2", [3, 4, 5], [1, 2, 3]),
    ]:
        for index, score in enumerate(values_a, start=1):
            data.append({
                "judge_id": judge_id,
                "submission_id": f"a{index}",
                "criterion_id": "c1",
                "score": score,
                "queue_position": index,
                "submitted_at": f"2026-09-29T00:0{index}:00+00:00",
            })
        for index, score in enumerate(values_b, start=1):
            data.append({
                "judge_id": judge_id,
                "submission_id": f"b{index}",
                "criterion_id": "c2",
                "score": score,
                "queue_position": index,
                "submitted_at": f"2026-09-29T00:1{index}:00+00:00",
            })
    return data


def test_criterion_specific_normalization_calibrates_groups():
    result = normalize_by_judge_criterion(rows(), "robust_zscore", min_observations=3)
    assert result["diagnostics"]["normalized_row_count"] == 12
    assert all(item["normalization_status"] == "normalized" for item in result["scores"])
    assert set(result["global_criteria"]) == {"c1", "c2"}


def test_insufficient_data_is_not_invented():
    sample = rows()[:2]
    result = normalize_by_judge_criterion(sample, min_observations=3)
    assert all(item["normalization_status"] == "insufficient_data" for item in result["scores"])
    assert result["scores"][0]["normalized_score"] == result["scores"][0]["score"]


def test_calibration_reports_severity_shift_and_anchor_checks():
    result = calibration_metrics(
        rows(),
        anchors=[
            {
                "submission_id": "a1",
                "criterion_id": "c1",
                "target_score": 2.0,
                "tolerance": 0.5,
            }
        ],
        min_observations=3,
    )
    assert result["diagnostics"]["group_count"] == 4
    assert result["diagnostics"]["anchor_check_count"] == 2


def test_drift_is_criterion_specific_and_honors_threshold():
    result = drift_metrics(rows(), min_observations=3)
    assert result["diagnostics"]["ready_group_count"] == 4
    assert all("slope_per_position" in group for group in result["groups"])
