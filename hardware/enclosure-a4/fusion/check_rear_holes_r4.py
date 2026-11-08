"""Scan the vertical rear wall against the uncut native exterior reference."""
import json,sys
from pathlib import Path
import numpy as np
import trimesh
import vtk
from check_side_holes import locator
from interface_seams import is_driver_cover_seam

def first(loc,x,z):
    t=vtk.reference(0.);sub=vtk.reference(0);cell=vtk.reference(0)
    point=[0.,0.,0.];coords=[0.,0.,0.]
    hit=loc.IntersectWithLine([float(x),100,float(z)],[float(x),-100,float(z)],1e-7,t,point,coords,sub,cell)
    return point[1] if hit else None

def check(folder,step=.5):
    old=[locator(trimesh.load_mesh(folder/f'exterior-reference-{label}.stl')) for label in ['upper','lower']]
    new=[locator(trimesh.load_mesh(folder/f'a4-{label}-r4-assembly.stl')) for label in ['upper','lower']]
    working=json.loads((folder.parent.parent/'fusion/working-r4.json').read_text(encoding='utf-8'))
    vents=working.get('rear_vent_bores_mm',[])
    bad=[];tested=0
    for x in np.arange(-9,82.01,step):
        for z in np.arange(-2,72.01,step):
            source=[v for loc in old if (v:=first(loc,x,z)) is not None]
            if not source or max(source)<4:continue # only the rear wall, not a view through the front window
            before=max(source)
            if is_driver_cover_seam(x,before,z,working):continue
            if any((x-vx)**2+(z-vz)**2<(r+.12)**2 for vx,vz,r in vents):continue
            current=[v for loc in new if (v:=first(loc,x,z)) is not None]
            after=max(current) if current else None;tested+=1
            if after is None or before-after>.15:bad.append(dict(x=float(x),z=float(z),before_y=before,after_y=after))
    result=dict(grid_step_mm=step,checked_rays=tested,unexpected_opening_samples=len(bad),samples=bad[:80])
    (folder/'rear-surface-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2));assert not bad

if __name__=='__main__':check(Path(sys.argv[1]))
