"""Pure local protocol helpers. Public geometry dimensions are millimeters."""
import json
import math
import os
import re
from pathlib import Path

OPERATIONS=frozenset({'ping','import_step','new_document','inspect','copy_body','cylinder','box','combine','transform','fillet','export_stl','export_step','snapshot','shutdown'})
_ID=re.compile(r'^[A-Za-z0-9_-]{1,96}$')

def validate_request(data):
    if not isinstance(data,dict):raise ValueError('Request must be an object')
    for key in ['id','session_id']:
        if not isinstance(data.get(key),str) or not _ID.fullmatch(data[key]):raise ValueError('Invalid '+key)
    if data.get('op') not in OPERATIONS:raise ValueError('Unsupported operation')
    if not isinstance(data.get('args'),dict):raise ValueError('args must be an object')
    return data

def mm_to_cm(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('Dimension must be a finite number')
    return float(value)/10.0

def point_cm(values):
    if not isinstance(values,(list,tuple)) or len(values)!=3:raise ValueError('Expected a 3D millimeter point')
    return [mm_to_cm(value) for value in values]

def matrix_cm(values):
    if not isinstance(values,(list,tuple)) or len(values)!=16:raise ValueError('Expected 16 matrix values')
    for value in values:mm_to_cm(value)
    result=list(map(float,values))
    if any(abs(result[12+i]-v)>1e-9 for i,v in enumerate([0,0,0,1])):raise ValueError('Matrix must be affine')
    a,b,c,d,e,f,g,h,i=(result[k] for k in [0,1,2,4,5,6,8,9,10])
    determinant=a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g)
    rows=[[a,b,c],[d,e,f],[g,h,i]]
    if abs(determinant-1)>1e-5 or any(abs(sum(v*v for v in row)-1)>1e-5 for row in rows):raise ValueError('Only proper rigid transforms are allowed')
    for k in [3,7,11]:result[k]/=10.0
    return result

def within_root(path,root):
    root=Path(root).resolve();path=Path(path).resolve()
    if not path.is_relative_to(root):raise ValueError('Path is outside the declared workspace root')
    return path

def atomic_json(path,data):
    path=Path(path)
    encoded=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    try:
        temp.write_text(encoded,encoding='utf-8')
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()
