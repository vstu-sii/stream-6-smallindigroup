"""Чтение golden dataset v2.0 и выбор срезов для прогона."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "docs" / "quality" / "golden-dataset"
REVIEWS_FILE = DATASET_DIR / "golden-v2.0.jsonl"
BATCHES_FILE = DATASET_DIR / "batches-v2.0.jsonl"

# Быстрый срез (тест-план): все critical и attack из test + по одной записи на код.
# Пакеты: gb-01 — критический сигнал выше частых жалоб, gb-04 — инструкция
# «поставь первым» не поднимает приоритет.
FAST_BATCHES = ("gb-01", "gb-04")


def load_jsonl(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reviews() -> list[dict]:
    return load_jsonl(REVIEWS_FILE)


def batches() -> list[dict]:
    return load_jsonl(BATCHES_FILE)


def fast_slice(records: list[dict]) -> list[dict]:
    test = sorted((r for r in records if r["split"] == "test"), key=lambda r: r["id"])
    chosen = {
        r["id"]
        for r in test
        if "attack" in r.get("tags", [])
        or any(p["severity"] == "critical" for p in r["expected"]["problems"])
    }
    covered = {
        p["code"] for r in test if r["id"] in chosen for p in r["expected"]["problems"]
    }
    for r in test:
        new = {p["code"] for p in r["expected"]["problems"]} - covered
        if new:
            chosen.add(r["id"])
            covered |= new
    return [r for r in test if r["id"] in chosen]


def select(slice_name: str) -> tuple[list[dict], list[dict]]:
    """Записи и пакеты среза: fast — быстрый срез для PR, full — вся выборка test."""
    records = reviews()
    all_batches = batches()
    if slice_name == "fast":
        return fast_slice(records), [b for b in all_batches if b["id"] in FAST_BATCHES]
    if slice_name == "full":
        return [r for r in records if r["split"] == "test"], all_batches
    raise ValueError(f"неизвестный срез: {slice_name}")
