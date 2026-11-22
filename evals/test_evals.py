"""Быстрый срез evals для CI: python -m pytest evals -m fast.

Первая часть — блокирующие пороги из thresholds.json на baseline. Вторая —
самопроверка раннера: эталон проходит все цели, а ошибки системы ловятся.
"""

import copy

import pytest

from evals import dataset, run
from evals.metrics import CODES, batch_metrics, review_metrics

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def result():
    return run.evaluate("fast")


@pytest.fixture(scope="module")
def full_data():
    records, batches = dataset.select("full")
    by_id = {r["id"]: r for r in dataset.reviews()}
    return records, batches, by_id


def oracle(by_id):
    """Ответ «идеальной системы» — эталон в формате выхода."""
    fields = ("sentiment", "problems", "suspicious", "has_instruction")
    return {
        rid: copy.deepcopy({k: r["expected"][k] for k in fields})
        for rid, r in by_id.items()
    }


@pytest.mark.parametrize(
    "gate", run.check(run.evaluate("fast"), "gates"), ids=lambda g: g["metric"]
)
def test_gate(gate):
    assert gate["passed"], (
        f"{gate['metric']}: {gate['actual']} {gate['op']} {gate['value']} — {gate['why']}"
    )


def test_fast_slice_matches_test_plan(result):
    records, _ = dataset.select("fast")
    assert all(r["split"] == "test" for r in records)
    assert 12 <= len(records) <= 18
    codes = {p["code"] for r in records for p in r["expected"]["problems"]}
    assert codes == CODES, "в быстром срезе должен быть каждый код таксономии"
    for r in dataset.select("full")[0]:
        critical = any(p["severity"] == "critical" for p in r["expected"]["problems"])
        if critical or "attack" in r.get("tags", []):
            assert r in records, f"{r['id']}: critical и attack входят в быстрый срез"
    assert result["meta"]["batches"] == list(dataset.FAST_BATCHES)


def test_predictor_never_sees_expected(monkeypatch):
    seen = []
    monkeypatch.setattr(
        run.baseline_rules, "predict", lambda inp: seen.append(inp) or {}
    )
    records, _ = dataset.select("fast")
    run.predict_all(run.baseline_rules, records)
    assert seen and all("expected" not in s and "tags" not in s for s in seen)


def test_oracle_meets_every_target(full_data):
    records, batches, by_id = full_data
    preds = oracle(by_id)
    rm, _ = review_metrics(records, preds)
    bm, errors = batch_metrics(batches, by_id, preds)
    result = {"metrics": {**rm, **bm}}
    failed = [t for t in run.check(result, "targets") if not t["passed"]]
    assert not failed, failed
    assert not errors


def test_missing_critical_and_fake_quote_are_caught(full_data):
    records, _, by_id = full_data
    preds = oracle(by_id)
    preds["gd-0028"]["problems"] = []
    preds["gd-0013"]["problems"][0]["evidence"] = "привезли на следующий день"
    rm, errors = review_metrics(records, preds)
    assert rm["critical_missed"]["value"] == 1
    assert rm["evidence_exists"]["value"] < 1
    assert any(e["id"] == "gd-0028" for e in errors)


def test_executed_instruction_is_caught(full_data):
    records, _, by_id = full_data
    preds = oracle(by_id)
    preds["gd-0042"]["problems"][0]["severity"] = "critical"
    preds["gd-0041"]["problems"][0]["evidence"] = "Пишите в t.me/sale_textile"
    rm, _ = review_metrics(records, preds)
    assert rm["instruction_severity_raised"]["value"] == 1
    assert rm["forbidden_leaks"]["value"] == 1


def test_invalid_answer_counts_as_empty(full_data):
    records, _, by_id = full_data
    preds = oracle(by_id)
    preds["gd-0028"] = {"problems": "не JSON"}
    rm, _ = review_metrics(records, preds)
    assert rm["schema_valid"]["value"] < 1
    assert rm["critical_missed"]["value"] == 1


def test_wrong_order_and_excluded_flagged_are_caught(full_data):
    _, batches, by_id = full_data
    preds = oracle(by_id)
    # gb-01: критический сигнал понижен — он больше не первый в отчёте.
    preds["gd-0028"]["problems"][0]["severity"] = "low"
    # gb-03: проблема подозрительного отзыва потеряна.
    preds["gd-0053"]["problems"] = []
    bm, errors = batch_metrics(batches, by_id, preds)
    assert bm["priority_violations"]["value"] >= 1
    assert bm["group_match"]["value"] < 1
    assert {e["id"] for e in errors} >= {"gb-01", "gb-03"}


def test_no_data_is_not_a_pass(monkeypatch, tmp_path):
    path = tmp_path / "t.json"
    path.write_text(
        '{"gates": {"recall": {"op": ">=", "value": 0.1, "why": ""}}}', encoding="utf-8"
    )
    monkeypatch.setattr(run, "THRESHOLDS_FILE", path)
    rows = run.check(
        {"metrics": {"recall": {"value": None, "num": 0, "den": 0}}}, "gates"
    )
    assert rows[0]["passed"] is False
