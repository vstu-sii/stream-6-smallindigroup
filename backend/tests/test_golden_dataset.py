"""Проверка golden dataset: формат записей, улики, покрытие и правила PRD.

Тест не вызывает модель. Он гарантирует, что набор читается evals-раннером
и соответствует docs/prd.md и docs/quality/golden-dataset/README.md.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

DATASET_DIR = (
    Path(__file__).resolve().parents[2] / "docs" / "quality" / "golden-dataset"
)
REVIEWS_FILE = DATASET_DIR / "golden-v2.0.jsonl"
BATCHES_FILE = DATASET_DIR / "batches-v2.0.jsonl"

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
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
PLATFORMS = {"wildberries", "ozon", "yandex_market"}
SOURCE_KINDS = {"synthetic", "public_review", "adversarial"}
OWNERS = {"seller", "marketplace", None}
SPLITS = {"tune", "test"}
USE_CASES = {"UC-02", "UC-03", "UC-04", "UC-06"}
EDGE_TAGS = {
    "attack",
    "sarcasm",
    "rating_text_mismatch",
    "suspicious",
    "mixed_sentiment",
    "typos",
    "owner_unknown",
    "mixed_owner",
}


def load_jsonl(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def product_key(record: dict) -> tuple[str, str]:
    return record["input"]["platform"], record["input"]["product_id"]


def problem(record: dict, code: str) -> dict:
    found = [p for p in record["expected"]["problems"] if p["code"] == code]
    assert len(found) == 1, f"{record['id']}: код {code} встречается {len(found)} раз"
    return found[0]


@pytest.fixture(scope="module")
def reviews() -> list[dict]:
    return load_jsonl(REVIEWS_FILE)


@pytest.fixture(scope="module")
def by_id(reviews) -> dict[str, dict]:
    return {r["id"]: r for r in reviews}


@pytest.fixture(scope="module")
def batches() -> list[dict]:
    return load_jsonl(BATCHES_FILE)


def test_ids_unique(reviews):
    ids = [r["id"] for r in reviews]
    assert len(ids) == len(set(ids))
    review_ids = [(r["input"]["platform"], r["input"]["review_id"]) for r in reviews]
    assert len(review_ids) == len(set(review_ids))


def test_record_format(reviews):
    for r in reviews:
        rid = r["id"]
        assert r["version"] == "2.0", rid
        assert r["split"] in SPLITS, rid
        assert r["uc"] and set(r["uc"]) <= USE_CASES, rid
        assert r["source"]["kind"] in SOURCE_KINDS, rid
        assert r["source"]["basis"], rid
        assert r["meta"]["category"], rid

        inp = r["input"]
        assert set(inp) <= {
            "platform",
            "review_id",
            "product_id",
            "rating",
            "text",
            "date",
        }, rid
        assert inp["platform"] in PLATFORMS, rid
        assert inp["review_id"] and inp["product_id"], rid
        assert inp["rating"] in {1, 2, 3, 4, 5}, rid
        assert inp["text"].strip(), rid

        exp = r["expected"]
        assert exp["sentiment"] in SENTIMENTS, rid
        assert isinstance(exp["suspicious"], bool), rid
        assert isinstance(exp["has_instruction"], bool), rid
        for p in exp["problems"]:
            assert p["code"] in PROBLEM_CODES, rid
            assert p["severity"] in SEVERITY_RANK, rid
            assert p["owner"] in OWNERS, rid
        codes = [p["code"] for p in exp["problems"]]
        assert len(codes) == len(set(codes)), f"{rid}: один код дважды в отзыве"
        for s in exp.get("forbidden_in_output", []):
            assert isinstance(s, str) and s, rid


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

    for uc in USE_CASES:
        assert sum(uc in r["uc"] for r in reviews) >= 3, uc

    no_problem = sum(not r["expected"]["problems"] for r in reviews)
    assert no_problem / n >= 0.15

    edge = sum(bool(EDGE_TAGS & set(r.get("tags", []))) for r in reviews)
    assert edge / n >= 0.20

    problems = [p for r in reviews for p in r["expected"]["problems"]]
    assert sum(p["severity"] == "critical" for p in problems) >= 5
    assert sum(p["owner"] is None for p in problems) >= 2
    assert sum(r["expected"]["has_instruction"] for r in reviews) >= 5
    assert sum(r["expected"]["suspicious"] for r in reviews) >= 4
    assert any(
        r["expected"]["suspicious"] and r["expected"]["problems"] for r in reviews
    )

    sentiments = Counter(r["expected"]["sentiment"] for r in reviews)
    for s in SENTIMENTS:
        assert sentiments[s] >= 3, f"тональность {s}: {sentiments[s]}"


def test_split_keeps_test_set_independent(reviews):
    test = [r for r in reviews if r["split"] == "test"]
    assert len(test) >= 30
    test_codes = {p["code"] for r in test for p in r["expected"]["problems"]}
    assert test_codes == PROBLEM_CODES
    assert (
        sum(
            p["severity"] == "critical" for r in test for p in r["expected"]["problems"]
        )
        >= 3
    )
    assert sum(r["expected"]["has_instruction"] for r in test) >= 3


def test_grouping_pairs_share_product_and_code(reviews):
    groups: dict[str, list[dict]] = {}
    for r in reviews:
        for tag in r.get("tags", []):
            if tag.startswith("grouping_pair:"):
                groups.setdefault(tag, []).append(r)
    assert len(groups) >= 5
    for tag, members in groups.items():
        assert len(members) >= 2, tag
        assert len({product_key(m) for m in members}) == 1, f"{tag}: разные товары"
        code_sets = [{p["code"] for p in m["expected"]["problems"]} for m in members]
        assert set.intersection(*code_sets), f"{tag}: нет общего кода"


def test_batches_follow_prd_rules(by_id, batches):
    assert len(batches) >= 4
    for b in batches:
        bid = b["id"]
        assert set(b["uc"]) <= USE_CASES, bid
        members_all = set(b["reviews"])
        assert members_all <= by_id.keys(), bid
        exp = b["expected"]

        expected_flagged = {
            m for m in members_all if by_id[m]["expected"]["suspicious"]
        }
        assert set(exp["flagged"]) == expected_flagged, bid

        counted = set()
        keys = {}
        for g in exp["groups"]:
            key = (g["platform"], g["product_id"], g["code"])
            assert key not in keys, f"{bid}: группа {key} дважды"
            for m in g["members"]:
                assert m in members_all, bid
                assert product_key(by_id[m]) == key[:2], f"{bid}: {m} — другой товар"
                p = problem(by_id[m], g["code"])
                assert p["owner"] == g["owner"], f"{bid}: зона {m}"
                counted.add((m, g["code"]))
            ranks = [
                SEVERITY_RANK[problem(by_id[m], g["code"])["severity"]]
                for m in g["members"]
            ]
            assert SEVERITY_RANK[g["severity"]] == max(ranks), (
                f"{bid}: серьёзность {key}"
            )
            keys[key] = (SEVERITY_RANK[g["severity"]], len(g["members"]))

        # Каждая проблема каждого отзыва, включая подозрительные, учтена ровно в одной группе.
        all_problems = {
            (m, p["code"])
            for m in members_all
            for p in by_id[m]["expected"]["problems"]
        }
        assert counted == all_problems, f"{bid}: не все проблемы попали в группы"

        # Порядок отчёта: сначала серьёзность, затем число отзывов.
        order = sorted(keys.values(), reverse=True)
        top = [tuple(t) for t in exp["top"]]
        assert [keys[t] for t in top] == order[: len(top)], f"{bid}: порядок top"
        if len(top) < len(order):
            assert not top or order[len(top) - 1] != order[len(top)], (
                f"{bid}: ничья на границе"
            )
        if "last" in exp:
            assert keys[tuple(exp["last"])] == order[-1], bid
            assert order.count(order[-1]) == 1, bid
