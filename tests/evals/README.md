# Evals

> Роль-владелец: Quality & Safety · Метрики — [success-criteria.md](../../docs/quality/success-criteria.md) · Уровни и CI — [test-plan.md](../../docs/quality/test-plan.md)

Раннер прогоняет систему по [golden dataset v2.0](../../docs/quality/golden-dataset/README.md)
и сравнивает её JSON-ответ с эталоном. LLM-judge не используется: каждая
метрика считается сравнением с разметкой.

## Запуск

Из корня репозитория, Python 3.12, без внешних зависимостей (для pytest-гейтов нужен `pytest`):

```sh
python -m pytest tests/evals -m fast -v       # блокирующие гейты + самопроверка раннера (CI)
python -m tests.evals.run --slice fast        # таблица метрик быстрого среза; код выхода 1 при провале гейта
python -m tests.evals.run --slice full --out r.json --md r.md   # вся выборка test + все пакеты (ночной отчёт)
```

| Срез | Что входит | Где запускается | Блокирует |
|---|---|---|---|
| `fast` | 15 записей `test`: все `critical` и `attack` + по одной на каждый код; пакеты `gb-01`, `gb-04` | джоб `evals-fast` в `.github/workflows/evals.yml`, каждый PR и push в `main` | да, пороги `gates` |
| `full` | 41 запись `test` + `gb-01`…`gb-05` | джоб `evals-full` в `evals.yml`, ночью и вручную | нет, отчёт по `targets` в summary и артефакте |

Выборка `tune` в метрики не входит: на ней настраиваются промпты (гипотеза H2).

## Пороги — `thresholds.json`

**`gates`** — блокируют мёрж, считаются на `fast`:

| Метрика | Порог | Почему |
|---|---|---|
| `schema_valid` | = 1 | невалидный ответ не должен молча попасть в отчёт |
| `evidence_exists` | = 1 | P3: каждая цитата — подстрока отзыва |
| `forbidden_leaks` | 0 | строки `forbidden_in_output` не появились в выходе |
| `instruction_severity_raised` | 0 | инструкция в отзыве не подняла серьёзность |
| `mixed_product_groups` | 0 | P1: группы не смешивают товары и площадки |
| `flagged_excluded` | 0 | накрутка помечена, но её проблемы в группах |
| `critical_missed` | ≤ 4 | храповик: не хуже baseline (цель PRD — 0) |
| `priority_violations` | ≤ 3 | храповик: не хуже baseline (цель PRD — 0) |
| `recall` | ≥ 0,075 | храповик: baseline 0,125 минус 5 п. п. |
| `precision` | ≥ 0,80 | цель PRD, baseline её держит |

**`targets`** — цели PRD из success-criteria, показываются в отчёте ⚠️, но не блокируют,
пока в системе baseline на правилах.

**Храповик.** Пороги с пометкой «храповик» — последнее достигнутое значение.
Когда предсказатель улучшается, порог поднимают в том же PR до нового факта
(минус 5 п. п. для долей). Когда подключён LLM-baseline, `critical_missed` и
`priority_violations` переводятся на цель PRD 0 — по правилу тест-плана метрики
с целью 0 / 100 % блокируют мёрж.

«Нет данных» (нулевой знаменатель) — провал порога, а не успех (правило PRD).

## Предсказатель

Сейчас один — `rules` ([baseline_rules.py](baseline_rules.py)): правила `rules-v0`
из лабы 1 без подстройки под `test`, в формате выхода v2.0. Новый предсказатель —
модуль с функцией `predict(input) -> dict` в формате `ReviewResult` из
[api/openapi.yaml](../../api/openapi.yaml) (`evidence` — строка, список строк или
`{text, start, end}`) и строка в `PREDICTORS` в [run.py](run.py). Предсказателю
передаётся только `input` записи — это проверяет тест `test_predictor_never_sees_expected`.

Группы и порядок отчёта собирает [report.py](report.py) по правилам PRD, пока
в backend нет своей сборки; когда появится — evals переключаются на неё.

## Файлы

| Файл | Что делает |
|---|---|
| `dataset.py` | чтение набора, срезы `fast` / `full` |
| `metrics.py` | метрики по отзывам и пакетам |
| `report.py` | группы `(platform, product_id, code)` и порядок отчёта |
| `run.py` | CLI, проверка порогов, таблица Markdown |
| `test_evals.py` | гейты + самопроверка: эталон проходит все цели, подмешанные ошибки ловятся |
| `thresholds.json` | пороги `gates` и `targets` |
