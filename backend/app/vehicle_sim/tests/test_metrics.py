from app.vehicle_sim.evaluation.metrics import evaluate_run


def test_metrics_empty_file(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")

    result = evaluate_run(str(path))

    assert result["ok"] is False
