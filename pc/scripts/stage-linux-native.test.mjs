import test from 'node:test';import assert from 'node:assert/strict';import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,existsSync,rmSync} from 'node:fs';import {tmpdir} from 'node:os';import {join} from 'node:path';
import {stageLinuxNative} from './stage-linux-native.mjs';
import {fileURLToPath} from 'node:url';
test('nonempty output is rejected before old files can enter a release',()=>{
 const root=mkdtempSync(join(tmpdir(),'hachimo-stale-stage-'));
 try{
 const output=join(root,'out');mkdirSync(output);writeFileSync(join(output,'private-stale.txt'),'do not ship');
 writeFileSync(join(root,'resource.txt'),'fresh');writeFileSync(join(root,'app'),Buffer.from([127,69,76,70]));
 assert.throws(()=>stageLinuxNative({tauriRoot:root,resources:{'resource.txt':'tools/resource.txt'},outputRoot:output,binaryPath:join(root,'app')}),/nonempty.*backup.*rerun/i);
 assert.equal(readFileSync(join(output,'private-stale.txt'),'utf8'),'do not ship');
 assert.equal(existsSync(join(output,'usr')),false);
 }finally{rmSync(root,{recursive:true,force:true});}
});
test('an existing empty output directory can be staged safely',()=>{
 const root=mkdtempSync(join(tmpdir(),'hachimo-empty-stage-'));
 try{
 const output=join(root,'out');mkdirSync(output);writeFileSync(join(root,'resource.txt'),'fresh');writeFileSync(join(root,'app'),Buffer.from([127,69,76,70]));
 stageLinuxNative({tauriRoot:root,resources:{'resource.txt':'tools/resource.txt'},outputRoot:output,binaryPath:join(root,'app')});
 assert.equal(readFileSync(join(output,'usr/lib/pet-manager-tauri/tools/resource.txt'),'utf8'),'fresh');
 }finally{rmSync(root,{recursive:true,force:true});}
});
test('native Linux layout keeps resources beside the installed library path',()=>{
 const root=mkdtempSync(join(tmpdir(),'hachimo-stage-'));
 try{mkdirSync(join(root,'sources'));writeFileSync(join(root,'sources/data.txt'),'ready');writeFileSync(join(root,'app'),Buffer.from([127,69,76,70]));
 const output=join(root,'out');stageLinuxNative({tauriRoot:root,resources:{'sources/data.txt':'tools/data.txt'},outputRoot:output,binaryPath:join(root,'app')});
 assert.equal(readFileSync(join(output,'usr/lib/pet-manager-tauri/tools/data.txt'),'utf8'),'ready');assert.ok(existsSync(join(output,'usr/bin/pet-manager-tauri')));assert.match(readFileSync(join(output,'launch.sh'),'utf8'),/usr\/bin\/pet-manager-tauri/);
 assert.throws(()=>stageLinuxNative({tauriRoot:root,resources:{'missing':'tools/missing'},outputRoot:join(root,'bad'),binaryPath:join(root,'app')}),/missing/);
 }finally{rmSync(root,{recursive:true,force:true});}
});
test('configured Tauri product name determines the portable resource directory',()=>{
 const root=mkdtempSync(join(tmpdir(),'hachimo-product-stage-'));
 try{mkdirSync(join(root,'sources'));writeFileSync(join(root,'sources/data.txt'),'ready');writeFileSync(join(root,'app'),Buffer.from([127,69,76,70]));
 const config=JSON.parse(readFileSync(new URL('../src-tauri/tauri.conf.json',import.meta.url)));
 const output=join(root,'out');stageLinuxNative({tauriRoot:root,resources:{'sources/data.txt':'tools/data.txt'},outputRoot:output,binaryPath:join(root,'app'),packageName:config.productName});
 assert.equal(readFileSync(join(output,'usr/lib',config.productName,'tools/data.txt'),'utf8'),'ready');
 }finally{rmSync(root,{recursive:true,force:true});}
});
test('desktop resource maps stage the S3 firmware and the independent native UI',()=>{
 const root=mkdtempSync(join(tmpdir(),'hachimo-s3-stage-'));
 try{
 const tauriRoot=fileURLToPath(new URL('../src-tauri/',import.meta.url));
 const base=JSON.parse(readFileSync(join(tauriRoot,'tauri.conf.json')));
 const overlay=JSON.parse(readFileSync(join(tauriRoot,'tauri.linux.conf.json')));
 const all={...base.bundle.resources,...overlay.bundle.resources};
 const destinations=['firmware/esp32-s3/firmware.bin','s3-landscape-ui','tools/prepare_s3_assets.py'];
 const resources=Object.fromEntries(Object.entries(all).filter(([,destination])=>destinations.includes(destination)));
 assert.equal(Object.keys(resources).length,3);
 writeFileSync(join(root,'app'),Buffer.from([127,69,76,70]));
 stageLinuxNative({tauriRoot,resources,binaryPath:join(root,'app'),packageName:base.productName,outputRoot:join(root,'out')});
 const installed=join(root,'out/usr/lib',base.productName);
 const inventory=JSON.parse(readFileSync(join(installed,'s3-landscape-ui/inventory.json')));
 assert.equal(inventory.components.length,28);
 for(const logical of Object.keys(inventory.files))assert.ok(existsSync(join(installed,'s3-landscape-ui',logical)),logical);
 assert.deepEqual(readFileSync(join(installed,'firmware/esp32-s3/firmware.bin')),readFileSync(join(tauriRoot,'firmware/esp32-s3/firmware.bin')));
 assert.ok(existsSync(join(installed,'tools/prepare_s3_assets.py')));
 }finally{rmSync(root,{recursive:true,force:true});}
});
