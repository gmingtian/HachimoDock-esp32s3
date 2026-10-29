import test from 'node:test';import assert from 'node:assert/strict';import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,existsSync,rmSync} from 'node:fs';import {tmpdir} from 'node:os';import {join} from 'node:path';
import {stageLinuxNative} from './stage-linux-native.mjs';
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
