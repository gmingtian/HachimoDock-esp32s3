import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateClawpkgManifest} from './clawpkg-contract.js';
function fixture(){
  const read=p=>JSON.parse(readFileSync(new URL(`../../local-clawpkgs/gomoku-a4/${p}`,import.meta.url)));
  const runtime=read('runtime/widget.json');
  runtime.game.type='xiangqi';runtime.game.difficulty_var='level';runtime.game.status_var='phase';
  runtime.vars.level={type:'int',init:1};runtime.vars.phase={type:'int',init:0};
  return {'component.json':read('component.json'),'negative-screen.json':read('negative-screen.json'),'buttons.json':read('buttons.json'),'runtime/':{},'assets/':{},'share.json':read('share.json'),'runtime/widget.json':runtime};
}
test('xiangqi admits six cursor actions and explicit integer difficulty/status projections',()=>{
  const result=validateClawpkgManifest(fixture());assert.deepEqual(result.errors,[]);
});
test('xiangqi projections are required int vars and are unavailable on old presets',()=>{
  for(const field of ['difficulty_var','status_var']){
    const f=fixture();delete f['runtime/widget.json'].game[field];assert.equal(validateClawpkgManifest(f).valid,false);
    const bad=fixture();bad['runtime/widget.json'].game[field]='missing';assert.equal(validateClawpkgManifest(bad).valid,false);
    const old=fixture();old['runtime/widget.json'].game.type='gomoku';assert.equal(validateClawpkgManifest(old).valid,false);
  }
});
