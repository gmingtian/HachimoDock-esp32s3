import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import trimesh
import numpy as np
from explore_geometry import render,load,ROOT
out=ROOT/'output/r2-fusion'
upper=trimesh.load_mesh(out/'a4-upper-r2-assembly.stl')
lower=trimesh.load_mesh(out/'a4-lower-r2-assembly.stl')
parts=[(lower,(.65,.67,.68)),(upper,(.93,.93,.90))]
caps=[(load(i),(.97,.35,.075)) for i in [2,3,4,5,6]]
render(parts+caps,out/'r2-exterior.png',camera=(145,-190,125))
render([(upper,(.65,.68,.70))],out/'r2-inside.png',camera=(40,-90,-140))
for label,m in [('upper',upper),('lower',lower)]:
    print(label,'parts',[(len(c.faces),c.volume,c.bounds.tolist()) for c in m.split()])
