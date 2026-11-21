"""Offline MLX trials for Lab1. Run after downloading the pinned model snapshot."""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
import hashlib
import platform
import sys
import subprocess
import time
from pathlib import Path

from run import ROOT, DATA, OUT, read_jsonl, messages, evaluate, dump, sha


def parse_prediction(text):
    """Strict parser: no repair and no stripping Markdown to improve scores."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def hardware_info():
    result = subprocess.run(['/usr/sbin/system_profiler', 'SPHardwareDataType', '-json'],
                            capture_output=True, text=True)
    if result.returncode:
        return {'machine': platform.machine()}
    rows = json.loads(result.stdout).get('SPHardwareDataType', [])
    return {k: row[k] for row in rows for k in ('chip_type', 'physical_memory', 'number_processors') if k in row}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-dir', type=Path, default=ROOT/'.local-llm/models/Qwen3-4B-4bit')
    ap.add_argument('--session', default='local-qwen3-4b-pilot')
    ap.add_argument('--repeat', type=int, default=3)
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--prompts', nargs='+', choices=['p0','p1','p2'], default=['p0','p1'])
    args = ap.parse_args()
    if not args.session.replace('-', '').replace('_', '').isalnum() or not 1 <= args.repeat <= 3:
        ap.error('Use a simple session name and 1–3 repeats')
    if not (args.model_dir/'model.safetensors').is_file():
        ap.error('Download pinned weights first; this runner does not download or call cloud APIs')
    session = OUT/args.session
    session.mkdir(parents=True, exist_ok=False)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    os.environ['HF_HOME'] = str(ROOT/'.local-llm/hf-cache')
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    load_start = time.perf_counter()
    model, tokenizer = load(str(args.model_dir), trust_remote_code=False)
    load_seconds = time.perf_counter()-load_start
    revision = (ROOT/'.local-llm/model-revision.txt').read_text().strip()
    protocol = {'started_at_utc':datetime.now(timezone.utc).isoformat(),
        'model':'mlx-community/Qwen3-4B-4bit','model_revision':revision,
        'weights_sha256':file_digest(args.model_dir/'model.safetensors'),
        'runner_sha256':sha(__file__),'evaluator_sha256':sha(ROOT/'experiments/lab1/run.py'),
        'environment':{'python':platform.python_version(),'machine':platform.machine(),
                       'mlx':version('mlx'),'mlx-lm':version('mlx-lm'),'transformers':version('transformers')},
        'hardware':hardware_info(),
        'load_seconds':load_seconds,'temperature':0,'seed':0,'enable_thinking':False,
        'max_output_tokens':800,'network_during_inference':False,'cloud_api_cost_rub':0,
        'parse_policy':'strict json.loads, no extraction or repair',
        'prompts':['p1'] if args.smoke else args.prompts,
        'scope':'synthetic development/diagnostic pilot, not independent validation'}
    dump(session/'protocol.json',protocol)
    inputs = [('golden', DATA, read_jsonl(DATA)),
              ('challenge', ROOT/'experiments/lab1/challenge-v0.1.jsonl',
               read_jsonl(ROOT/'experiments/lab1/challenge-v0.1.jsonl'))]
    if args.smoke:
        inputs = [('smoke', DATA, read_jsonl(DATA)[:1])]
    for repeat in range(1 if args.smoke else args.repeat):
        for prompt_name in (['p1'] if args.smoke else args.prompts):
            prompt_path=ROOT/'experiments/lab1/prompts'/f'{prompt_name}.txt'
            prompt=prompt_path.read_text()
            for name, data_path, records in inputs:
                target=session/f'{name}-{prompt_name}-repeat-{repeat+1}'
                target.mkdir()
                runs=[]
                start=time.perf_counter()
                for record in records:
                    mx.random.seed(0)
                    encoded=tokenizer.apply_chat_template(messages(record,prompt),tokenize=True,
                        add_generation_prompt=True,enable_thinking=False)
                    before=time.perf_counter()
                    chunks=[]; last=None
                    for response in stream_generate(model,tokenizer,encoded,max_tokens=800,
                                                     sampler=make_sampler(temp=0)):
                        chunks.append(response.text); last=response
                    if last is None: raise RuntimeError('No generation response')
                    text=''.join(chunks)
                    row={'id':record['id'],'prediction':parse_prediction(text) if last.finish_reason == 'stop' else None,'raw_text':text,
                         'latency_seconds':time.perf_counter()-before,
                         'prompt_tokens':last.prompt_tokens,'generation_tokens':last.generation_tokens,
                         'prompt_tokens_per_second':last.prompt_tps,
                         'generation_tokens_per_second':last.generation_tps,
                         'process_peak_mlx_memory_gb':last.peak_memory,'finish_reason':last.finish_reason,
                         'api_cost_rub':0}
                    runs.append(row)
                    (target/'responses.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in runs))
                    print(f'{name} {prompt_name} r{repeat+1} {len(runs)}/{len(records)}: '
                          f'{row["latency_seconds"]:.1f}s, {last.generation_tokens} tokens, '
                          f'{last.generation_tps:.1f} tok/s, peak {last.peak_memory:.2f} GB, '
                          f'JSON={row["prediction"] is not None}, finish={last.finish_reason}',flush=True)
                dump(target/'summary.json',{'metadata':{'model':protocol['model'],'repeat':repeat+1,
                    'dataset_sha256':sha(data_path),'prompt_sha256':sha(prompt_path),
                    'elapsed_seconds':time.perf_counter()-start,
                    'prompt_tokens':sum(r['prompt_tokens'] for r in runs),
                    'generation_tokens':sum(r['generation_tokens'] for r in runs),
                    'cloud_api_cost_rub':0,'local_electricity_cost':'not measured'},
                    'metrics':evaluate(records,runs)})
    dump(session/'completed.json',{'status':'complete','completed_at_utc':datetime.now(timezone.utc).isoformat(),
                                 'repeats':1 if args.smoke else args.repeat,'cloud_api_cost_rub':0})
    print('COMPLETE',flush=True)


if __name__ == '__main__':
    main()
