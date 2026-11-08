// Deterministic hardware acceptance plan from the exact shared C rules engine.
import fs from 'node:fs';
import {createClassicCore} from '../pc/src/component-center/classic-core.js';
const runtime=JSON.parse(fs.readFileSync(new URL('../pc/local-clawpkgs/gomoku-a4/runtime/widget.json',import.meta.url)));
const g=await createClassicCore(fs.readFileSync(new URL('../pc/src/component-center/classic-core.wasm',import.meta.url)),runtime);
g.action('gomoku.place',10);let t=10;const rounds=[];
for(let n=0;n<120&&!g.snapshot().over;n++){
  const s=g.snapshot(),i=s.cells.findIndex(c=>!(c&3)),cursor=s.cells.findIndex(c=>c&4),a=[];
  for(let x=cursor%15;x!==i%15;x+=x<i%15?1:-1)a.push(x<i%15?'gomoku.right':'gomoku.left');
  for(let y=Math.floor(cursor/15);y!==Math.floor(i/15);y+=y<Math.floor(i/15)?1:-1)a.push(y<Math.floor(i/15)?'gomoku.down':'gomoku.up');
  a.push('gomoku.place');for(const action of a)g.action(action,++t);t+=300;g.tick(t);
  rounds.push({actions:a,score:g.snapshot().score,over:g.snapshot().over});
}
if(!g.snapshot().over)throw Error('Match plan did not end');
const path=new URL('../artifacts/gomoku-a4/match-plan.json',import.meta.url);
fs.writeFileSync(path,JSON.stringify({rounds,result:g.snapshot()},null,2));
console.log(`${rounds.length} rounds, ${rounds.reduce((n,r)=>n+r.actions.length,0)} acknowledged actions, final score ${g.snapshot().score}`);
