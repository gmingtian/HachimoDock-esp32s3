import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
import {chromium} from 'playwright';

test('real Xiangqi preview advances 8ms search slices without repainting unchanged boards',{timeout:60000},async()=>{
  const load=async id=>JSON.parse(await readFile(new URL(`../local-clawpkgs/${id}/runtime/widget.json`,import.meta.url)));
  const runtimes={xiangqi:await load('xiangqi-a4'),gomoku:await load('gomoku-a4')};
  const fixture=`
import React,{Profiler} from 'react';
import {createRoot} from 'react-dom/client';
import {flushSync} from 'react-dom';
import {ComponentAppPreview} from './src/component-center/AppSurface.jsx';
const runtimes=${JSON.stringify(runtimes)};let root=createRoot(document.getElementById('root')),commits=0;
window.__entry={mount(type,ticking=false){const r=structuredClone(runtimes[type]);if(ticking){r.vars.beat={type:'int',init:0};r.tick=[{every_ms:80,inc:{beat:1}}];r.surface.elements.push({type:'text',x:500,y:50,w:70,h:22,color:0,font_size:16,var_bind:'beat'});}r.surface.elements.push(...Object.entries(r.game.actions).map(([key,action],i)=>({type:'button',x:420,y:300+i*25,w:200,h:24,color:65535,font_size:16,text:'test-'+key,action})));flushSync(()=>root.render(React.createElement(Profiler,{id:'preview',onRender:()=>commits++},React.createElement(ComponentAppPreview,{component:{id:'test-'+type,appRuntime:r},active:true,interactive:true}))));},commits:()=>commits,step(){flushSync(()=>window.__clock.advance());},unmount(){flushSync(()=>root.unmount());}};
window.__entry.mount('xiangqi');`;
  let browser;
  try{
    const directory=fileURLToPath(new URL('..',import.meta.url));
    const bundle=await build({stdin:{contents:fixture,resolveDir:directory,loader:'jsx'},bundle:true,write:false,platform:'browser',format:'iife',define:{'process.env.NODE_ENV':'"development"'},plugins:[{name:'inline-wasm',setup(b){b.onResolve({filter:/\.wasm\?url$/},args=>({path:resolve(args.resolveDir,args.path.slice(0,-4)),namespace:'wasm'}));b.onLoad({filter:/.*/,namespace:'wasm'},async args=>({contents:'export default '+JSON.stringify('data:application/wasm;base64,'+(await readFile(args.path)).toString('base64'))}));}}]});
    browser=await chromium.launch({headless:true,executablePath:process.env.PET_TEST_BROWSER||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
    const page=await browser.newPage(),errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('browser error:',e.message);});
    page.setDefaultTimeout(10000);
    await page.addInitScript(()=>{
      const intervals=new Map();let id=0;const instantiate=WebAssembly.instantiate.bind(WebAssembly);
      window.setInterval=(callback,ms)=>{intervals.set(++id,{callback,ms});return id;};window.clearInterval=id=>intervals.delete(id);
      WebAssembly.instantiate=async(...args)=>{const result=await instantiate(...args);window.__wasm=result.instance||result;return result;};
      window.__clock={periods:()=>[...intervals.values()].map(v=>v.ms),advance:()=>{for(const timer of [...intervals.values()])timer.callback();}};
      window.__score=()=>{const e=window.__wasm?.exports;return e?new Int32Array(e.memory.buffer,e.classic_snapshot(),6)[2]:-1;};
    });
    await page.goto('about:blank');await page.setContent('<div id="root"></div><script>'+bundle.outputFiles[0].text+'</script>');await page.waitForFunction(()=>window.__score()===16);
    const press=key=>page.getByRole('button',{name:'test-'+key,exact:true}).evaluate(el=>el.dispatchEvent(new MouseEvent('click',{bubbles:true,detail:0})));
    const measurements=[];
    for(const level of [0,1,2]){
      if(level){await page.evaluate(()=>window.__entry.mount('xiangqi'));await page.waitForFunction(()=>window.__score()===16);}
      if(level===0)await press('up');if(level===2)await press('down');
      await press('place');await press('place');await press('up');await press('place');
      await page.waitForFunction(()=>window.__score()%16===3);
      const before=await page.evaluate(()=>window.__entry.commits());
      const result=await page.evaluate(()=>{let steps=0;const period=window.__clock.periods()[0];while(window.__score()%16===3&&steps<3000){window.__entry.step();steps++;}return {period,steps,elapsed:steps*period,score:window.__score(),commits:window.__entry.commits()};});
      result.level=level;result.commits-=before;measurements.push(result);
    }
    console.log('real WASM preview openings:',JSON.stringify(measurements));
    assert.ok(measurements.every(v=>v.elapsed<=4000),'all three opening replies settle within four simulated seconds');
    assert.ok(measurements.every(v=>v.period===8),'Xiangqi gets its native eight-millisecond search cadence');
    assert.ok(measurements.every(v=>v.commits<=4),'hidden search slices do not trigger full SVG renders');
    const idle=await page.evaluate(()=>{const before=window.__entry.commits();for(let i=0;i<100;i++)window.__entry.step();return window.__entry.commits()-before;});
    assert.equal(idle,0,'an unchanged idle board does not re-render every search tick');
    await page.evaluate(()=>window.__entry.mount('xiangqi',true));await page.waitForFunction(()=>window.__score()===16);
    await page.evaluate(()=>{for(let i=0;i<20;i++)window.__entry.step();});
    assert.equal(await page.locator('g[data-label="2"] > text').count(),1,'runtime timers retain all elapsed eight-millisecond periods between renders');
    await page.evaluate(()=>window.__entry.mount('gomoku'));await page.waitForFunction(()=>window.__score()===0);
    assert.deepEqual(await page.evaluate(()=>window.__clock.periods()),[50],'existing native presets retain their original cadence');
    await page.evaluate(()=>window.__entry.unmount());assert.deepEqual(await page.evaluate(()=>window.__clock.periods()),[]);
    assert.deepEqual(errors,[]);
    const live=await browser.newPage();live.setDefaultTimeout(10000);
    await live.addInitScript(()=>{const instantiate=WebAssembly.instantiate.bind(WebAssembly);WebAssembly.instantiate=async(...args)=>{const result=await instantiate(...args);window.__wasm=result.instance||result;return result;};window.__score=()=>{const e=window.__wasm?.exports;return e?new Int32Array(e.memory.buffer,e.classic_snapshot(),6)[2]:-1;};});
    await live.goto('about:blank');await live.setContent('<div id="root"></div><script>'+bundle.outputFiles[0].text+'</script>');await live.waitForFunction(()=>window.__score()===16);
    const realTimes=[];
    const livePress=key=>live.getByRole('button',{name:'test-'+key,exact:true}).evaluate(el=>el.dispatchEvent(new MouseEvent('click',{bubbles:true,detail:0})));
    for(const level of [0,1,2]){
      if(level){await live.evaluate(()=>window.__entry.mount('xiangqi'));await live.waitForFunction(()=>window.__score()===16);}
      if(level===0)await livePress('up');if(level===2)await livePress('down');
      await livePress('place');await livePress('place');await livePress('up');
      const began=performance.now();await livePress('place');await live.waitForFunction(()=>window.__score()%16!==3);
      const elapsed=Math.round(performance.now()-began);realTimes.push({level,milliseconds:elapsed});
      assert.ok(elapsed<6000,'live browser opening responds within six seconds');
    }
    console.log('live browser opening response:',JSON.stringify(realTimes));await live.evaluate(()=>window.__entry.unmount());
  }finally{await browser?.close();}
});
