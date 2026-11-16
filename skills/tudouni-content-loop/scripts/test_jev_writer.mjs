import test from 'node:test';
import assert from 'node:assert/strict';
import { cleanEvidence, decideWritingState } from './jev-writer.mjs';

const ready = { submitted: false, composer_ready: true, model_verified: true };
const done = { submitted: true, model_verified: true, generation_active: false,
  completion_visible: true, current_response_confirmed: true, response_json_complete: true };
function mock(choice, confidence = 0.99, inspect = () => {}) {
  return { apiKey: 'test-only-key', fetchImpl: async (url, init) => {
    inspect(url, init);
    return { ok: true, json: async () => ({ answers: { next_step: { choice, confidence } } }) };
  } };
}
test('sanitized observations only go to fixed official endpoint', async () => {
  const r = await decideWritingState({ ...ready, email: 'private@example.test', body: 'private' },
    mock('prepare', 0.99, (url, init) => {
      assert.equal(url, 'https://api.typesafe.ai/v1/systemone');
      assert.equal(init.redirect, 'error');
      assert.ok(!init.body.includes('private'));
      assert.ok(!init.body.includes('test-only-key'));
    }));
  assert.equal(r.decision, 'prepare');
  assert.equal(r.browser_action_executed, false);
});
test('unknown evidence cannot authorize prepare', async () => {
  assert.equal((await decideWritingState({}, mock('prepare'))).decision, 'unknown');
});
test('extract needs every completion, attribution and model observation', async () => {
  assert.equal((await decideWritingState(done, mock('extract'))).decision, 'extract');
  for (const flag of Object.keys(done)) {
    assert.equal((await decideWritingState({ ...done, [flag]: null }, mock('extract'))).decision, 'unknown');
  }
});
test('active generation and blockers override model advice', async () => {
  assert.equal((await decideWritingState({ ...done, generation_active: true }, mock('extract'))).decision, 'wait');
  assert.equal((await decideWritingState({ ...ready, blocker: 'region_unavailable' }, mock('prepare'))).decision, 'blocked');
});
test('low confidence does not authorize extraction', async () => {
  assert.equal((await decideWritingState(done, mock('extract', 0.5))).decision, 'unknown');
});
test('free text in state fields is rejected', () => {
  assert.throws(() => cleanEvidence({ submitted: 'Bearer secret' }), /INVALID_EVIDENCE/);
  assert.throws(() => cleanEvidence({ blocker: 'https://private.example/' }), /INVALID_BLOCKER/);
});
test('bad response and HTTP failures are bounded and sanitized', async () => {
  await assert.rejects(() => decideWritingState(done, mock('run_shell')), /INVALID_ANSWER/);
  await assert.rejects(() => decideWritingState(done, mock('extract', 2)), /INVALID_ANSWER/);
  let calls = 0;
  await assert.rejects(() => decideWritingState(done, { apiKey: 'test-only-key', fetchImpl: async () => {
    calls++; return { ok: false, status: 401 };
  } }), /JEV_HTTP_401/);
  assert.equal(calls, 1);
});
