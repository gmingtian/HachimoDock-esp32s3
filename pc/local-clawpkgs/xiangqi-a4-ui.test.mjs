import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {createRequire} from 'node:module';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {transformSync} from 'esbuild';
import {initialApp,appVisible} from '../src/component-center/app-runtime.js';
import {validateClawpkgManifest} from '../src/lib/clawpkg-contract.js';
const require=createRequire(import.meta.url),module={exports:{}};
new Function('require','module','exports',transformSync(readFileSync(new URL('../src/component-center/ClassicGameLayer.jsx',import.meta.url),'utf8'),{loader:'jsx',format:'cjs'}).code)(require,module,module.exports);
const draw=cells=>renderToStaticMarkup(React.createElement(module.exports.ClassicGameLayer,{view:{x:8,y:8,w:396,h:440},frame:{kind:6,width:9,height:10,cells}}));
test('xiangqi displays all 14 piece identities and authoritative guide types',()=>{
  const html=draw([1,2,3,4,5,6,7,8,9,10,11,12,13,14,0x80,0x80|8,0x10|0x20|0x40|5]);
  for(const label of ['帅','仕','相','马','车','炮','兵','将','士','象','卒'])assert.ok(html.includes(label),label);
  assert.match(html,/data-xiangqi-guide="empty"/);
  assert.match(html,/data-xiangqi-guide="capture"/);
  for(const flag of ['selected','cursor','last'])assert.match(html,new RegExp(`data-xiangqi-${flag}="true"`));
  assert.equal((draw([0]).match(/<circle/g)||[]).length,0,'unmarked empty intersections preserve the board');
});
test('package exposes three difficulties, nine phases, six controls and a native aligned board',()=>{
  const root=new URL('./xiangqi-a4/',import.meta.url);
  assert.ok(existsSync(new URL('component.json',root)),'installable xiangqi package is present');
  const load=p=>JSON.parse(readFileSync(new URL(p,root)));
  const r=load('runtime/widget.json'),b=load('buttons.json');
  const files=Object.fromEntries(['component.json','buttons.json','negative-screen.json','share.json','runtime/widget.json'].map(p=>[p,load(p)]));
  files['runtime/']={};files['assets/']={};assert.deepEqual(validateClawpkgManifest(files).errors,[]);
  assert.equal(load('component.json').author,'gaomt');
  assert.equal(r.game.type,'xiangqi');assert.equal(r.game.difficulty_var,'level');assert.equal(r.game.status_var,'phase');
  assert.deepEqual(r.surface.game_view,{engine:'p4-game-surface-v1',x:8,y:8,w:396,h:440});
  assert.equal(b.length,6);assert.ok(b.every(v=>!v.event.startsWith('button.sw3.')));
  assert.equal(r.surface.elements.length<=32,true);assert.equal(r.texts,undefined);
  for(const n of r.surface.elements)assert.ok(n.x+n.w<=640&&n.y+n.h<=480,'every declared node fits the logical display');
  assert.equal(Buffer.byteLength(JSON.stringify(r))<=8191,true);
  assert.deepEqual(r.transitions.map(t=>t.from),Array(6).fill('*'));
  for(let level=0;level<3;level++)for(let phase=0;phase<9;phase++){
    const s=initialApp(r);s.vars.level=level;s.vars.phase=phase;
    const visible=r.surface.elements.filter(n=>appVisible(n,0,s.vars,0));
    assert.equal(visible.filter(n=>n.show?.var==='level').length,1);
    assert.equal(visible.filter(n=>n.show?.var==='phase').length,1);
  }
  const png=readFileSync(new URL('assets/board.png',root));assert.equal(png.readUInt32BE(16),198);assert.equal(png.readUInt32BE(20),220);
});
