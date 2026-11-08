// Read-only device acceptance expectations from the current shared C/WASM core.
// This generator never opens a serial port or implements Xiangqi movement rules.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import {createClassicCore} from '../pc/src/component-center/classic-core.js';

const wasmUrl=new URL('../pc/src/component-center/classic-core.wasm',import.meta.url);
const runtimeUrl=new URL('../pc/local-clawpkgs/xiangqi-a4/runtime/widget.json',import.meta.url);
const outUrl=new URL('../artifacts/s3-xiangqi-r16/device-plan.json',import.meta.url);
const bytes=fs.readFileSync(wasmUrl),runtimeBytes=fs.readFileSync(runtimeUrl);
const runtime=JSON.parse(runtimeBytes),actions=runtime.game.actions;
const directions=['up','right','down','left'];
const hash=data=>crypto.createHash('sha256').update(data).digest('hex');
const xy=index=>({index,x:index%9,y:Math.floor(index/9)});
const findFlag=(cells,flag)=>{const at=cells.findIndex(c=>c&flag);return at<0?null:at;};
const pure=s=>s.cells.map(c=>c&15);
const activePhase=s=>s.score%16;

function expected(snapshot){
  assert.equal(snapshot.kind,6);assert.equal(snapshot.width,9);assert.equal(snapshot.height,10);assert.equal(snapshot.cells.length,90);
  assert.ok(snapshot.cells.every(c=>Number.isInteger(c)&&c>=0&&c<=255&&(c&15)<=14));
  const legalTargets=[],captureTargets=[];
  snapshot.cells.forEach((c,i)=>{if(c&128){legalTargets.push(i);if(c&15)captureTargets.push(i);}});
  return {
    gameType:'xiangqi',gameGridWidth:9,gameGridHeight:10,
    gameScore:snapshot.score,gameDifficulty:Math.floor(snapshot.score/16),gamePhase:activePhase(snapshot),
    gameRunning:snapshot.running,gameOver:snapshot.over,state:snapshot.state,
    gameCells:snapshot.cells,cursor:findFlag(snapshot.cells,16),selected:findFlag(snapshot.cells,32),
    legalTargets,captureTargets,pieceCount:snapshot.cells.filter(c=>c&15).length,
  };
}

async function make(){return {core:await createClassicCore(bytes,runtime),now:0};}
function act(session,action){session.core.action(action,++session.now);return session.core.snapshot();}
function record(session,steps,action,purpose){
  const snapshot=act(session,action);steps.push({action,purpose,expected:expected(snapshot)});return snapshot;
}
function navigate(session,target,steps){
  let cursor=findFlag(session.core.snapshot().cells,16);assert.notEqual(cursor,null);
  assert.equal(findFlag(session.core.snapshot().cells,32),null,'grid navigation must be unselected');
  while(cursor%9!==target%9){record(session,steps,cursor%9<target%9?actions.right:actions.left,'move unselected cursor');cursor=findFlag(session.core.snapshot().cells,16);}
  while(Math.floor(cursor/9)!==Math.floor(target/9)){record(session,steps,Math.floor(cursor/9)<Math.floor(target/9)?actions.down:actions.up,'move unselected cursor');cursor=findFlag(session.core.snapshot().cells,16);}
}

// Probe the actual joystick handler. Nodes are cursor indices, edges are real
// WASM actions; no distance calculation or piece-movement logic is duplicated.
async function measuredDirectionGraph(origin){
  const graph=new Map(),routes=new Map([[origin,[]]]),queue=[origin];
  while(queue.length){
    const cursor=queue.shift(),edges={};
    for(const direction of directions){
      const s=await make();act(s,actions.place);navigate(s,origin,[]);act(s,actions.place);
      for(const action of routes.get(cursor))act(s,action);
      assert.equal(findFlag(s.core.snapshot().cells,16),cursor);
      const next=expected(act(s,actions[direction]));assert.equal(next.selected,origin);
      edges[direction]=next.cursor;
      if(next.cursor!==origin)assert.ok(next.legalTargets.includes(next.cursor),'direction must land on a legal hint');
      if(!routes.has(next.cursor)){routes.set(next.cursor,[...routes.get(cursor),actions[direction]]);queue.push(next.cursor);}
    }
    graph.set(cursor,edges);
  }
  return graph;
}

function routeBetween(graph,from,to){
  const routes=new Map([[from,[]]]),queue=[from];
  while(queue.length){
    const at=queue.shift();if(at===to)return routes.get(at);
    for(const direction of directions){
      const next=graph.get(at)[direction];
      if(!routes.has(next)){routes.set(next,[...routes.get(at),actions[direction]]);queue.push(next);}
    }
  }
  throw Error(`WASM joystick cannot reach legal target ${to} from ${from}`);
}

const main=await make(),launch=expected(main.core.snapshot()),startSteps=[];
record(main,startSteps,actions.place,'start normal difficulty game');
const initialPieces=pure(main.core.snapshot()),cases=[];
const pieces=[
  {id:'general',name:'帅',piece:1,origin:85},
  {id:'advisor',name:'仕',piece:2,origin:84},
  {id:'elephant',name:'相',piece:3,origin:83},
  {id:'horse',name:'马',piece:4,origin:82},
  {id:'chariot',name:'车',piece:5,origin:81},
  {id:'cannon',name:'炮',piece:6,origin:64},
  {id:'soldier',name:'兵',piece:7,origin:54},
];
for(const piece of pieces){
  const steps=[];navigate(main,piece.origin,steps);
  assert.equal(main.core.snapshot().cells[piece.origin]&15,piece.piece);
  const selected=expected(record(main,steps,actions.place,'select piece and inspect every legal hint'));
  assert.equal(selected.selected,piece.origin);assert.ok(selected.legalTargets.length>0);
  const graph=await measuredDirectionGraph(piece.origin),visited=new Set();
  for(const target of selected.legalTargets){
    const cursor=findFlag(main.core.snapshot().cells,16);
    for(const action of routeBetween(graph,cursor,target)){
      const next=expected(record(main,steps,action,'jump directly between legal destinations'));
      assert.equal(next.selected,piece.origin);assert.deepEqual(next.legalTargets,selected.legalTargets);
      assert.ok(selected.legalTargets.includes(next.cursor));visited.add(next.cursor);
      assert.deepEqual(pure(main.core.snapshot()),initialPieces);
    }
    visited.add(target);
  }
  assert.deepEqual([...visited].sort((a,b)=>a-b),selected.legalTargets);
  // Observe a no-target direction too; the real handler may keep its cursor.
  const cursor=findFlag(main.core.snapshot().cells,16);
  const noMove=directions.find(d=>graph.get(cursor)[d]===cursor);
  if(noMove)record(main,steps,actions[noMove],'no suitable legal target in this direction: remain in place');
  const cancelled=expected(record(main,steps,actions.undo,'cancel selection without making a move'));
  assert.equal(cancelled.selected,null);assert.deepEqual(cancelled.legalTargets,[]);
  assert.equal(cancelled.gamePhase,1);assert.equal(cancelled.pieceCount,32);
  assert.deepEqual(pure(main.core.snapshot()),initialPieces);
  cases.push({...piece,origin:xy(piece.origin),selectedExpected:selected,
    directionGraph:Object.fromEntries(graph),visitedLegalTargets:[...visited].sort((a,b)=>a-b),
    actions:steps.map(s=>s.action),steps,afterCancelExpected:cancelled});
}

const aiCases=[];
for(let level=0;level<3;level++){
  const s=await make(),steps=[],freshLaunchExpected=expected(s.core.snapshot());
  if(level===0)record(s,steps,actions.up,'choose simple difficulty while ready');
  if(level===2)record(s,steps,actions.down,'choose hard difficulty while ready');
  record(s,steps,actions.place,'start a fresh game');navigate(s,54,steps);
  record(s,steps,actions.place,'select red soldier at 0,6');
  record(s,steps,actions.up,'follow the legal guide to 0,5');
  const thinking=expected(record(s,steps,actions.place,'commit human move and start bounded AI'));
  assert.equal(thinking.gamePhase,3);assert.equal(thinking.gameDifficulty,level);
  let ticks=0,lastThinking=thinking;
  while(activePhase(s.core.snapshot())===3&&ticks<10000){
    s.now+=8;s.core.tick(s.now);ticks++;
    const state=expected(s.core.snapshot());
    if(state.gamePhase===3){assert.deepEqual(state.gameCells,lastThinking.gameCells);lastThinking=state;}
  }
  const replied=expected(s.core.snapshot());assert.notEqual(replied.gamePhase,3,'AI must reply within bounded logical time');
  assert.equal(replied.gameDifficulty,level);assert.equal(replied.gameRunning,true);
  const afterUndo=expected(record(s,[],actions.undo,'take back human and AI moves together'));
  assert.deepEqual(pure(s.core.snapshot()),initialPieces);
  aiCases.push({difficulty:level,name:['简单','普通','困难'][level],requiresFreshLaunch:true,
    freshLaunchExpected,actions:steps.map(step=>step.action),steps,thinkingExpected:thinking,
    responseExpected:replied,wasmTicksAt8ms:ticks,wasmLogicalResponseMs:ticks*8,
    responseObservation:{queryTopic:'miniapp/query',pollIntervalMs:25,timeoutMs:30000,
      thinkingMayFinishBeforeFirstQuery:true,compareFinalGameCells:true,
      measure:'device elapsed wall time from the acknowledged final place action to first phase != 3'},
    undoAction:actions.undo,afterUndoExpected:afterUndo});
}

const plan={schema:'s3-xiangqi-device-plan-v1',
  source:{rules:'current firmware C core compiled into classic-core.wasm; no duplicate JS rules',
    wasm:'pc/src/component-center/classic-core.wasm',wasmSha256:hash(bytes),
    runtime:'pc/local-clawpkgs/xiangqi-a4/runtime/widget.json',runtimeSha256:hash(runtimeBytes)},
  observation:{topic:'miniapp/state',requestTopic:'miniapp/query',optionalFields:['gameCells','gameDifficulty','gamePhase'],
    cells:90,flags:{pieceMask:15,cursor:16,selected:32,lastMoveEndpoints:64,legalDestination:128},
    captureHint:'legalDestination bit set and (cell & pieceMask) nonzero',
    compare:'exact gameCells/gameScore/gameDifficulty/gamePhase; ignore revision counters and requestId'},
  execution:{connectsToDevice:false,requiresFirmwareWithOptionalXiangqiObservation:true,
    prepare:'launch xiangqi-a4 freshly once for the hint session, then run startSteps and cases in order',
    afterEachAction:'wait for the action acknowledgement, query miniapp/state, compare that step expected projection',
    hintSessionMakesMoves:false,aiCasesRequireFreshLaunch:true},
  launchExpected:launch,startSteps,cases,hintSessionFinalExpected:expected(main.core.snapshot()),aiCases,
  exitDuringHardSearch:{requiresFreshLaunch:true,prepareActions:aiCases[2].actions,
    operation:'Use the physical SW3 exit/home control immediately after the last human place acknowledgement; do not send another Xiangqi move',
    expected:'Home is responsive while thinking. Xiangqi observation becomes inactive or yields to the home view; pending search cannot later change home or submit a stale move.',
    followUp:'Launch Xiangqi again and verify fresh ready/32-piece board before another game. Measure exit latency on the device.'},
};
if(process.argv.includes('--check'))assert.deepEqual(JSON.parse(fs.readFileSync(outUrl)),plan,'device plan must match current WASM/runtime');
else{fs.mkdirSync(new URL('../artifacts/s3-xiangqi-r16/',import.meta.url),{recursive:true});fs.writeFileSync(outUrl,JSON.stringify(plan,null,2)+'\n');}
console.log(`Xiangqi device plan: ${cases.length} piece cases, ${cases.reduce((n,c)=>n+c.visitedLegalTargets.length,0)} legal targets, ${cases.reduce((n,c)=>n+c.actions.length,0)+startSteps.length} hint-session actions`);
console.log(`AI response logical ms: ${aiCases.map(c=>`${c.name}=${c.wasmLogicalResponseMs}`).join(', ')}; WASM ${hash(bytes).slice(0,16)}`);
