#!/usr/bin/env python3
"""Local, versioned editorial handoff. No browser, model, TTS or publish calls."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


def require(condition, message):
    if not condition:
        raise ValueError(message)


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def parse_json(text):
    return json.loads(text, object_pairs_hook=no_duplicate_keys)


def read_json(path):
    return parse_json(Path(path).read_text(encoding='utf-8'))


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def script_hash(text):
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def identity(obj, expected=None):
    require(isinstance(obj, dict), 'object required')
    require(isinstance(obj.get('task_id'), str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', obj['task_id']), 'invalid task_id')
    require(type(obj.get('revision')) is int and obj['revision'] > 0, 'invalid revision')
    if expected is not None:
        require((obj['task_id'], obj['revision']) == (expected['task_id'], expected['revision']), 'task or revision mismatch')


def packet_from(path):
    obj = read_json(path)
    identity(obj)
    source = Path(obj['source_path'])
    require(source.is_absolute() and source.is_file(), 'source file unavailable')
    require(file_hash(source) == obj['source_sha256'], 'source changed; review the facts again')
    writer = obj.get('writer', {})
    require(nonempty(writer.get('provider')), 'writer provider required')
    if writer['provider'] != 'local':
        require(nonempty(writer.get('requested_model')), 'requested model required')
    brief = obj.get('brief')
    require(isinstance(brief, dict), 'brief required')
    for field in ('topic', 'audience', 'goal', 'draft', 'visual_evidence'):
        require(nonempty(brief.get(field)), 'brief field missing: ' + field)
    facts = brief.get('facts')
    require(isinstance(facts, list) and facts, 'facts required')
    ids = []
    for fact in facts:
        require(isinstance(fact, dict) and nonempty(fact.get('id')) and nonempty(fact.get('statement')) and nonempty(fact.get('evidence')), 'invalid fact')
        ids.append(fact['id'])
    require(len(ids) == len(set(ids)), 'duplicate fact id')
    required = brief.get('required_fact_ids', [])
    require(isinstance(required, list) and all(isinstance(x, str) for x in required) and set(required) <= set(ids), 'invalid required facts')
    quotes = brief.get('locked_quotes', [])
    require(isinstance(quotes, list) and all(nonempty(q) for q in quotes), 'invalid locked quotes')
    low, high = brief.get('min_chars', 1), brief.get('max_chars', 100000)
    require(type(low) is int and type(high) is int and 1 <= low <= high, 'invalid length range')
    return obj


def validate_response(raw, packet):
    text = raw.strip()
    if text.startswith('```'):
        match = re.fullmatch(r'```(?:json)?\s*\n([\s\S]*?)\n```', text)
        require(match is not None, 'invalid fenced response')
        text = match.group(1)
    obj = parse_json(text)
    identity(obj, packet)
    fields = {'task_id', 'revision', 'completion', 'script', 'used_fact_ids', 'unresolved', 'change_notes'}
    require(set(obj) == fields, 'missing or unknown response fields')
    require(obj['completion'] == 'complete', 'response is not complete; resolve missing input')
    require(obj['unresolved'] == [], 'response has unresolved input')
    require(isinstance(obj['change_notes'], list) and all(isinstance(x, str) for x in obj['change_notes']), 'invalid change notes')
    require(nonempty(obj['script']), 'empty script')
    script = obj['script'].strip()
    count = len(re.sub(r'\s+', '', script))
    brief = packet['brief']
    require(brief.get('min_chars', 1) <= count <= brief.get('max_chars', 100000), 'script outside length range')
    require(not re.search(r'```|SCRIPT_BEGIN|SCRIPT_END|REPLY_DONE|\[TODO\]|\[待补\]', script), 'protocol or placeholder in script')
    paragraphs = [re.sub(r'\s+', '', p) for p in re.split(r'\n+', script) if len(p.strip()) >= 12]
    require(len(paragraphs) == len(set(paragraphs)), 'duplicate long paragraph; review repetition')
    for quote in brief.get('locked_quotes', []):
        require(quote in script, 'locked quote missing')
    used = obj['used_fact_ids']
    require(isinstance(used, list) and all(isinstance(x, str) for x in used), 'invalid used fact ids')
    require(len(used) == len(set(used)), 'duplicate used fact id')
    known = {x['id'] for x in brief['facts']}
    require(set(used) <= known and set(brief.get('required_fact_ids', [])) <= set(used), 'unknown or missing fact ids')
    return script, count


def validate_receipt(path, packet):
    if packet['writer']['provider'] == 'local':
        require(path is None, 'local writer must not attach a web receipt')
        return
    require(path is not None, 'web writer receipt required')
    receipt = read_json(path)
    identity(receipt, packet)
    writer = packet['writer']
    require(receipt.get('provider') == writer['provider'] and receipt.get('requested_model') == writer['requested_model'], 'writer receipt mismatch')
    require(nonempty(receipt.get('observed_model')) and receipt.get('model_verified') is True, 'model observation not verified')
    require(receipt.get('response_complete') is True, 'web response not complete')
    url = urlsplit(receipt.get('conversation_url', ''))
    require(url.scheme == 'https' and bool(url.hostname) and not url.username and not url.password, 'invalid conversation URL')
    if writer['provider'] == 'gemini_web':
        require(url.hostname == 'gemini.google.com', 'wrong Gemini origin')
    times = [datetime.fromisoformat(receipt[x].replace('Z', '+00:00')) for x in ('submitted_at', 'completed_at')]
    require(all(t.tzinfo is not None for t in times) and times[1] >= times[0], 'invalid receipt times')


def reference(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': file_hash(path)}


def check_reference(ref):
    require(file_hash(ref['path']) == ref['sha256'], 'referenced file changed')


def write_new(path, text):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(text)


def json_text(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2) + '\n'


def export_prompt(packet_path, out):
    packet = packet_from(packet_path)
    public = {'task_id': packet['task_id'], 'revision': packet['revision'], 'brief': packet['brief']}
    response = {'task_id': packet['task_id'], 'revision': packet['revision'], 'completion': 'complete', 'script': '完整口播正文', 'used_fact_ids': packet['brief'].get('required_fact_ids', []), 'unresolved': [], 'change_notes': []}
    prompt = '请依据以下写作包写一份完整中文口播。仅使用包内事实，保留条件、否定和作者判断；不得补造经历、收入或实测结果。语言自然，画面能兑现承诺。正文只包含可朗读文字，不含标题、分镜、时间码或修改说明。\n\n'
    prompt += json_text(public)
    prompt += '\n只返回一个符合以下字段的JSON对象，不要在对象前后附加文字。正文放script。事实不足时completion为needs_input、script为null，并在unresolved列明具体问题；不得编成定稿。\n'
    prompt += json_text(response)
    write_new(out, prompt)
    return {'status': 'exported', 'out': str(Path(out).resolve())}


def accept(packet_path, response_path, receipt_path, out_dir):
    packet = packet_from(packet_path)
    script, count = validate_response(Path(response_path).read_text(encoding='utf-8'), packet)
    validate_receipt(receipt_path, packet)
    record = {'task_id': packet['task_id'], 'revision': packet['revision'], 'packet': reference(packet_path), 'source': reference(packet['source_path']), 'response': reference(response_path), 'receipt': reference(receipt_path) if receipt_path else None, 'script_sha256': script_hash(script), 'chars': count, 'facts_reviewed': False}
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=False)
    write_new(out / 'candidate.txt', script + '\n')
    write_new(out / 'accepted.json', json_text(record))
    return {'status': 'accepted', 'chars': count, 'script_sha256': record['script_sha256'], 'packet_sha256': record['packet']['sha256'], 'facts_reviewed': False}


def accepted_from(directory):
    directory = Path(directory).resolve()
    record = read_json(directory / 'accepted.json')
    for field in ('packet', 'source', 'response'):
        check_reference(record[field])
    if record['receipt'] is not None:
        check_reference(record['receipt'])
    packet = packet_from(record['packet']['path'])
    identity(record, packet)
    receipt_path = record['receipt']['path'] if record['receipt'] else None
    validate_receipt(receipt_path, packet)
    raw_script, count = validate_response(Path(record['response']['path']).read_text(encoding='utf-8'), packet)
    candidate = (directory / 'candidate.txt').read_text(encoding='utf-8').strip()
    require(candidate == raw_script and script_hash(candidate) == record['script_sha256'], 'candidate differs from accepted response')
    require(record['source']['path'] == str(Path(packet['source_path']).resolve()), 'source reference mismatch')
    return record, candidate


def validate_review(path, record):
    review = read_json(path)
    identity(review, record)
    require(review.get('packet_sha256') == record['packet']['sha256'] and review.get('script_sha256') == record['script_sha256'], 'review hashes mismatch')
    require(isinstance(review.get('checks'), dict) and all(review['checks'].get(x) == 'pass' for x in ('facts', 'intent', 'speakable', 'visual_support')), 'editorial review incomplete')
    notes = review.get('evidence_notes')
    require(isinstance(notes, list) and notes and all(nonempty(x) for x in notes), 'review evidence required')
    choice = review.get('selection', {})
    require(choice.get('allowed_to_produce') is True and nonempty(choice.get('basis')), 'no recorded authority to produce')


def freeze(accepted_dir, review_path, out_dir):
    record, script = accepted_from(accepted_dir)
    validate_review(review_path, record)
    out = Path(out_dir).resolve()
    accepted_dir = Path(accepted_dir).resolve()
    handoff = {'schema_version': 1, 'task_id': record['task_id'], 'revision': record['revision'], 'accepted': reference(accepted_dir / 'accepted.json'), 'candidate': reference(accepted_dir / 'candidate.txt'), 'review': reference(review_path), 'script_path': str(out / 'script.txt'), 'script_sha256': script_hash(script), 'production_skill': 'tudouni-ai-video', 'audio_path': None, 'timeline_path': None, 'duration_ms': None}
    out.mkdir(parents=True, exist_ok=False)
    write_new(out / 'script.txt', script + '\n')
    write_new(out / 'handoff.json', json_text(handoff))
    return {'status': 'frozen', 'handoff': str(out / 'handoff.json'), 'script_sha256': handoff['script_sha256']}


def verify(handoff_path):
    handoff = read_json(handoff_path)
    require(handoff.get('schema_version') == 1, 'unsupported handoff schema')
    for field in ('accepted', 'candidate', 'review'):
        check_reference(handoff[field])
    accepted_dir = Path(handoff['accepted']['path']).parent
    require(Path(handoff['candidate']['path']) == accepted_dir / 'candidate.txt', 'candidate reference mismatch')
    record, candidate = accepted_from(accepted_dir)
    identity(handoff, record)
    validate_review(handoff['review']['path'], record)
    script = Path(handoff['script_path']).read_text(encoding='utf-8').strip()
    require(script == candidate and script_hash(script) == handoff['script_sha256'], 'frozen script changed')
    return {'status': 'verified', 'task_id': handoff['task_id'], 'revision': handoff['revision'], 'script_sha256': handoff['script_sha256'], 'audio_verified': False, 'video_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    exp = sub.add_parser('export')
    exp.add_argument('--packet', required=True); exp.add_argument('--out', required=True)
    acc = sub.add_parser('accept')
    acc.add_argument('--packet', required=True); acc.add_argument('--response', required=True)
    acc.add_argument('--receipt'); acc.add_argument('--out-dir', required=True)
    frz = sub.add_parser('freeze')
    frz.add_argument('--accepted', required=True); frz.add_argument('--review', required=True); frz.add_argument('--out-dir', required=True)
    ver = sub.add_parser('verify'); ver.add_argument('--handoff', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'export':
            result = export_prompt(args.packet, args.out)
        elif args.command == 'accept':
            result = accept(args.packet, args.response, args.receipt, args.out_dir)
        elif args.command == 'freeze':
            result = freeze(args.accepted, args.review, args.out_dir)
        else:
            result = verify(args.handoff)
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        print(json_text({'status': 'failed', 'reason': str(error)}), end='')
        return 1
    print(json_text(result), end='')
    return 0


if __name__ == '__main__':
    sys.exit(main())
