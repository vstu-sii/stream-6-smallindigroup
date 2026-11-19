"""Проверка golden dataset: формат записей, улики и покрытие.

Тест не вызывает модель. Он гарантирует, что набор читается evals-раннером
и соответствует docs/quality/golden-dataset/README.md.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

DATASET_DIR = (
    Path(__file__).resolve().parents[2] / "docs" / "quality" / "golden-dataset"
)
REVIEWS_FILE = DATASET_DIR / "golden-v1.0.jsonl"
BATCHES_FILE = DATASET_DIR / "batches-v1.0.jsonl"

PROBLEM_CODES = {
    "delivery_delay",
    "not_delivered",
    "wrong_item",
    "defect_on_arrival",
    "defect_after_use",
    "material_quality",
    "size_mismatch",
    "description_mismatch",
    "smell",
    "safety_hazard",
}
SENTIMENTS = {"positive", "neutral", "negative", "mixed"}
SEVERITIES = ["none", "low", "medium", "high", "critical"]
PLATFORMS = {"wildberries", "ozon", "yandex_market", "maps", "other"}
SOURCE_KINDS = {"synthetic", "interview", "public_review", "adversarial"}
OWNERS = {"seller", "marketplace", None}
USE_CASES = {"UC-01", "UC-02", "UC-03", "UC-04", "UC-05"}
EDGE_TAGS = {
    "attack",
    "sarcasm",
    "rating_text_mismatch",
    "suspicious",
    "mixed_sentiment",
    "typos",
}


def load_jsonl(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@pytest.fixture(scope="module")
def reviews() -> list[dict]:
    return load_jsonl(REVIEWS_FILE)


@pytest.fixture(scope="module")
def batches() -> list[dict]:
    return load_jsonl(BATCHES_FILE)


def test_ids_unique(reviews):
    ids = [r["id"] for r in reviews]
    assert len(ids) == len(set(ids))


def test_record_format(reviews):
    for r in reviews:
        rid = r["id"]
        assert r["version"] == "1.0", rid
        assert set(r["uc"]) <= USE_CASES and r["uc"], rid
        assert r["source"]["kind"] in SOURCE_KINDS, rid
        assert r["source"]["basis"], rid

        inp = r["input"]
        assert inp["platform"] in PLATFORMS, rid
        assert inp["category"], rid
        assert inp["rating"] in {1, 2, 3, 4, 5}, rid
        assert inp["text"].strip(), rid

        exp = r["expected"]
        assert exp["sentiment"] in SENTIMENTS, rid
        assert exp["severity"] in SEVERITIES, rid
        assert exp["owner"] in OWNERS, rid
        assert isinstance(exp["suspicious"], bool), rid
        assert isinstance(exp["has_instruction"], bool), rid
        assert exp["reply"]["must"] and exp["reply"]["must_not"], rid

        problems = exp["problems"]
        if problems:
            assert exp["severity"] != "none", rid
            assert exp["owner"] is not None, rid
        else:
            assert exp["severity"] == "none", rid
        for p in problems:
            assert p["code"] in PROBLEM_CODES, rid


def test_evidence_is_quoted_from_text(reviews):
    for r in reviews:
        text = " ".join(r["input"]["text"].split())
        for p in r["expected"]["problems"]:
            for fragment in p["evidence"].split(" ... "):
                fragment = " ".join(fragment.split())
                assert fragment in text, f"{r['id']}: «{fragment}» нет в тексте"


def test_volume_and_coverage(reviews):
    n = len(reviews)
    assert 30 <= n <= 80

    codes = Counter(p["code"] for r in reviews for p in r["expected"]["problems"])
    for code in PROBLEM_CODES:
        assert codes[code] >= 3, f"код {code}: {codes[code]} записей, нужно ≥ 3"

    for uc in USE_CASES - {"UC-03"}:
        assert sum(uc in r["uc"] for r in reviews) >= 3, uc

    no_problem = sum(not r["expected"]["problems"] for r in reviews)
    assert no_problem / n >= 0.15

    edge = sum(bool(EDGE_TAGS & set(r.get("tags", []))) for r in reviews)
    assert edge / n >= 0.20

    assert sum(r["expected"]["severity"] == "critical" for r in reviews) >= 5
    assert sum(r["expected"]["has_instruction"] for r in reviews) >= 5
    assert sum(r["expected"]["suspicious"] for r in reviews) >= 4

    sentiments = Counter(r["expected"]["sentiment"] for r in reviews)
    for s in SENTIMENTS:
        assert sentiments[s] >= 3, f"тональность {s}: {sentiments[s]}"


def test_grouping_pairs_share_code(reviews):
    groups: dict[str, list[dict]] = {}
    for r in reviews:
        for tag in r.get("tags", []):
            if tag.startswith("grouping_pair:"):
                groups.setdefault(tag, []).append(r)
    assert len(groups) >= 5
    for tag, members in groups.items():
        assert len(members) >= 2, tag
        code_sets = [{p["code"] for p in m["expected"]["problems"]} for m in members]
        assert set.intersection(*code_sets), f"{tag}: нет общего кода"


def test_batches_reference_reviews(reviews, batches):
    by_id = {r["id"]: r for r in reviews}
    assert len(batches) >= 3
    for b in batches:
        bid = b["id"]
        assert set(b["uc"]) <= USE_CASES, bid
        members_all = set(b["reviews"])
        assert members_all <= by_id.keys(), bid
        exp = b["expected"]
        assert set(exp["excluded"]) <= members_all, bid
        assert set(exp["must_flag"]) <= members_all, bid
        for g in exp["groups"]:
            assert g["code"] in PROBLEM_CODES, bid
            for m in g["members"]:
                assert m in members_all, bid
                codes = {p["code"] for p in by_id[m]["expected"]["problems"]}
                assert g["code"] in codes, f"{bid}: {m} не содержит {g['code']}"
        assert set(exp["top"]) == {g["code"] for g in exp["groups"]}, bid
        for m in exp["must_flag"]:
            assert by_id[m]["expected"]["severity"] == "critical", bid
        for m in exp["excluded"]:
            assert by_id[m]["expected"]["suspicious"], bid
