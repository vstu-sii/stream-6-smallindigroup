"""Aggregate saved local runs without generating new answers."""
import argparse
import json
from pathlib import Path
from statistics import mean
from run import ROOT, OUT, dump, read_jsonl


def summarize(session):
    session = Path(session)
    summaries = []
    grouped = {}
    for p in sorted(session.glob('*/summary.json')):
        name = p.parent.name
        dataset, prompt, _, repeat = name.split('-')
        rows = read_jsonl(p.parent/'responses.jsonl')
        d = json.loads(p.read_text())
        summaries.append({'run': name, 'metadata': d['metadata'], 'metrics': d['metrics']})
        grouped.setdefault((dataset,prompt),[]).append((int(repeat),rows,d))
    result = {'protocol':json.loads((session/'protocol.json').read_text()),'groups':[],
              'total_calls':0,'cloud_api_cost_rub':0,'independent_evaluation':False}
    for (dataset,prompt),runs in sorted(grouped.items()):
        runs.sort()
        metrics = [r[2]['metrics'] for r in runs]
        all_rows = [row for _,rows,_ in runs for row in rows]
        result['total_calls'] += len(all_rows)
        first = runs[0][1]
        stable = all([x['prediction'] for x in rows]==[x['prediction'] for x in first]
                     for _,rows,_ in runs)
        scalars = ['problem_precision','problem_recall','schema_valid',
                   'owner_accuracy_including_null','severity_exact_accuracy','sentiment_accuracy','p95_seconds']
        metric_range = {key:{'min':min(m[key] for m in metrics),'max':max(m[key] for m in metrics)}
                        for key in scalars if all(m[key] is not None for m in metrics)}
        result['groups'].append({'dataset':dataset,'prompt':prompt,'repeats':len(runs),
            'unique_records':len(first),'calls':len(all_rows),'predictions_identical_across_repeats':stable,
            'metrics_range':metric_range,'first_run_metrics':metrics[0],
            'mean_latency_seconds':mean(r['latency_seconds'] for r in all_rows),
            'max_mlx_memory_gb':max(r['process_peak_mlx_memory_gb'] for r in all_rows),
            'total_prompt_tokens':sum(r['prompt_tokens'] for r in all_rows),
            'total_generation_tokens':sum(r['generation_tokens'] for r in all_rows),
            'length_stops':sum(r['finish_reason']=='length' for r in all_rows)})
    dump(session/'comparison.json',result)
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('session',type=Path)
    args=ap.parse_args()
    print(json.dumps(summarize(args.session),ensure_ascii=False,indent=2))
