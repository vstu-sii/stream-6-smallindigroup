"""Lab 1: dependency-free development baseline, evaluator and opt-in LLM runner."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'docs/quality/golden-dataset/golden-v0.1.jsonl'
OUT = ROOT / 'docs/experiments/results/lab1'
LEVELS = ['none', 'low', 'medium', 'high', 'critical']
# Generic development rules. Tuned with knowledge of v0.1, NOT a held-out model.
RULES = {
    'delivery_delay': r'долго|задерж|шло\s+\d+',
    'not_delivered': r'не приш[её]л|не доставлен',
    'wrong_item': r'пришли два|не тот цвет|не ту модель',
    'defect_on_arrival': r'дырк|пятно|брак',
    'defect_after_use': r'разош[её]лся шов|сломал',
    'material_quality': r'катышк|сел[ао]\b|полинял|линяет',
    'size_mismatch': r'как XS|маломер|не соответствует размер',
    'description_mismatch': r'не та, что в описании|не соответствует описанию',
    'smell': r'воня|пахнет|запах',
    'safety_hazard': r'красн\w* пятн|аллерг|ожог',
}


def read_jsonl(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def dump(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def norm(s):
    return ' '.join(s.split())


def baseline(inp, version='rules-v0'):
    text = inp['text']
    # v1: intentionally small fix for a common negation, applied after v0.
    searchable = re.sub(r'не линяет', '', text, flags=re.I) if version == 'rules-v1' else text
    problems = []
    for code, pattern in RULES.items():
        if re.search(pattern, searchable, re.I):
            # Whole original sentence, not an invented/paraphrased citation.
            evidence = next((s.strip() for s in re.split(r'(?<=[.!?])\s+', text)
                             if re.search(pattern, s, re.I)), text)
            problems.append({'code': code, 'evidence': evidence})
    codes = {p['code'] for p in problems}
    severity = ('critical' if 'safety_hazard' in codes else
                'high' if codes & {'not_delivered', 'defect_on_arrival', 'material_quality'} else
                'medium' if codes else 'none')
    delivery = {'delivery_delay', 'not_delivered'}
    owner = ('marketplace' if codes and codes <= delivery else 'seller' if codes else None)
    return {'sentiment': 'negative' if codes else 'positive' if inp['rating'] >= 4 else 'neutral',
            'problems': problems, 'severity': severity, 'owner': owner,
            'suspicious': text.count('!!!') >= 3,
            'has_instruction': bool(re.search(r'игнорируй|СИСТЕМА:', text, re.I))}


def validate(pred):
    assert isinstance(pred, dict)
    assert pred['sentiment'] in ['positive', 'neutral', 'negative', 'mixed']
    assert pred['severity'] in LEVELS
    assert pred['owner'] in ['seller', 'marketplace', None]
    assert type(pred['suspicious']) is bool and type(pred['has_instruction']) is bool
    assert isinstance(pred['problems'], list)
    codes = []
    for p in pred['problems']:
        assert p['code'] in RULES and isinstance(p['evidence'], str) and p['evidence'].strip()
        codes.append(p['code'])
    assert len(codes) == len(set(codes))


def evaluate(records, runs):
    assert [r['id'] for r in records] == [r['id'] for r in runs]
    tp = fp = fn = ev_ok = ev_total = valid = owner = severity = sentiment = critical_ok = critical_n = 0
    errors = []
    latencies = []
    for rec, run in zip(records, runs):
        exp = rec['expected']
        pred = run.get('prediction')
        e = {p['code'] for p in exp['problems']}
        try:
            validate(pred)
            valid += 1
        except (AssertionError, KeyError, TypeError):
            pred = {'problems': [], 'severity': None, 'owner': '__invalid__', 'sentiment': None}
        p = {x['code'] for x in pred['problems']}
        tp += len(e & p); fp += len(p - e); fn += len(e - p)
        for x in pred['problems']:
            ev_total += 1
            # Require nonempty literal contiguous span. No ellipsis convention in model output.
            ev_ok += norm(x['evidence']) in norm(rec['input']['text'])
        owner += pred.get('owner') == exp['owner']
        severity += pred.get('severity') == exp['severity']
        sentiment += pred.get('sentiment') == exp['sentiment']
        if exp['severity'] == 'critical':
            critical_n += 1; critical_ok += pred.get('severity') == 'critical'
        mismatch = {}
        if p != e: mismatch['problems'] = {'missing': sorted(e-p), 'extra': sorted(p-e)}
        for key in ['severity', 'owner', 'sentiment', 'suspicious', 'has_instruction']:
            if pred.get(key) != exp[key]: mismatch[key] = {'expected': exp[key], 'actual': pred.get(key)}
        if mismatch: errors.append({'id': rec['id'], 'differences': mismatch})
        latencies.append(run['latency_seconds'])
    def ratio(a, b): return a / b if b else None
    return {'n': len(records), 'tp': tp, 'fp': fp, 'fn': fn,
            'problem_precision': ratio(tp, tp+fp), 'problem_recall': ratio(tp, tp+fn),
            'literal_evidence': {'valid': ev_ok, 'total': ev_total, 'ratio': ratio(ev_ok, ev_total)},
            'schema_valid': ratio(valid, len(records)), 'owner_accuracy_including_null': ratio(owner, len(records)),
            'severity_exact_accuracy': ratio(severity, len(records)),
            'sentiment_accuracy': ratio(sentiment, len(records)),
            'critical_recall': {'found': critical_ok, 'total': critical_n, 'ratio': ratio(critical_ok, critical_n)},
            'p95_seconds': sorted(latencies)[max(0, math.ceil(.95*len(latencies))-1)],
            'grouping': None, 'north_star': None, 'errors': errors}


def messages(rec, prompt):
    # Only input, never expected, tags or source; isolation from golden labels.
    return [{'role': 'system', 'content': prompt},
            {'role': 'user', 'content': json.dumps(rec['input'], ensure_ascii=False)}]


def llm_call(msgs, provider, model):
    key = os.environ.get('LAB1_API_KEY')
    if provider == 'yandex':
        url = 'https://llm.api.cloud.yandex.net/v1/chat/completions'
    elif provider == 'local':
        url = 'http://127.0.0.1:8001/v1/chat/completions'
    else:
        url = ('https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent')
    if provider != 'local' and not key: raise RuntimeError('Set LAB1_API_KEY in environment, never in notebook')
    headers = {'Content-Type': 'application/json'}
    if provider == 'gemini':
        headers['x-goog-api-key'] = key
        body = {'systemInstruction': {'parts': [{'text': msgs[0]['content']}]},
                'contents': [{'role': 'user', 'parts': [{'text': msgs[1]['content']}]}],
                'generationConfig': {'temperature': 0, 'maxOutputTokens': 1200, 'responseMimeType': 'application/json'}}
    else:
        if key: headers['Authorization'] = 'Bearer ' + key
        body = {'model': model, 'messages': msgs, 'temperature': 0,
                'max_tokens': 1200, 'response_format': {'type': 'json_object'}}
    # No automatic retries: requests can be billed even if response is lost.
    with urlopen(Request(url, json.dumps(body).encode(), headers), timeout=60) as resp:
        raw = json.load(resp)
    if provider == 'gemini':
        text = ''.join(p.get('text', '') for p in raw['candidates'][0]['content']['parts'])
        usage = raw.get('usageMetadata', {})
    else:
        text = raw['choices'][0]['message']['content']; usage = raw.get('usage', {})
    try: prediction = json.loads(text)
    except json.JSONDecodeError: prediction = None
    return prediction, text, usage, raw.get('model', model)


def run_experiment(provider, model, dataset=DATA, prompt_path=None, out=OUT, allow_network=False):
    dataset = Path(dataset).resolve()
    records = read_jsonl(dataset)
    started_at = datetime.now(timezone.utc).isoformat()
    if provider != 'rules' and not allow_network:
        raise RuntimeError('Live LLM calls require --allow-network and a configured endpoint/key')
    if not records or len(records) > 20:
        raise ValueError('Lab1 pilot is limited to 1–20 records, not a production batch runner')
    prompt = Path(prompt_path).read_text() if prompt_path else ''
    runs = []
    start = time.perf_counter()
    for rec in records:
        t = time.perf_counter()
        if provider == 'rules':
            pred = baseline(rec['input'], model)
            raw_text = json.dumps(pred, ensure_ascii=False); usage = {}; actual_model = model
        else:
            pred, raw_text, usage, actual_model = llm_call(messages(rec, prompt), provider, model)
        runs.append({'id': rec['id'], 'prediction': pred, 'raw_text': raw_text,
                     'latency_seconds': time.perf_counter()-t, 'usage': usage, 'returned_model': actual_model})
        # Persist after each response; a later request failure does not erase previous evidence.
        target = Path(out) / (model.replace('/', '_').replace(':', '_') +
                               ('-' + Path(prompt_path).stem if prompt_path else ''))
        target.mkdir(parents=True, exist_ok=True)
        (target / 'responses.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in runs))
    meta = {'started_at_utc': started_at,
            'provider': provider, 'model': model, 'dataset': str(Path(dataset).relative_to(ROOT)),
            'dataset_sha256': sha(dataset), 'runner_sha256': sha(__file__),
            'prompt_sha256': sha(prompt_path) if prompt_path else None,
            'python': sys.version.split()[0], 'platform': platform.platform(),
            'elapsed_seconds': time.perf_counter()-start,
            'tokens': None if provider == 'rules' else 'see usage per response',
            'inference_api_cost_rub': 0 if provider == 'rules' else None,
            'scope': 'development pilot; NOT product acceptance or independent validation'}
    report = {'metadata': meta, 'metrics': evaluate(records, runs)}
    dump(target / 'summary.json', report)
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--provider', choices=['rules', 'yandex', 'gemini', 'local'], default='rules')
    ap.add_argument('--model', default='rules-v0')
    ap.add_argument('--dataset', type=Path, default=DATA)
    ap.add_argument('--prompt', type=Path)
    ap.add_argument('--out', type=Path, default=OUT)
    ap.add_argument('--allow-network', action='store_true')
    a = ap.parse_args()
    if a.provider != 'rules' and not a.prompt: ap.error('LLM run requires --prompt')
    print(json.dumps(run_experiment(a.provider, a.model, a.dataset, a.prompt, a.out, a.allow_network),
                     ensure_ascii=False, indent=2))
