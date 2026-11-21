"""Bounded Yandex pilot. Credentials remain local; every attempted request is journaled."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone, timedelta, date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from run import ROOT, DATA, OUT, read_jsonl, evaluate, messages, sha, dump

CONFIG = ROOT / '.env.yandex.local'
ENDPOINT = 'https://ai.api.cloud.yandex.net/v1/chat/completions'
INPUT_RUB = 0.10 / 1000
OUTPUT_RUB = 0.20 / 1000
MAX_OUTPUT = 1200


def configuration():
    cfg = {}
    if CONFIG.exists():
        for line in CONFIG.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                k, sep, v = line.partition('=')
                if sep:
                    cfg[k.strip()] = v.strip().strip('\"\'')
    for key in ('YANDEX_API_KEY', 'YANDEX_FOLDER_ID'):
        if os.getenv(key):
            cfg[key] = os.environ[key]
    return cfg


def require_free_trial(cfg, budget_rub, today=None):
    """Fail closed: this runner must never authorize pay-as-you-go usage."""
    today = today or datetime.now(timezone(timedelta(hours=3))).date()
    if cfg.get('YANDEX_BILLING_STATUS') != 'TRIAL_ACTIVE':
        raise ValueError('Free-only mode requires confirmed TRIAL_ACTIVE status; no paid transition allowed')
    try:
        remaining = float(cfg['YANDEX_GRANT_REMAINING_RUB'])
        expires = date.fromisoformat(cfg['YANDEX_GRANT_EXPIRES'])
    except (ValueError, KeyError):
        raise ValueError('Grant amount and expiry must be confirmed in Billing') from None
    if not remaining >= budget_rub + 1 or expires <= today:
        raise ValueError('Grant is insufficient, expiring today, expired, or unconfirmed')
    return remaining


def usage_cost(usage):
    # Cache ignored intentionally: upper estimate at uncached rate, not billing invoice.
    incoming = usage.get('prompt_tokens')
    outgoing = usage.get('completion_tokens')
    if type(incoming) is not int or type(outgoing) is not int or min(incoming, outgoing) < 0:
        return None
    return incoming * INPUT_RUB + outgoing * OUTPUT_RUB


def reserve_cost(msgs):
    # UTF-8 bytes are a conservative tokenizer bound; reserve extra framing tokens.
    incoming_upper = sum(len(m['content'].encode('utf-8')) for m in msgs) + 1024
    return incoming_upper * INPUT_RUB + MAX_OUTPUT * OUTPUT_RUB


def safe_prediction(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def perform(msgs, cfg):
    model = 'gpt://' + cfg['YANDEX_FOLDER_ID'] + '/aliceai-llm-flash'
    body = {'model': model, 'messages': msgs, 'temperature': 0,
            'max_tokens': MAX_OUTPUT, 'response_format': {'type': 'json_object'}}
    headers = {'Authorization': 'Api-Key ' + cfg['YANDEX_API_KEY'],
               'Content-Type': 'application/json', 'OpenAI-Project': cfg['YANDEX_FOLDER_ID']}
    request = Request(ENDPOINT, data=json.dumps(body, ensure_ascii=False).encode(), headers=headers)
    with urlopen(request, timeout=60) as response:
        raw = json.load(response)
    choice = raw['choices'][0]
    text = choice['message'].get('content') or ''
    # Defensive redaction: credentials and folder are never saved in results.
    for secret in (cfg['YANDEX_API_KEY'], cfg['YANDEX_FOLDER_ID']):
        text = text.replace(secret, '[REDACTED]')
    return {'prediction': safe_prediction(text), 'raw_text': text,
            'usage': raw.get('usage', {}), 'finish_reason': choice.get('finish_reason'),
            'returned_model': str(raw.get('model', 'aliceai-llm-flash')).replace(cfg['YANDEX_FOLDER_ID'], '[FOLDER]')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check-config', action='store_true')
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--repeat', type=int, default=3)
    ap.add_argument('--budget-rub', type=float)
    ap.add_argument('--allow-grant-usage', action='store_true')
    ap.add_argument('--session', default='yandex-first-trials')
    args = ap.parse_args()
    cfg = configuration()
    ready = bool(cfg.get('YANDEX_API_KEY')) and bool(re.fullmatch(r'[A-Za-z0-9_-]{8,80}', cfg.get('YANDEX_FOLDER_ID', '')))
    if args.check_config:
        print(json.dumps({'key_present': bool(cfg.get('YANDEX_API_KEY')), 'folder_configured': bool(cfg.get('YANDEX_FOLDER_ID')), 'ready': ready}))
        return
    if not ready:
        sys.exit('Configure YANDEX_API_KEY and YANDEX_FOLDER_ID locally in .env.yandex.local; do not paste secrets into chat.')
    if not args.allow_grant_usage or args.budget_rub is None or not 0 < args.budget_rub <= 50:
        sys.exit('Explicit --allow-grant-usage and --budget-rub between 0 and 50 required')
    try:
        require_free_trial(cfg, args.budget_rub)
    except ValueError as exc:
        sys.exit(str(exc))
    if not 1 <= args.repeat <= 3 or not re.fullmatch(r'[a-zA-Z0-9_-]+', args.session):
        sys.exit('Invalid repeat/session')
    session = OUT / args.session
    session.mkdir(parents=True, exist_ok=True)
    ledger = session / 'journal.jsonl'
    if ledger.exists():
        sys.exit('Session already exists; review journal before making more calls. No implicit retry.')
    records = read_jsonl(DATA)
    datasets = [('golden', DATA, records)]
    if not args.smoke:
        challenge = ROOT / 'experiments/lab1/challenge-v0.1.jsonl'
        datasets.append(('challenge', challenge, read_jsonl(challenge)))
    else:
        datasets = [('smoke', DATA, records[:1])]
    spent = 0.0
    jobs = [(name, path, rows, prompt, repeat)
            for repeat in range(1 if args.smoke else args.repeat)
            for prompt in (['p1'] if args.smoke else ['p0', 'p1'])
            for name, path, rows in datasets]
    dump(session / 'protocol.json', {'endpoint': ENDPOINT, 'model': 'aliceai-llm-flash',
        'runner_sha256': sha(__file__), 'evaluator_sha256': sha(ROOT/'experiments/lab1/run.py'),
        'budget_rub': args.budget_rub, 'funding':'verified free trial grant only', 'date_utc': datetime.now(timezone.utc).isoformat(),
        'temperature':0,'max_tokens':MAX_OUTPUT,'automatic_retries':0,
        'tariff_checked':'2026-11-21', 'input_rub_per_1000':.1,'output_rub_per_1000':.2,
        'price_source':'https://aistudio.yandex.ru/ru/docs/ai-studio/pricing',
        'scope':'development pilot, synthetic examples; not product acceptance'})
    for name, path, rows, prompt_name, repeat in jobs:
        prompt_path = ROOT / 'experiments/lab1/prompts' / (prompt_name + '.txt')
        prompt = prompt_path.read_text()
        target = session / (f'{name}-{prompt_name}-repeat-{repeat+1}')
        target.mkdir()
        runs = []
        started = time.perf_counter()
        for record in rows:
            msgs = messages(record, prompt)
            reserve = reserve_cost(msgs)
            if spent + reserve > args.budget_rub:
                sys.exit('Stopped before request: insufficient budget reserve. Existing outputs preserved.')
            event = {'dataset':name,'id':record['id'],'prompt':prompt_name,'repeat':repeat+1,
                     'reserved_rub':reserve, 'utc':datetime.now(timezone.utc).isoformat()}
            with ledger.open('a') as f:
                f.write(json.dumps(dict(event,status='attempt'),ensure_ascii=False)+'\n')
                f.flush(); os.fsync(f.fileno())
            before = time.perf_counter()
            try:
                result = perform(msgs, cfg)
            except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
                # Do not print provider response bodies or credential-bearing request headers.
                event['status']='failed_or_unknown_charge'
                event['error_type']=type(exc).__name__
                event['http_status']=getattr(exc,'code',None)
                with ledger.open('a') as f: f.write(json.dumps(event)+'\n')
                sys.exit('Request failed; saved reservation, no retry. Error: '+type(exc).__name__+' status='+str(getattr(exc,'code',None)))
            result['id'] = record['id']
            result['latency_seconds'] = time.perf_counter()-before
            cost = usage_cost(result['usage'])
            result['uncached_cost_estimate_rub'] = cost
            runs.append(result)
            (target/'responses.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in runs))
            event.update(status='completed', usage_cost_rub=cost)
            with ledger.open('a') as f: f.write(json.dumps(event)+'\n')
            if cost is None or cost > reserve:
                sys.exit('Usage missing or exceeds reservation: outputs saved; stop for billing review.')
            spent += cost
            print(f'{name} {prompt_name} repeat={repeat+1}: {len(runs)}/{len(rows)}, cumulative <= {spent:.4f} RUB', flush=True)
        dump(target/'summary.json',{'metadata':{'model':'aliceai-llm-flash',
            'dataset_sha256':sha(path),'prompt_sha256':sha(prompt_path),
            'elapsed_seconds':time.perf_counter()-started,
            'cost_estimate_rub':sum(r['uncached_cost_estimate_rub'] for r in runs),
            'prompt_tokens':sum(r['usage']['prompt_tokens'] for r in runs),
            'completion_tokens':sum(r['usage']['completion_tokens'] for r in runs)},
            'metrics':evaluate(rows,runs)})
    dump(session/'completed.json',{'status':'complete','cost_estimate_rub':spent,
                                'runs':len(jobs),'actual_invoice_checked':False})
    print('COMPLETE. Uncached cost estimate: '+str(round(spent,4))+' RUB')


if __name__ == '__main__':
    main()
