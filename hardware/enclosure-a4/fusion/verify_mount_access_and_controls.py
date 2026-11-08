"""Check real LCD screw/driver access and original control end profiles."""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_enclosure import solid
from verify_r4 import sc

OUT = ROOT/'output/r4-original-copy'


def samples(lines):
    points = []
    for a,b in lines:
        n = max(2, int(np.linalg.norm(b-a)/.15)+1)
        points.extend(np.linspace(a,b,n))
    points = np.array(points)
    # The exterior silhouette is allowed to widen. These points isolate the
    # original keyboard pocket and its two ends, away from that silhouette.
    return points[(points[:,0]>-4.5)&(points[:,0]<57.3)&(points[:,1]>-71.4)&(points[:,1]<-49.65)]


def nearest(points, lines):
    a = lines[:,0,:2];v = lines[:,1,:2]-a
    vv = np.einsum('ij,ij->i',v,v)
    maximum = 0.
    for chunk in np.array_split(points[:,:2], max(1,len(points)//200)):
        if len(chunk)==0: continue
        p = chunk[:,None,:]-a
        t = np.clip(np.einsum('cij,ij->ci',p,v)/np.maximum(vv,1e-20),0,1)
        d = np.linalg.norm(p-t[:,:,None]*v,axis=2).min(axis=1)
        maximum = max(maximum,float(d.max()))
    return maximum


def inner_section(mesh, z):
    """Separate closed loops, excluding only the exterior case silhouette."""
    lines=trimesh.intersections.mesh_plane(mesh,[0,0,1],[0,0,z])
    adjacency={};endpoints=[]
    for i,line in enumerate(lines):
        keys=[tuple(np.round(p[:2],5)) for p in line];endpoints.append(keys)
        for k in keys:adjacency.setdefault(k,[]).append(i)
    seen=set();groups=[]
    for i in range(len(lines)):
        if i in seen:continue
        todo=[i];seen.add(i);ids=[]
        while todo:
            j=todo.pop();ids.append(j)
            for k in endpoints[j]:
                for nxt in adjacency[k]:
                    if nxt not in seen:seen.add(nxt);todo.append(nxt)
        groups.append(ids)
    def area(ids):
        p=lines[ids].reshape(-1,3);return np.prod(np.ptp(p[:,:2],axis=0))
    exterior=max(groups,key=area)
    return lines[[i for ids in groups if ids is not exterior for i in ids]]


def main():
    upper_mesh = trimesh.load_mesh(OUT/'a4-upper-r4-assembly.stl')
    upper = solid(upper_mesh)
    lower = solid(trimesh.load_mesh(OUT/'a4-lower-r4-assembly.stl'))
    source = trimesh.load_mesh(OUT/'native-original-upper.stl')
    checks = {'lcd_screw_access': [], 'control_sections': [], 'physical_access_verified': False}
    for u in [3,78.2]:
        for v in [3,48]:
            row = dict(u=u,v=v,
                driver_upper_obstruction_mm3=(sc(u,v,2.25,-65,-6.45)^upper).volume(),
                installed_head_shell_overlap_mm3=(sc(u,v,1.95,-8,-6.4)^(upper+lower)).volume())
            checks['lcd_screw_access'].append(row)
    for z in [11.5,13.5,15.8]:
        original_lines = inner_section(source,z)
        current_lines = inner_section(upper_mesh,z)
        original_samples = samples(original_lines);current_samples = samples(current_lines)
        row = dict(z=z,original_samples=len(original_samples),current_samples=len(current_samples),
                   original_to_current_max_mm=nearest(original_samples,current_lines),
                   current_to_original_max_mm=nearest(current_samples,original_lines))
        checks['control_sections'].append(row)
    (OUT/'mount-access-and-controls.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print(json.dumps(checks,indent=2))
    assert all(r['driver_upper_obstruction_mm3']<.02 and r['installed_head_shell_overlap_mm3']<.02
               for r in checks['lcd_screw_access']), checks['lcd_screw_access']
    assert all(max(r['original_to_current_max_mm'],r['current_to_original_max_mm'])<.05
               for r in checks['control_sections']), checks['control_sections']


if __name__=='__main__':
    main()
