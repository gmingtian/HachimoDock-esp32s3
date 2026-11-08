import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {createClassicCore} from './classic-core.js';
const bytes=await fs.readFile(new URL('./classic-core.wasm',import.meta.url));
const runtime=JSON.parse(await fs.readFile(new URL('../../local-clawpkgs/xiangqi-a4/runtime/widget.json',import.meta.url)));
test('xiangqi uses the shared C board and derives lifecycle from core with wildcard actions',async()=>{
  const core=await createClassicCore(bytes,runtime),a=runtime.game.actions;
  let s=core.snapshot();assert.equal(s.width,9);assert.equal(s.height,10);assert.equal(s.kind,6);
  assert.equal(s.score,16);assert.equal(s.state,'ready');assert.equal(s.cells.filter(c=>c&15).length,32);
  core.action(a.down,1);assert.equal(core.snapshot().score,32);assert.equal(core.snapshot().state,'ready');
  core.action(a.up,2);assert.equal(core.snapshot().score,16);
  core.action(a.place,3);s=core.snapshot();assert.equal(s.running,true);assert.equal(s.state,'playing');assert.equal(s.score,17);
  const cursor=s.cells.findIndex(c=>c&16);assert.ok(cursor>=0);
  // The opening cursor is a red soldier at file five: select and follow a real guide.
  core.action(a.place,4);s=core.snapshot();assert.ok(s.cells.some(c=>c&32));assert.ok(s.cells.some(c=>c&128));
  core.action(a.undo,5);assert.equal(core.snapshot().cells.some(c=>c&32),false);
  core.action(a.place,6);core.action(a.up,7);core.action(a.place,8);s=core.snapshot();
  assert.equal(s.score%16,3);const before=s.cells.map(c=>c&15);core.action(a.place,9);assert.deepEqual(core.snapshot().cells.map(c=>c&15),before);
  for(let t=16;t<200000&&core.snapshot().score%16===3;t+=8)core.tick(t);
  s=core.snapshot();assert.notEqual(s.score%16,3,'incremental AI replies');assert.equal(s.state,'playing');
  core.action(a.undo,200001);s=core.snapshot();assert.equal(s.cells.filter(c=>c&15).length,32);assert.equal(s.score,17);
});
