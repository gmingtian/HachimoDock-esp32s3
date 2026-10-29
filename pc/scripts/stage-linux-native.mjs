/** Stage an unpackaged native ELF with every resource Tauri resolves at runtime. */
import {chmodSync,copyFileSync,cpSync,existsSync,mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {dirname,join,resolve,isAbsolute} from 'node:path';
import {fileURLToPath} from 'node:url';

export function stageLinuxNative({tauriRoot,resources,outputRoot,binaryPath}) {
 const prefix=readFileSync(binaryPath).subarray(0,4);
 if(!prefix.equals(Buffer.from([127,69,76,70]))) throw new Error('Native Linux ELF executable is required');
 const libraryRoot=join(outputRoot,'usr/lib/pet-manager-tauri');
 const binaryRoot=join(outputRoot,'usr/bin');
 for(const [source,destination] of Object.entries(resources)){
  const from=resolve(tauriRoot,source);
  if(!existsSync(from))throw new Error(`Required desktop resource missing: ${from}`);
  const to=resolve(libraryRoot,destination);
  if(isAbsolute(destination)||!to.startsWith(resolve(libraryRoot)+'/'))throw new Error(`Invalid resource destination: ${destination}`);
 }
 mkdirSync(binaryRoot,{recursive:true});mkdirSync(libraryRoot,{recursive:true});
 copyFileSync(binaryPath,join(binaryRoot,'pet-manager-tauri'));chmodSync(join(binaryRoot,'pet-manager-tauri'),0o755);
 for(const [source,destination] of Object.entries(resources)){
  const target=join(libraryRoot,destination);mkdirSync(dirname(target),{recursive:true});
  cpSync(resolve(tauriRoot,source),target,{recursive:true,dereference:true});
 }
 writeFileSync(join(outputRoot,'launch.sh'),'#!/bin/sh\nset -eu\napp_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec "$app_root/usr/bin/pet-manager-tauri" "$@"\n');
 chmodSync(join(outputRoot,'launch.sh'),0o755);
 return outputRoot;
}

if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const pcRoot=resolve(dirname(fileURLToPath(import.meta.url)),'..');
 const tauriRoot=join(pcRoot,'src-tauri');
 const config=JSON.parse(readFileSync(join(tauriRoot,'tauri.conf.json')));
 const linux=JSON.parse(readFileSync(join(tauriRoot,'tauri.linux.conf.json')));
 const resources={...config.bundle.resources,...linux.bundle.resources};
 const targetRoot=process.env.CARGO_TARGET_DIR?resolve(process.env.CARGO_TARGET_DIR):join(tauriRoot,'target');
 const binaryPath=process.env.PET_MANAGER_LINUX_BINARY||join(targetRoot,'release/pet-manager-tauri');
 const output=stageLinuxNative({tauriRoot,resources,binaryPath,outputRoot:join(pcRoot,'dist-linux')});
 console.log(`Native Linux app staged: ${output}/launch.sh (requires system WebKitGTK, GTK3, ALSA, OpenSSL, FFmpeg and Python3)`);
}
