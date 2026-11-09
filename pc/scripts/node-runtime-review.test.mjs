import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdtempSync,mkdirSync,readFileSync,writeFileSync,existsSync,rmSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {copyNodeRuntimeLicense,validateReviewedNodeRuntime,nodeRuntimeReview} from './dependency-license-resources.mjs';

const root=fileURLToPath(new URL('../../',import.meta.url));
const digest=data=>createHash('sha256').update(data).digest('hex');
function actualNodes(){
 if(process.env.REVIEWED_NODE_ARCHIVE_ROOT)return Object.values(nodeRuntimeReview.targets).map(record=>({record,path:join(process.env.REVIEWED_NODE_ARCHIVE_ROOT,record.binary)}));
 const path=process.env.REVIEWED_NODE_BIN||process.execPath;
 const sha=digest(readFileSync(path));
 const record=Object.values(nodeRuntimeReview.targets).find(item=>item.binarySha256===sha);
 return record?[{record,path}]:[];
}
const nodes=actualNodes();
test('real official binaries accept only their reviewed platform and architecture',t=>{
 if(!nodes.length)return t.skip('real official Node binary required');
 for(const {record,path} of nodes){
  assert.deepEqual(validateReviewedNodeRuntime(path,record),record);
  for(const other of Object.values(nodeRuntimeReview.targets).filter(item=>item!==record)){
   assert.throws(()=>validateReviewedNodeRuntime(path,other),/no reviewed matching license/);
  }
 }
});
test('real official runtime stages exact complete carrier and refuses conflicting bytes',t=>{
 if(!nodes.length)return t.skip('real official Node binary required');
 const temporary=mkdtempSync(join(tmpdir(),'node-carrier-review-'));
 try{
  const {record,path}=nodes[0];const output=join(temporary,'out');
  copyNodeRuntimeLicense(path,join(root,'licenses'),output,record);
  const expected=readFileSync(join(root,'licenses',nodeRuntimeReview.license.file));
  assert.deepEqual(readFileSync(join(output,'node.LICENSE')),expected);
  copyNodeRuntimeLicense(path,join(root,'licenses'),output,record);
  writeFileSync(join(output,'node.LICENSE'),'conflicting old carrier');
  assert.throws(()=>copyNodeRuntimeLicense(path,join(root,'licenses'),output,record),/integrity mismatch/);
  assert.equal(readFileSync(join(output,'node.LICENSE'),'utf8'),'conflicting old carrier');
 }finally{rmSync(temporary,{recursive:true,force:true});}
});
test('unknown binary or incomplete carrier cannot create runtime license output',()=>{
 const temporary=mkdtempSync(join(tmpdir(),'node-carrier-reject-'));
 try{
  const output=join(temporary,'out');const unknown=join(temporary,'node');writeFileSync(unknown,'not an official binary');
  assert.throws(()=>copyNodeRuntimeLicense(unknown,join(root,'licenses'),output),/no reviewed/);
  assert.equal(existsSync(output),false);
  if(nodes.length){
   const source=join(temporary,'licenses');mkdirSync(source);writeFileSync(join(source,nodeRuntimeReview.license.file),'short MIT-only substitute');
   assert.throws(()=>copyNodeRuntimeLicense(nodes[0].path,source,output,nodes[0].record),/integrity mismatch/);
   assert.equal(existsSync(output),false);
  }
 }finally{rmSync(temporary,{recursive:true,force:true});}
});
