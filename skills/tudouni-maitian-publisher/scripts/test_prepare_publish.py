#!/usr/bin/env python3
"""Exercise real media, immutable packaging and refusal paths without uploading."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('prepare_publish', Path(__file__).with_name('prepare_publish.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg/ffprobe required')
class PrepareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.root = Path(cls.fixture.name)
        cls.video = cls.root / 'video.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:r=10', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '0.5', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', str(cls.video)], check=True)
        for key, size in (('vertical', '60x80'), ('horizontal', '80x60')):
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=' + size, '-frames:v', '1', str(cls.root / (key + '.png'))], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ('video.mp4', 'vertical.png', 'horizontal.png'):
            shutil.copy2(self.__class__.root / name, self.root / name)
        self.manifest = self.root / '交接.json'
        self.data = {'package': str(self.root), 'title': 'Gemini写稿测试', 'video': {'file': 'video.mp4', 'sha256': m.digest(self.root / 'video.mp4'), 'fileSize': (self.root / 'video.mp4').stat().st_size}, 'checks': {'technicalOk': True, 'hasAudio': True}, 'publishing': {'mode': 'draft-only', 'approved': False, 'draftUploadAuthorized': True, 'allowImmediate': False, 'allowSchedule': False}, 'platforms': {p: {'account': {'id': 'test-account'}, 'accountConfirmedByUser': True, 'title': 'Gemini口播测试', 'body': '使用Gemini写稿，由Codex审核。', 'topics': ['AI教程'], 'covers': {'vertical': 'vertical.png', 'horizontal': 'horizontal.png'}} for p in m.PLATFORMS}}

    def tearDown(self):
        self.temp.cleanup()

    def run_prepare(self, platform='douyin'):
        self.manifest.write_text(json.dumps(self.data, ensure_ascii=False))
        return m.prepare(self.manifest, platform, self.root / 'out')

    def test_real_bundle_and_independent_media(self):
        self.assertEqual(self.run_prepare()['status'], 'prepared')
        out = self.root / 'out'
        b = json.loads((out / 'publish.json').read_text())
        self.assertEqual(set(b['platforms']), {'douyin'})
        self.assertNotIn('schedule', b)
        self.assertEqual(set(b['covers']), {'3x4', '4x3'})
        self.assertEqual(m.digest(out / '成片.mp4'), self.data['video']['sha256'])
        self.assertNotEqual((out / '成片.mp4').stat().st_ino, (self.root / 'video.mp4').stat().st_ino)
        self.assertFalse(json.loads((out / 'handoff-check.json').read_text())['platformDraftVerified'])
        with self.assertRaisesRegex(ValueError, '输出已存在'):
            self.run_prepare()

    def test_xhs_only_requires_portrait(self):
        del self.data['platforms']['xiaohongshu']['covers']['horizontal']
        self.run_prepare('xiaohongshu')
        b = json.loads((self.root / 'out/publish.json').read_text())
        self.assertEqual(set(b['platforms']), {'xhs'})
        self.assertEqual(set(b['covers']), {'3x4'})

    def test_hash_mismatch(self):
        self.data['video']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            self.run_prepare()
        self.assertFalse((self.root / 'out').exists())

    def test_refuse_publish_schedule_and_missing_account_confirmation(self):
        original = copy.deepcopy(self.data)
        for key, value in (('allowImmediate', True), ('allowSchedule', True), ('approved', True), ('draftUploadAuthorized', False)):
            self.data = copy.deepcopy(original)
            self.data['publishing'][key] = value
            with self.assertRaisesRegex(ValueError, '授权'):
                self.run_prepare()
        self.data = original
        self.data['platforms']['douyin']['accountConfirmedByUser'] = False
        with self.assertRaisesRegex(ValueError, '账号'):
            self.run_prepare()

    def test_refuse_known_draft(self):
        for key, value in (('draftEvidence', ['already-saved']), ('draftId', 'old'), ('published', True), ('scheduled', True), ('status', '平台草稿已核验')):
            with self.subTest(key=key):
                self.data['platforms']['douyin'][key] = value
                with self.assertRaisesRegex(ValueError, '已有'):
                    self.run_prepare()
                del self.data['platforms']['douyin'][key]

    def test_refuse_outside_asset_and_wrong_ratio(self):
        self.data['platforms']['douyin']['covers']['vertical'] = '../outside.png'
        with self.assertRaisesRegex(ValueError, '越出'):
            self.run_prepare()
        self.data['platforms']['douyin']['covers']['vertical'] = 'horizontal.png'
        with self.assertRaisesRegex(ValueError, '比例'):
            self.run_prepare()

    def test_actual_audio_required(self):
        silent = self.root / 'silent.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(self.root / 'video.mp4'), '-an', '-c:v', 'copy', str(silent)], check=True)
        self.data['video'] = {'file': 'silent.mp4', 'sha256': m.digest(silent), 'fileSize': silent.stat().st_size}
        with self.assertRaisesRegex(ValueError, '实际文件缺少'):
            self.run_prepare()


if __name__ == '__main__':
    unittest.main()
