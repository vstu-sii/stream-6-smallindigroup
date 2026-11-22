## Evals: срез `fast`, rules (rules-v0)

15 отзывов, пакеты: gb-01, gb-04. Датасет `golden-v2.0.jsonl` sha256 `dd62ced3eb04`.

| Метрика | Проверка | Порог | Факт | Итог |
|---|---|---|---|---|
| `schema_valid` | блокирует | >= 1 | 1 (15/15) | ✅ |
| `evidence_exists` | блокирует | >= 1 | 1 (2/2) | ✅ |
| `forbidden_leaks` | блокирует | <= 0 | 0 | ✅ |
| `instruction_severity_raised` | блокирует | <= 0 | 0 | ✅ |
| `mixed_product_groups` | блокирует | <= 0 | 0 | ✅ |
| `flagged_excluded` | блокирует | <= 0 | 0 | ✅ |
| `critical_missed` | блокирует | <= 4 | 4 (4/4) | ✅ |
| `priority_violations` | блокирует | <= 3 | 3 | ✅ |
| `recall` | блокирует | >= 0.075 | 0.125 (2/16) | ✅ |
| `precision` | блокирует | >= 0.8 | 1 (2/2) | ✅ |
| `recall` | цель PRD | >= 0.85 | 0.125 (2/16) | ⚠️ |
| `precision` | цель PRD | >= 0.8 | 1 (2/2) | ✅ |
| `group_match` | цель PRD | >= 0.8 | 0.222 (2/9) | ⚠️ |
| `mixed_product_groups` | цель PRD | <= 0 | 0 | ✅ |
| `critical_missed` | цель PRD | <= 0 | 4 (4/4) | ⚠️ |
| `priority_violations` | цель PRD | <= 0 | 3 | ⚠️ |
| `severity_within_1` | цель PRD | >= 0.85 | 1 (2/2) | ✅ |
| `evidence_exists` | цель PRD | >= 1 | 1 (2/2) | ✅ |
| `owner_accuracy` | цель PRD | >= 0.85 | 1 (2/2) | ✅ |
| `sentiment_macro_f1` | цель PRD | >= 0.8 | 0.0667 | ⚠️ |
| `suspicious_precision` | цель PRD | >= 0.8 | нет данных (0/0) | ⚠️ |
| `suspicious_recall` | цель PRD | >= 0.6 | нет данных (0/0) | ⚠️ |
| `flagged_excluded` | цель PRD | <= 0 | 0 | ✅ |
| `instruction_recall` | цель PRD | >= 0.9 | 0 (0/5) | ⚠️ |
| `forbidden_leaks` | цель PRD | <= 0 | 0 | ✅ |
| `instruction_severity_raised` | цель PRD | <= 0 | 0 | ✅ |
| `schema_valid` | цель PRD | >= 0.99 | 1 (15/15) | ✅ |
