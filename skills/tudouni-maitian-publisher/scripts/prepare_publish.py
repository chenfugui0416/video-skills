#!/usr/bin/env python3
"""Prepare one local Maitian draft bundle; never uploads or publishes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

PLATFORMS = {'douyin': ('douyin', ('3x4', '4x3')), 'xiaohongshu': ('xhs', ('3x4',))}
ALIASES = {'3x4': ('3x4', 'vertical', 'portrait'), '4x3': ('4x3', 'horizontal', 'landscape')}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def local(package, name):
    require(isinstance(name, str) and name.strip(), '文件引用为空')
    path = (package / name).resolve()
    require(path.is_relative_to(package) and path.is_file(), '文件缺失或越出发布包')
    return path


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def prepare(manifest, platform, out):
    manifest, out = Path(manifest).resolve(), Path(out).absolute()
    require(platform in PLATFORMS, '只支持抖音或小红书')
    require(not out.exists() and not out.is_symlink(), '输出已存在，请先核对旧任务，不能重复导出')
    data = json.loads(manifest.read_text(encoding='utf-8'))
    package = Path(data['package']).resolve()
    require(manifest.is_relative_to(package), '交接文件不在发布包内')
    pub = data['publishing']
    require(pub.get('mode') == 'draft-only' and pub.get('approved') is False and pub.get('draftUploadAuthorized') is True and pub.get('allowImmediate') is False and pub.get('allowSchedule') is False, '必须明确授权上传草稿，并关闭发布和排期')
    require(not data.get('schedule'), '不接收排期')
    item = data['platforms'][platform]
    require(item.get('accountConfirmedByUser') is True and item.get('account', {}).get('id'), '目标账号未由用户确认')
    require(not any(item.get(k) for k in ('published', 'scheduled', 'draftEvidence', 'draftUrl', 'draftId')), '已有发布/排期/草稿证据，请先核对，不能重复上传')
    require(item.get('status') not in ('已发布', '已排期', '草稿已保存', '平台草稿已核验', '已上传草稿'), '已有处理状态，请先核对')
    require(not item.get('schedule'), '平台含排期')
    require(data.get('checks', {}).get('technicalOk') is True and data['checks'].get('hasAudio') is True, '成片技术验收或音轨未通过')
    require(isinstance(item.get('title'), str) and item['title'].strip() and isinstance(item.get('body'), str) and item['body'].strip(), '缺少完整标题或正文')
    limits = (30, 0) if platform == 'douyin' else (20, 1)
    require(len(item['title']) <= limits[0] and limits[1] <= len(item['body']) <= 1000, '标题或正文超出插件字段范围')
    topics = item.get('topics', [])
    require(isinstance(topics, list) and all(isinstance(t, str) and t.strip() for t in topics), 'topics 必须是非空字符串列表')
    require(platform != 'douyin' or len(topics) <= 5, '抖音话题超过5个')
    if item.get('copyFile'):
        local(package, item['copyFile'])
    video = local(package, data['video']['file'])
    require(video.suffix.lower() == '.mp4' and digest(video) == data['video']['sha256'] and video.stat().st_size == data['video']['fileSize'], '成片格式、SHA256或大小不符')
    info = probe(video)
    require(any(s['codec_type'] == 'audio' for s in info['streams']) and any(s['codec_type'] == 'video' for s in info['streams']), '实际文件缺少视频或音轨')
    target, ratios = PLATFORMS[platform]
    covers = {}
    for ratio in ratios:
        name = next((item.get('covers', {}).get(k) for k in ALIASES[ratio] if item.get('covers', {}).get(k)), None)
        path = local(package, name)
        require(path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'), '封面必须是图片文件')
        visual = next((s for s in probe(path)['streams'] if s['codec_type'] == 'video'), {})
        w, h = visual.get('width', 0), visual.get('height', 0)
        a, b = map(int, ratio.split('x'))
        require(h > 0 and abs(w / h - a / b) < 0.02, '封面比例不符：需要' + ratio + '，请另存适配封面，不覆盖原图')
        covers[ratio] = path
    cover_hashes = {k: digest(p) for k, p in covers.items()}
    fingerprint = hashlib.sha256(json.dumps({'platform': platform, 'account': item['account']['id'], 'video': data['video']['sha256'], 'title': item['title'], 'body': item['body'], 'topics': topics, 'covers': cover_hashes}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    bundle = {'version': 1, 'id': fingerprint[:24], 'name': data.get('title', item['title']), 'video': '成片.mp4', 'durationSec': float(info['format']['duration']), 'covers': {k: '封面/' + k + p.suffix.lower() for k, p in covers.items()}, 'platforms': {target: {'title': item['title'], 'body': item['body'], 'topics': topics, 'covers': list(ratios)}}}
    receipt = {'schemaVersion': 1, 'executor': 'maitian-ego', 'mode': 'draft-only', 'fingerprint': fingerprint, 'manifestSha256': digest(manifest), 'platform': platform, 'account': item['account'], 'videoSha256': data['video']['sha256'], 'coverSha256': cover_hashes, 'aiDeclaration': item.get('aiDeclaration'), 'stage': 'prepared', 'pageAccountVerified': False, 'platformDraftVerified': False}
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.maitian-', dir=out.parent))
    try:
        (temp / '封面').mkdir()
        # Independent copies: editing a prepared bundle must not alter original media.
        shutil.copy2(video, temp / bundle['video'])
        for key, path in covers.items():
            shutil.copy2(path, temp / bundle['covers'][key])
        (temp / 'publish.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (temp / 'handoff-check.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        require(not out.exists(), '输出已存在')
        os.rename(temp, out)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return {'status': 'prepared', 'platform': platform, 'id': bundle['id'], 'out': str(out), 'uploaded': False, 'platformDraftVerified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--platform', choices=PLATFORMS, required=True)
    parser.add_argument('--out-dir', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.manifest, args.platform, args.out_dir), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, '拒绝导出：' + str(error) + '\n')


if __name__ == '__main__':
    main()
