#!/usr/bin/env python3
"""Check frozen text, one-request TTS evidence and exact editing boundaries.

This checks recorded evidence and file structure, not acoustic truth or listening.
Only the Python standard library is required.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import unicodedata
import wave


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def compact(text):
    return ''.join(c for c in text if not c.isspace())


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def check(data, script, audio, synthesis=None, align_text=None, expected_resource='seed-tts-2.0'):
    errors, warnings = [], []
    report = {'ok': False, 'errors': errors, 'warnings': warnings}
    if not isinstance(data, dict):
        errors.append('时间轴根节点必须为对象')
        return report
    duration, fps = data.get('duration_ms'), data.get('fps')
    if not integer(data.get('schema_version')) or data['schema_version'] != 1:
        errors.append('schema_version 必须为整数 1')
    if not integer(duration) or duration <= 0:
        errors.append('duration_ms 必须为正整数')
        return report
    if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
        errors.append('fps 必须为有限正数')
        return report
    if data.get('example_only') is True:
        errors.append('示例时间轴不能作为真实制作输入')
    alignment = data.get('alignment')
    if not isinstance(alignment, dict):
        errors.append('alignment 必须为对象')
        alignment = {}
    if not isinstance(alignment.get('method'), str) or not alignment['method'].strip():
        errors.append('缺少声学对齐方法记录')
    if alignment.get('language') != 'zh':
        errors.append('对齐语言必须指定为 zh')
    if not isinstance(alignment.get('verified'), bool):
        errors.append('alignment.verified 必须为布尔值')
    if alignment.get('verified') is not True:
        warnings.append('整段逐字听验尚未完成，不能宣称全部验收通过')
    elif not isinstance(alignment.get('evidence'), str) or not alignment['evidence'].strip():
        errors.append('verified=true 必须记录核对证据')
    if alignment.get('timestamps_interpolated') is True:
        errors.append('禁止使用插值时间戳')
    warnings.append('本工具不能证明声学、试听、视觉或一次合成记录的真实性')

    script_hash = hashlib.sha256(script.strip().encode('utf-8')).hexdigest()
    if data.get('script_sha256') != script_hash:
        errors.append('定稿 SHA256 与时间轴不一致或缺失')
    if data.get('audio_sha256') != digest(audio):
        errors.append('音频 SHA256 与时间轴不一致或缺失')
    with wave.open(str(audio), 'rb') as wav:
        measured = round(wav.getnframes() * 1000 / wav.getframerate())
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getcomptype()) != (44100, 1, 2, 'NONE'):
            errors.append('源 WAV 必须为 44100Hz、单声道、16bit PCM')
    if measured != duration:
        errors.append(f'源 WAV 实测 {measured}ms 与时间轴 {duration}ms 不一致')

    phrases, shots = data.get('phrases'), data.get('shots')
    if not isinstance(phrases, list) or not phrases:
        errors.append('phrases 必须为非空数组')
        return report
    if not isinstance(shots, list) or not shots:
        errors.append('shots 必须为非空数组')
        return report
    indexed, ordered, texts, boundaries, previous_end = {}, [], [], {0, duration}, 0

    def span(item, label):
        if not isinstance(item, dict):
            errors.append(f'{label} 必须为对象')
            return None
        start, end = item.get('start_ms'), item.get('end_ms')
        if not integer(start) or not integer(end) or not 0 <= start < end <= duration:
            errors.append(f'{label} 时间区间无效')
            return None
        return start, end

    for i, phrase in enumerate(phrases):
        label = f'phrases[{i}]'
        interval = span(phrase, label)
        if interval is None:
            continue
        start, end = interval
        if start != previous_end:
            errors.append(f'{label} 存在空缺、重叠或乱序')
        previous_end = end
        pid, text = phrase.get('id'), phrase.get('text')
        if not isinstance(pid, str) or not pid or pid in indexed:
            errors.append(f'{label} id 缺失或重复')
            continue
        if not isinstance(text, str) or not text.strip():
            errors.append(f'{label} text 为空或无效')
            text = ''
        count = sum(not c.isspace() and not unicodedata.category(c).startswith('P') for c in text)
        if not 5 <= count <= 15:
            errors.append(f'{pid} 非标点字符数 {count}，须为 5–15')
        indexed[pid] = phrase
        ordered.append(pid)
        texts.append(text)
        boundaries.update(interval)
    if previous_end != duration:
        errors.append('末短语结束时间必须等于音频时长')
    if compact(''.join(texts)) != compact(script):
        errors.append('短语与定稿逐字不一致（只忽略排版空白，保留标点）')

    previous_end, assigned, shot_ids = 0, [], set()
    for i, shot in enumerate(shots):
        label = f'shots[{i}]'
        interval = span(shot, label)
        if interval is None:
            continue
        start, end = interval
        if start != previous_end:
            errors.append(f'{label} 镜头轨不连续')
        previous_end = end
        if start not in boundaries or end not in boundaries:
            errors.append(f'{label} 切点不在原短语边界')
        if round(end * fps / 1000) <= round(start * fps / 1000):
            errors.append(f'{label} 量化后不足一帧')
        sid = shot.get('id')
        if sid != f'S{i+1:03d}' or sid in shot_ids:
            errors.append(f'{label} 镜头编号必须从 S001 连续递增')
        if isinstance(sid, str):
            shot_ids.add(sid)
        if shot.get('roll') not in ('A', 'B'):
            errors.append(f'{label} roll 必须为 A 或 B')
        if not isinstance(shot.get('purpose'), str) or not shot['purpose'].strip():
            errors.append(f'{label} 缺少理解或情绪目标')
        ids = shot.get('phrase_ids')
        if not isinstance(ids, list) or not ids or any(not isinstance(pid, str) for pid in ids):
            errors.append(f'{label} phrase_ids 必须为非空字符串数组')
            ids = []
        assigned.extend(ids)
        for pid in ids:
            phrase = indexed.get(pid)
            if phrase is None or not start <= phrase['start_ms'] < phrase['end_ms'] <= end:
                errors.append(f'{label} 未知、切断或错误归属短语 {pid}')
        events = shot.get('events')
        if not isinstance(events, list) or not events:
            errors.append(f'{label} events 必须为非空数组')
            continue
        last_event = start
        for n, event in enumerate(events):
            elabel = f'{label}.events[{n}]'
            if not isinstance(event, dict):
                errors.append(f'{elabel} 必须为对象')
                continue
            at, pid = event.get('at_ms'), event.get('phrase_id')
            if not integer(at) or not last_event <= at < end:
                errors.append(f'{elabel} 时间无效或乱序')
                continue
            last_event = at
            if not isinstance(pid, str) or pid not in ids or pid not in indexed or at != indexed[pid]['start_ms']:
                errors.append(f'{elabel} 未严格取引用短语的起点')
            if not isinstance(event.get('change'), str) or not event['change'].strip():
                errors.append(f'{elabel} 缺少有效信息变化说明')
    if previous_end != duration:
        errors.append('镜头轨未覆盖到音频结尾')
    if assigned != ordered:
        errors.append('镜头必须按原序且仅一次覆盖全部短语')

    if align_text is not None:
        rows = []
        for line in align_text.splitlines():
            match = re.fullmatch(r'\[(\d+)ms-(\d+)ms\] (.+)', line)
            if not match:
                errors.append('vo-align.txt 行格式必须严格为 [开始ms-结束ms] 原文')
                break
            rows.append((int(match[1]), int(match[2]), compact(match[3])))
        expected = [(p['start_ms'], p['end_ms'], compact(p['text'])) for p in indexed.values()]
        if rows != expected:
            errors.append('vo-align.txt 与时间轴短语、文字或端点不一致')
    else:
        warnings.append('未提供 --align-text，未核对 TXT 交付物')
    if synthesis is not None:
        if not isinstance(synthesis, dict):
            errors.append('一次合成记录必须为对象')
        else:
            if not integer(synthesis.get('request_count')) or synthesis['request_count'] != 1:
                errors.append('一次合成记录的 request_count 必须为整数 1')
            if synthesis.get('resource_id') != expected_resource:
                errors.append(f'一次合成记录的资源与预期 {expected_resource} 不一致')
            if synthesis.get('script_sha256') != script_hash or synthesis.get('duration_ms') != measured:
                errors.append('一次合成记录与定稿或音频时长不一致')
            receipt_audio_hash = synthesis.get('audio_sha256')
            if receipt_audio_hash is not None and receipt_audio_hash != data.get('audio_sha256'):
                errors.append('一次合成记录的音频 SHA256 与实际音频不一致')
            if expected_resource != 'seed-tts-2.0' and receipt_audio_hash is None:
                errors.append('替代配音服务的回执必须包含音频 SHA256')
            report['voice_id'] = synthesis.get('speaker')
            report['expected_resource'] = expected_resource
    else:
        if expected_resource != 'seed-tts-2.0':
            errors.append('替代配音服务必须提供 --synthesis 全文合成回执')
        else:
            warnings.append('未提供 --synthesis，无法核对全文一次合成记录')
    report.update(ok=not errors, audio_duration_ms=measured, phrase_count=len(phrases),
                  final_end_ms=phrases[-1].get('end_ms') if isinstance(phrases[-1], dict) else None,
                  shot_count=len(shots))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('timeline', type=Path)
    parser.add_argument('--script', required=True, type=Path)
    parser.add_argument('--audio', required=True, type=Path)
    parser.add_argument('--synthesis', type=Path)
    parser.add_argument('--expected-resource', default='seed-tts-2.0',
                        help='本次已授权的配音资源；替代服务需显式指定并提供音频哈希')
    parser.add_argument('--align-text', type=Path)
    args = parser.parse_args()
    try:
        read = lambda p: p.read_text(encoding='utf-8-sig')
        report = check(json.loads(read(args.timeline)), read(args.script), args.audio,
                       json.loads(read(args.synthesis)) if args.synthesis else None,
                       read(args.align_text) if args.align_text else None,
                       args.expected_resource)
    except (OSError, ValueError, TypeError, KeyError, wave.Error, EOFError) as exc:
        report = {'ok': False, 'errors': [f'无法校验：{type(exc).__name__}: {exc}'], 'warnings': []}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
