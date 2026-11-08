"""Detect the duplicate scaled joystick lip outside the original control rim."""
import json
import sys
from pathlib import Path
import numpy as np
import trimesh
import manifold3d as mf

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_enclosure import solid


def main():
    out=ROOT/'output/r4-original-copy'
    path=Path(sys.argv[1]) if len(sys.argv)>1 else out/'a4-upper-r4-assembly.stl'
    current=solid(trimesh.load_mesh(path))
    source=solid(trimesh.load_mesh(out/'native-original-upper.stl'))
    lo=np.array([74.87495,-64.19864,16.45525253169416])
    hi=np.array([76.19,-49.89106,20.])
    region=mf.Manifold.cube((hi-lo).tolist()).translate(lo.tolist())
    report={'region_mm':[lo.tolist(),hi.tolist()],
            'original_material_above_deck_mm3':(source^region).volume(),
            'current_material_above_deck_mm3':(current^region).volume(),
            'file':str(path)}
    print(json.dumps(report,indent=2))
    assert report['original_material_above_deck_mm3']<.001,report
    assert report['current_material_above_deck_mm3']<.01,report
    return report


if __name__=='__main__':main()
