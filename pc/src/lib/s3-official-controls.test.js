import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { s3ButtonRows } from './s3-controls.js';
const source = readFileSync(new URL('../DeviceDashboard.jsx', import.meta.url), 'utf8');
const start = source.indexOf('export const P4_BUTTON_CONTROL_ROWS =');
const declaration = source.slice(start, source.indexOf('\n];', start) + 3);
const official = new Function('P4_CUSTOM_ACTION_OPTIONS', 'P4_DEFAULT_VOICE_TRIGGER', 'P4_DEFAULT_PROMPT',
  declaration.replace('export const', 'const') + '; return P4_BUTTON_CONTROL_ROWS;')(
  ['page_enter', 'page_back', 'component_center', 'realtime_chat', 'session_previous', 'session_next', 'disabled'], 'sw1.hold', '');
const rows = s3ButtonRows(official);
test('A4 has all official gestures and new preference identities', () => {
  assert.equal(rows.length, 12);
  assert.deepEqual(rows.map(({id, controlId, ...row}) => row), official.map(({id, controlId, ...row}) => row));
  assert.ok(rows.every(row => row.id.startsWith('s3j_')));
  assert.equal(new Set(rows.map(row => row.controlId)).size, 4);
});
test('A4 wire bindings preserve confirm/back/PTT and four directions', () => {
  const fn = source.slice(source.indexOf('export function buildBoardButtonConfigBindings'), source.indexOf('function createButtonConfigRequestId'));
  const build = new Function('buttonControlRowsForRuntime', 'clampButtonActionValue',
    fn.replace('export function', 'function') + ';return buildBoardButtonConfigBindings;')(() => rows, value => value);
  const bindings = build({}, {}, 'esp-s3', true);
  assert.equal(bindings.length, 16);
  const action = event => bindings.find(binding => binding.event === event)?.action;
  assert.equal(action('button.sw1.short_press'), 'page_enter');
  assert.equal(action('button.sw1.hold'), 'voice_ptt');
  assert.equal(action('button.sw2.short_press'), 'component_center');
  assert.equal(action('button.sw2.long_press'), 'realtime_chat');
  assert.equal(action('button.sw3.short_press'), 'page_back');
  assert.equal(action('button.encoder.short_press'), 'page_enter');
  for (const event of ['joystick.up', 'joystick.down', 'knob.rotate_cw', 'knob.rotate_ccw']) assert.ok(action(event));
  assert.equal(build({}, {}, 'esp-s3', false).filter(binding => binding.action === 'voice_ptt').length, 0);
});
