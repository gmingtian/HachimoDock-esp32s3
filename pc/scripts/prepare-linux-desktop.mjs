/** Prepare a native Linux development app using host-managed FFmpeg/Python. */
import {chmodSync,copyFileSync,existsSync,mkdirSync,readFileSync} from 'node:fs';
import {resolve,dirname,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
if(process.platform!=='linux') throw new Error('Linux desktop preparation requires Linux');
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const stage=join(root,'src-tauri/generated-runtime');
mkdirSync(stage,{recursive:true});
const node=process.env.PET_MANAGER_NODE_BIN||process.execPath;
if(readFileSync(node).subarray(0,4).toString()!=='\x7fELF') throw new Error('Native Linux Node ELF executable required');
copyFileSync(node,join(stage,'node'));chmodSync(join(stage,'node'),0o755);
const bridge=join(root,'src-tauri/bridge/packages/clawd-backend-service');
const manifest=JSON.parse(readFileSync(join(bridge,'package.json')));
if(!Object.keys(manifest.dependencies||{}).every(name=>existsSync(join(bridge,'node_modules',name,'package.json')))){
 const npm=process.env.npm_execpath;
 const cmd=npm?process.execPath:'npm';
 const args=[...(npm?[npm]:[]),'ci','--omit=dev','--ignore-scripts','--no-audit','--no-fund'];
 const result=spawnSync(cmd,args,{cwd:bridge,stdio:'inherit'});
 if(result.error||result.status!==0) throw new Error(`Bridge dependencies unavailable: ${result.error||result.status}`);
}
console.log('Linux native resources ready. FFmpeg and Python3 are resolved from the host; this does not produce a portable redistribution bundle.');
