"""Build compact tables from complete, immutable local inference artifacts."""
import json
from pathlib import Path
from run import ROOT, OUT, dump
from summarize_local import summarize


def percent(x):
    return 'нет данных' if x is None else f'{100*x:.1f}%'


def main():
    sessions = [OUT/'local-qwen3-4b-pilot', OUT/'local-qwen3-4b-p2']
    comparisons = []
    for session in sessions:
        if not (session/'completed.json').exists():
            raise RuntimeError('Incomplete session: '+session.name)
        comparisons.append(summarize(session))
    groups = [g for c in comparisons for g in c['groups']]
    groups.sort(key=lambda g:(g['dataset']!='golden',g['prompt']))
    total = sum(c['total_calls'] for c in comparisons)
    table = ['# Реальные локальные прогоны: таблицы результатов', '',
             'Qwen3-4B-4bit · MLX · Apple M1 Pro / 16 GB · 21.11.2026.', '',
             f'Основные серии: **{total} генераций** = 20 уникальных синтетических отзывов × 3 промпта × 3 повтора. ',
             'Отдельно выполнен один smoke-запрос. Облачные LLM не вызывались.', '',
             'Наборы использованы при разработке/анализе; независимой проверки здесь нет. ',
             'P2 разработан после просмотра ошибок P0/P1 на этих данных. Три greedy-повтора ',
             'проверяют воспроизводимость, не дают трёх независимых наблюдений.', '',
             '## Извлечение проблем и формат', '',
             '| Набор | Промпт | TP / FP / FN | Precision | Recall | Схема | Цитаты-подстроки | Critical (только уровень) |',
             '|---|---|---|---|---|---|---|---|']
    for g in groups:
        m = g['first_run_metrics']
        table.append(f'| {g["dataset"]} (n={g["unique_records"]}) | {g["prompt"].upper()} | '
                     f'{m["tp"]} / {m["fp"]} / {m["fn"]} | {percent(m["problem_precision"])} | '
                     f'{percent(m["problem_recall"])} | {percent(m["schema_valid"])} | '
                     f'{m["literal_evidence"]["valid"]}/{m["literal_evidence"]["total"]} | '
                     f'{m["critical_recall"]["found"]}/{m["critical_recall"]["total"]} |')
    stable = all(g['predictions_identical_across_repeats'] for g in groups)
    table.extend(['',f'Предсказания одинаковы во всех трёх повторах каждой группы: **{stable}**. ',
                  'В таблице приведён первый повтор; все метрики каждого повтора доступны в JSON. ',
                  'Метрика critical проверяет severity; правильность кода safety_hazard проверяется ',
                  'отдельно в precision/recall и ручном разборе. Одна верная отметка critical не доказывает безопасность.', '',
                  '## Остальные метки', '',
                  '| Набор | Промпт | Owner с null | Серьёзность exact | Тональность accuracy |',
                  '|---|---|---|---|---|'])
    for g in groups:
        m = g['first_run_metrics']
        table.append(f'| {g["dataset"]} | {g["prompt"].upper()} | {percent(m["owner_accuracy_including_null"])} | '
                     f'{percent(m["severity_exact_accuracy"])} | {percent(m["sentiment_accuracy"])} |')
    table.extend(['','## Время и ресурсы','','| Набор | Промпт | Среднее, с | p95 по повторам, с | Пик MLX, GB | Входные / выходные токены за 3 повтора |',
                  '|---|---|---|---|---|---|'])
    for g in groups:
        p = g['metrics_range']['p95_seconds']
        table.append(f'| {g["dataset"]} | {g["prompt"].upper()} | {g["mean_latency_seconds"]:.2f} | '
                     f'{p["min"]:.2f}–{p["max"]:.2f} | {g["max_mlx_memory_gb"]:.2f} | '
                     f'{g["total_prompt_tokens"]} / {g["total_generation_tokens"]} |')
    table.extend(['','Пик памяти — метрика MLX, не весь расход RAM системы. Время загрузки модели ',
                  'сохранено в protocol.json, отдельно от запроса. P95 на 8–12 строках — ',
                  'ориентир для пилота, не нагрузочное испытание. Все остановки по лимиту ',
                  f'выхода: {sum(g["length_stops"] for g in groups)}. Невалидный JSON и неправильные типы ',
                  'не исправлялись автоматически. Стоимость облачного API — **0 ₽**; электричество/амортизация не измерены.', '',
                  '## Доказательства и воспроизведение', '',
                  '- [P0/P1: comparison.json](results/lab1/local-qwen3-4b-pilot/comparison.json).',
                  '- [P2: comparison.json](results/lab1/local-qwen3-4b-p2/comparison.json).',
                  '- В каждой подпапке: responses.jsonl и summary.json; в корне сессии: protocol.json и completed.json.',
                  '- [Промпты и команды](../../experiments/lab1/README.md).',
                  '- [Ручной разбор и выводы](lab1.md).', '',
                  'Таблицы построены `experiments/lab1/report_local.py` из сохранённых ответов; новых генераций он не выполняет.'])
    (ROOT/'docs/experiments/local-results.md').write_text('\n'.join(line.rstrip() for line in table)+'\n')
    dump(OUT/'local-comparison-all.json',{'total_main_calls':total,'groups':groups,'all_predictions_stable':stable})
    print('Generated local-results.md, main calls:',total)


if __name__=='__main__':
    main()
