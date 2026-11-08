import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import {validateClawpkgManifest} from '../src/lib/clawpkg-contract.js';
import {createClassicCore} from '../src/component-center/classic-core.js';
import {initialApp,appAdvance,appDashboard} from '../src/component-center/app-runtime.js';

const root=new URL('./gomoku-a4/',import.meta.url);
function packageFiles(){
  assert.ok(existsSync(new URL('component.json',root)),'installable Gomoku component must exist');
  return Object.fromEntries(['component.json','buttons.json','negative-screen.json','share.json','runtime/widget.json'].map(p=>[p,JSON.parse(readFileSync(new URL(p,root)))]).concat([['runtime/',{}],['assets/',{}]]));
}
async function game(){return createClassicCore(readFileSync(new URL('../src/component-center/classic-core.wasm',import.meta.url)),packageFiles()['runtime/widget.json']);}
const stones=s=>s.cells.filter(c=>c&3).length;
function at(g,x,y,t){
  const i=g.snapshot().cells.findIndex(c=>c&4);assert.ok(i>=0);
  for(let cx=i%15;cx!==x;cx+=cx<x?1:-1)g.action(cx<x?'gomoku.right':'gomoku.left',t);
  for(let cy=Math.floor(i/15);cy!==y;cy+=cy<y?1:-1)g.action(cy<y?'gomoku.down':'gomoku.up',t);
}

test('package passes client contract and keeps global exit unbound',()=>{
  const p=packageFiles(),v=validateClawpkgManifest(p);assert.deepEqual(v.errors,[]);
  const b=p['buttons.json'];assert.equal(b.find(b=>b.event==='button.sw1.short_press').action,'gomoku.place');
  assert.equal(b.find(b=>b.event==='button.sw2.short_press').action,'gomoku.undo');
  assert.equal(b.some(b=>b.event.startsWith('button.sw3.')),false);
  assert.equal(b.length,6);
});
test('physical direction bindings move the cursor, start and place remain separate',async()=>{
  const p=packageFiles(),g=await game();g.action('gomoku.place',10);
  assert.equal(stones(g.snapshot()),0);assert.equal(g.snapshot().cells.findIndex(c=>c&4),112);
  for(const [event,want] of [['knob.rotate_ccw',111],['joystick.up',96],['knob.rotate_cw',97],['joystick.down',112]]){
    g.action(p['buttons.json'].find(b=>b.event===event).action,11);assert.equal(g.snapshot().cells.findIndex(c=>c&4),want);
  }
  g.action('gomoku.place',12);assert.equal(g.snapshot().cells[112]&3,1);
  g.action('gomoku.place',13);assert.equal(stones(g.snapshot()),1,'no second black during AI turn');
  g.tick(310);assert.equal(stones(g.snapshot()),2);assert.ok(g.snapshot().aiReads<=8100);
  g.action('gomoku.place',311);assert.equal(stones(g.snapshot()),2,'occupied intersection rejected');
  g.action('gomoku.undo',312);assert.equal(stones(g.snapshot()),0);
  g.action('gomoku.undo',313);assert.equal(stones(g.snapshot()),0,'one-level undo');
});
test('cursor stops at board edges and undo cancels a pending AI reply',async()=>{
  const g=await game();g.action('gomoku.place',0);at(g,0,0,1);
  g.action('gomoku.left',2);g.action('gomoku.up',3);assert.equal(g.snapshot().cells.findIndex(c=>c&4),0);
  at(g,14,14,4);g.action('gomoku.right',5);g.action('gomoku.down',6);assert.equal(g.snapshot().cells.findIndex(c=>c&4),224);
  g.action('gomoku.place',7);g.action('gomoku.undo',8);g.tick(300);assert.equal(stones(g.snapshot()),0);
});
test('complete match highlights a win, freezes board, and restarts empty',async()=>{
  const g=await game();g.action('gomoku.place',0);let t=0;
  for(let n=0;n<120&&!g.snapshot().over;n++){
    const s=g.snapshot(),i=s.cells.findIndex(c=>!(c&3));at(g,i%15,Math.floor(i/15),++t);
    g.action('gomoku.place',t);t+=300;g.tick(t);
  }
  const s=g.snapshot();assert.equal(s.state,'result');assert.equal(s.over,true);
  assert.ok(s.score>=2000&&s.score<3000);assert.equal(s.cells.filter(c=>c&16).length,5);
  g.action('gomoku.left',++t);g.action('gomoku.undo',++t);assert.deepEqual(g.snapshot().cells,s.cells);
  g.action('gomoku.place',++t);assert.equal(g.snapshot().state,'playing');assert.equal(stones(g.snapshot()),0);
});
test('result UI distinguishes black win, white win, and full-board draw',()=>{
  const r=packageFiles()['runtime/widget.json'];
  for(const [score,want] of [[1009,'黑棋获胜'],[2024,'白棋获胜'],[3225,'棋盘已满']]){
    const s=initialApp(r);s.state='result';s.vars.score=score;
    assert.equal(appDashboard(r,appAdvance(r,s,300)).headline,want);
  }
});
test('background intersections match 15x15 game cell centers at native LCD scale',()=>{
  const r=packageFiles()['runtime/widget.json'],v=r.surface.game_view;
  assert.deepEqual([v.x,v.y,v.w,v.h],[14,14,420,420]);
  const png=readFileSync(new URL('assets/board.png',root));assert.equal(png.readUInt32BE(16),220);assert.equal(png.readUInt32BE(20),220);
  const board=r.surface.elements.find(n=>n.image==='board');assert.deepEqual([board.x,board.y,board.w,board.h],[4,4,440,440]);
  assert.ok(r.surface.elements.length<=32);assert.ok(Buffer.byteLength(JSON.stringify(r))<=8191);
});
