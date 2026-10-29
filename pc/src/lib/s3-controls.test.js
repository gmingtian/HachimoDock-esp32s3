import test from 'node:test';
import assert from 'node:assert/strict';
import { s3ButtonRows } from './s3-controls.js';
test('S3 exposes only the wired keys with escape/menu/PTT defaults', () => {
 const rows = s3ButtonRows();
 assert.equal(rows.length, 6);
 assert.deepEqual([...new Set(rows.map(r=>r.controlId))], ['s3_sw1','s3_sw2','s3_sw3']);
 assert.deepEqual(rows.map(r=>r.defaultAction), ['session_previous','page_back','session_next','component_center','page_enter','voice_ptt']);
 assert.equal(rows[5].holdEvent,'button.sw3.hold');
 assert.ok(rows.every(r=>!r.event.includes('encoder') && !r.event.includes('joystick')));
});

import {readFileSync} from 'node:fs';
test('S3 wire config reserves long previous for back and emits voice only on confirm hold', () => {
 const dashboard=readFileSync(new URL('../DeviceDashboard.jsx',import.meta.url),'utf8');
 const source=dashboard.slice(dashboard.indexOf('export function buildBoardButtonConfigBindings'),dashboard.indexOf('function createButtonConfigRequestId'));
 const build=new Function('buttonControlRowsForRuntime','clampButtonActionValue',source.replace('export function','function')+'; return buildBoardButtonConfigBindings;')(()=>s3ButtonRows(),v=>v);
 const bindings=build({}, {}, 'esp-s3', true);
 assert.equal(bindings.length,9);
 assert.deepEqual(bindings.find(b=>b.event==='button.sw1.long_press'),{event:'button.sw1.long_press',action:'page_back'});
 assert.deepEqual(bindings.find(b=>b.event==='button.sw2.long_press'),{event:'button.sw2.long_press',action:'component_center'});
 assert.deepEqual(bindings.find(b=>b.event==='button.sw3.hold'),{event:'button.sw3.hold',action:'voice_ptt'});
 assert.equal(bindings.filter(b=>b.action==='voice_ptt').length,1);
 assert.equal(build({}, {}, 'esp-s3', false).filter(b=>b.action==='voice_ptt').length,0);
});
