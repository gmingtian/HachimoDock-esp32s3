"""Compare the widened right control rim with the native source surface."""
import json
import sys
from pathlib import Path
import numpy as np
import trimesh

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from explore_geometry import heights

OUT=ROOT/'output/r4-original-copy'
source=trimesh.load_mesh(OUT/'native-original-upper.stl')
current=trimesh.load_mesh(OUT/'a4-upper-r4-assembly.stl')
rows=[]
for y in [-52,-57,-60,-63]:
    for x in [74.5,74.85,74.94,74.96,75.05,75.25,75.5,75.8,76,76.2,77]:
        a=heights(source,x,-y);b=heights(current,x,-y)
        a=[v for v in a if v<20];b=[v for v in b if v<20]
        rows.append(dict(x=x,y=y,source_top=max(a) if a else None,current_top=max(b) if b else None))
(OUT/'control-rim-before-profile.json').write_text(json.dumps(rows,indent=2))
for y in [-52,-57,-60,-63]:
    print('y',y,[(r['x'],r['source_top'],r['current_top']) for r in rows if r['y']==y])
