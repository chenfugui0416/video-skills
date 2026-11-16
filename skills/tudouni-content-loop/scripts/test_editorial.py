"""Offline behavioral checks; never open browsers or call models/TTS."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import editorial as e


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tudouni-editorial-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.md'
        self.source.write_text('材料没有日期，不补造日期。', encoding='utf-8')
        self.packet = {'task_id': 'TD-test', 'revision': 1, 'source_path': str(self.source), 'source_sha256': e.file_hash(self.source), 'writer': {'provider': 'local'}, 'brief': {'topic': '核对清单', 'audience': 'AI新手', 'goal': '不补造日期', 'draft': '材料没有写日期。', 'visual_evidence': '人工示意清单', 'facts': [{'id': 'F1', 'statement': '材料没有日期', 'evidence': '本次示例'}], 'required_fact_ids': ['F1'], 'locked_quotes': ['标为待确认'], 'min_chars': 5, 'max_chars': 200}}
        self.packet_path = self.root / 'packet.json'
        self.save(self.packet_path, self.packet)
        self.reply = {'task_id': 'TD-test', 'revision': 1, 'completion': 'complete', 'script': '先核对原文，没有日期就标为待确认。', 'used_fact_ids': ['F1'], 'unresolved': [], 'change_notes': []}
        self.response = self.root / 'response.txt'
        self.save(self.response, self.reply)

    def save(self, path, obj):
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')

    def accepted(self):
        directory = self.root / 'accepted'
        e.accept(self.packet_path, self.response, None, directory)
        return directory

    def review(self, accepted):
        record = e.read_json(accepted / 'accepted.json')
        path = self.root / 'review.json'
        self.save(path, {'task_id': 'TD-test', 'revision': 1, 'packet_sha256': record['packet']['sha256'], 'script_sha256': record['script_sha256'], 'checks': {x: 'pass' for x in ('facts', 'intent', 'speakable', 'visual_support')}, 'evidence_notes': ['已对照示例，原文没有日期，画面标明人工示意。'], 'selection': {'allowed_to_produce': True, 'basis': 'test only'}})
        return path

    def frozen(self):
        accepted = self.accepted()
        review = self.review(accepted)
        e.freeze(accepted, review, self.root / 'frozen')
        return self.root / 'frozen/handoff.json'

    def test_complete_roundtrip_and_exclusive_output(self):
        handoff = self.frozen()
        self.assertEqual(e.verify(handoff)['status'], 'verified')
        self.assertIsNone(e.read_json(handoff)['duration_ms'])
        with self.assertRaises(FileExistsError):
            e.freeze(self.root / 'accepted', self.root / 'review.json', self.root / 'frozen')

    def test_export_excludes_local_paths_and_private_packet_fields(self):
        self.packet['private_context'] = 'THIS_MUST_STAY_LOCAL'
        self.save(self.packet_path, self.packet)
        out = self.root / 'prompt.txt'
        e.export_prompt(self.packet_path, out)
        text = out.read_text()
        self.assertNotIn(str(self.root), text)
        self.assertNotIn('THIS_MUST_STAY_LOCAL', text)

    def test_reject_stale_task_and_version(self):
        for field, value in [('task_id', 'other'), ('revision', 2), ('revision', True)]:
            with self.subTest(field=field, value=value):
                obj = dict(self.reply, **{field: value})
                with self.assertRaises(ValueError):
                    e.validate_response(json.dumps(obj), self.packet)

    def test_reject_duplicate_json_keys_and_trailing_draft(self):
        for raw in [json.dumps(self.reply)[:-1] + ',"script":"另一篇"}', json.dumps(self.reply) + '\n第二篇']:
            with self.assertRaises(ValueError):
                e.validate_response(raw, self.packet)

    def test_accept_only_whole_json_fence(self):
        raw = '```json\n' + json.dumps(self.reply) + '\n```'
        self.assertEqual(e.validate_response(raw, self.packet)[0], self.reply['script'])
        with self.assertRaises(ValueError):
            e.validate_response(raw + '\n别的稿子', self.packet)

    def test_reject_missing_input_empty_and_unknown_fields(self):
        for changes in [{'completion': 'needs_input', 'script': None, 'unresolved': ['缺材料']}, {'script': ''}, {'another_script': '另一篇'}, {'unresolved': ['未核实']}]:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    e.validate_response(json.dumps(dict(self.reply, **changes)), self.packet)

    def test_fact_ids_and_locked_quote(self):
        for changes in [{'used_fact_ids': []}, {'used_fact_ids': ['F2']}, {'script': '这里直接写一个日期就行。'}]:
            with self.assertRaises(ValueError):
                e.validate_response(json.dumps(dict(self.reply, **changes)), self.packet)

    def test_repeat_and_length_limits(self):
        text = self.reply['script']
        for changes in [{'script': text + '\n' + text}, {'script': text * 30}]:
            with self.assertRaises(ValueError):
                e.validate_response(json.dumps(dict(self.reply, **changes)), self.packet)

    def test_source_change_blocks_accept(self):
        self.source.write_text('新增了明确日期')
        with self.assertRaises(ValueError):
            self.accepted()
        self.assertFalse((self.root / 'accepted').exists())

    def test_candidate_change_blocks_freeze(self):
        accepted = self.accepted()
        review = self.review(accepted)
        (accepted / 'candidate.txt').write_text('替换正文')
        with self.assertRaises(ValueError):
            e.freeze(accepted, review, self.root / 'frozen')

    def test_incomplete_review_cannot_freeze(self):
        accepted = self.accepted()
        review = self.review(accepted)
        obj = e.read_json(review)
        obj['checks']['visual_support'] = 'pending'
        self.save(review, obj)
        with self.assertRaises(ValueError):
            e.freeze(accepted, review, self.root / 'frozen')

    def test_frozen_inputs_changes_block_verify(self):
        handoff = self.frozen()
        paths = [self.source, self.packet_path, self.response, self.root / 'review.json', self.root / 'frozen/script.txt']
        for path in paths:
            with self.subTest(path=path.name):
                data = path.read_bytes()
                path.write_bytes(data + b' change')
                with self.assertRaises(ValueError):
                    e.verify(handoff)
                path.write_bytes(data)

    def test_web_receipt_required_and_validated(self):
        self.packet['writer'] = {'provider': 'gemini_web', 'requested_model': 'test-model'}
        self.save(self.packet_path, self.packet)
        with self.assertRaises(ValueError):
            e.accept(self.packet_path, self.response, None, self.root / 'accepted')
        path = self.root / 'receipt.json'
        receipt = {'task_id': 'TD-test', 'revision': 1, 'provider': 'gemini_web', 'requested_model': 'test-model', 'observed_model': 'test-model', 'model_verified': True, 'conversation_url': 'https://gemini.google.com/app/test', 'submitted_at': '2026-10-08T10:00:00+08:00', 'completed_at': '2026-10-08T10:01:00+08:00', 'response_complete': True}
        self.save(path, receipt)
        e.validate_receipt(path, self.packet)
        for field, value in [('model_verified', False), ('response_complete', False), ('requested_model', 'other'), ('conversation_url', 'https://example.com')]:
            with self.subTest(field=field):
                self.save(path, dict(receipt, **{field: value}))
                with self.assertRaises(ValueError):
                    e.validate_receipt(path, self.packet)


if __name__ == '__main__':
    unittest.main(verbosity=2)
