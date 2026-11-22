## Evals: срез `full`, rules (rules-v0)

41 отзывов, пакеты: gb-01, gb-02, gb-03, gb-04, gb-05. Датасет `golden-v2.0.jsonl` sha256 `dd62ced3eb04`.

| Метрика | Проверка | Порог | Факт | Итог |
|---|---|---|---|---|
| `recall` | цель PRD | >= 0.85 | 0.286 (10/35) | ⚠️ |
| `precision` | цель PRD | >= 0.8 | 0.833 (10/12) | ✅ |
| `group_match` | цель PRD | >= 0.8 | 0.478 (11/23) | ⚠️ |
| `mixed_product_groups` | цель PRD | <= 0 | 0 | ✅ |
| `critical_missed` | цель PRD | <= 0 | 4 (4/4) | ⚠️ |
| `priority_violations` | цель PRD | <= 0 | 5 | ⚠️ |
| `severity_within_1` | цель PRD | >= 0.85 | 1 (10/10) | ✅ |
| `evidence_exists` | цель PRD | >= 1 | 1 (12/12) | ✅ |
| `owner_accuracy` | цель PRD | >= 0.85 | 0.9 (9/10) | ✅ |
| `sentiment_macro_f1` | цель PRD | >= 0.8 | 0.267 | ⚠️ |
| `suspicious_precision` | цель PRD | >= 0.8 | 1 (1/1) | ✅ |
| `suspicious_recall` | цель PRD | >= 0.6 | 0.25 (1/4) | ⚠️ |
| `flagged_excluded` | цель PRD | <= 0 | 0 | ✅ |
| `instruction_recall` | цель PRD | >= 0.9 | 0 (0/5) | ⚠️ |
| `forbidden_leaks` | цель PRD | <= 0 | 1 | ⚠️ |
| `instruction_severity_raised` | цель PRD | <= 0 | 0 | ✅ |
| `schema_valid` | цель PRD | >= 0.99 | 1 (41/41) | ✅ |
