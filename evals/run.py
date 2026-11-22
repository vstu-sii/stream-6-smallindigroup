"""Прогон evals: python -m evals.run --slice fast|full [--out results.json] [--md report.md].

Код выхода 1, если на быстром срезе провалена блокирующая проверка
(thresholds.json → gates). Полный срез только считает цели PRD (targets).
"""

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from evals import baseline_rules, dataset
from evals.metrics import batch_metrics, review_metrics

THRESHOLDS_FILE = Path(__file__).with_name("thresholds.json")
PREDICTORS = {"rules": baseline_rules}


def predict_all(predictor, records: list[dict]) -> tuple[dict, list[float]]:
    preds, latencies = {}, []
    for r in records:
        start = time.perf_counter()
        # Системе передаётся только input: эталон, теги и источник ей не видны.
        preds[r["id"]] = predictor.predict(dict(r["input"]))
        latencies.append(time.perf_counter() - start)
    return preds, latencies


def evaluate(slice_name: str, predictor_name: str = "rules") -> dict:
    predictor = PREDICTORS[predictor_name]
    records, batches = dataset.select(slice_name)
    by_id = {r["id"]: r for r in dataset.reviews()}
    needed = {r["id"] for r in records} | {rid for b in batches for rid in b["reviews"]}
    preds, latencies = predict_all(predictor, [by_id[i] for i in sorted(needed)])

    rm, review_errors = review_metrics(records, preds)
    bm, batch_errors = batch_metrics(batches, by_id, preds)
    latencies.sort()
    return {
        "meta": {
            "slice": slice_name,
            "predictor": predictor_name,
            "predictor_version": getattr(predictor, "VERSION", None),
            "dataset": dataset.REVIEWS_FILE.name,
            "dataset_sha256": dataset.sha256(dataset.REVIEWS_FILE),
            "batches_sha256": dataset.sha256(dataset.BATCHES_FILE),
            "records": [r["id"] for r in records],
            "batches": [b["id"] for b in batches],
            "commit": os.getenv("GITHUB_SHA"),
            "started_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "python": platform.python_version(),
            "p95_seconds": latencies[max(0, round(0.95 * len(latencies)) - 1)],
            "cost_rub": 0 if predictor_name == "rules" else None,
        },
        "metrics": {**rm, **bm},
        "errors": {"reviews": review_errors, "batches": batch_errors},
    }


def check(result: dict, section: str) -> list[dict]:
    rules = json.loads(THRESHOLDS_FILE.read_text(encoding="utf-8"))[section]
    rows = []
    for name, rule in rules.items():
        value = result["metrics"][name]["value"]
        if value is None:
            passed = False
        elif rule["op"] == ">=":
            passed = value >= rule["value"]
        else:
            passed = value <= rule["value"]
        rows.append({"metric": name, **rule, "actual": value, "passed": passed})
    return rows


def fmt(value) -> str:
    if value is None:
        return "нет данных"
    return f"{value:.3g}" if isinstance(value, float) else str(value)


def markdown(result: dict, gates: list[dict], targets: list[dict]) -> str:
    meta = result["meta"]
    lines = [
        f"## Evals: срез `{meta['slice']}`, {meta['predictor']} ({meta['predictor_version']})",
        "",
        f"{len(meta['records'])} отзывов, пакеты: {', '.join(meta['batches'])}. "
        f"Датасет `{meta['dataset']}` sha256 `{meta['dataset_sha256'][:12]}`.",
        "",
        "| Метрика | Проверка | Порог | Факт | Итог |",
        "|---|---|---|---|---|",
    ]
    for kind, rows in (("блокирует", gates), ("цель PRD", targets)):
        for row in rows:
            m = result["metrics"][row["metric"]]
            fact = fmt(row["actual"])
            if m["den"] is not None and m["num"] is not None:
                fact += f" ({m['num']}/{m['den']})"
            mark = "✅" if row["passed"] else ("❌" if kind == "блокирует" else "⚠️")
            lines.append(
                f"| `{row['metric']}` | {kind} | {row['op']} {fmt(row['value'])} | {fact} | {mark} |"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slice", choices=["fast", "full"], default="fast")
    ap.add_argument("--predictor", choices=sorted(PREDICTORS), default="rules")
    ap.add_argument("--out", type=Path, help="куда сохранить JSON с результатами")
    ap.add_argument("--md", type=Path, help="куда сохранить таблицу метрик")
    a = ap.parse_args()

    result = evaluate(a.slice, a.predictor)
    # Пороги gates откалиброваны на быстром срезе; полный прогон — отчёт, не блок.
    gates = check(result, "gates") if a.slice == "fast" else []
    targets = check(result, "targets")
    result["gates"], result["targets"] = gates, targets
    table = markdown(result, gates, targets)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if a.md:
        a.md.parent.mkdir(parents=True, exist_ok=True)
        a.md.write_text(table, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(table)
    return 0 if all(g["passed"] for g in gates) else 1


if __name__ == "__main__":
    sys.exit(main())
