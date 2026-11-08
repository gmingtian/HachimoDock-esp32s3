"""Read original STEP solids and preserve unmodified, individually exported meshes."""
from pathlib import Path
import hashlib
import json
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.StlAPI import StlAPI_Writer

ROOT = Path(__file__).resolve().parent
source = ROOT / "reference/original-assembly.STEP"
expected = "0c4a8b58af7ed373da93895adf4c9dde235b14f9bbf6209ec10d7f310a2b896c"
digest = hashlib.sha256(source.read_bytes()).hexdigest()
assert digest == expected, (digest, expected)
reader = STEPControl_Reader()
assert reader.ReadFile(str(source)) == 1
reader.TransferRoots()
ex = TopExp_Explorer(reader.OneShape(), TopAbs_SOLID)
report = {"sourceSha256": digest, "sourceAxes": "X left-right; Y height; Z front-back", "solids": []}
out = ROOT / "reference/step-solids"
out.mkdir(exist_ok=True)
i = 0
while ex.More():
    shape = ex.Current()
    bb = Bnd_Box()
    BRepBndLib.Add_s(shape, bb)
    lo, hi = bb.CornerMin(), bb.CornerMax()
    bounds = [lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()]
    report["solids"].append({"index": i, "bounds": bounds,
                              "size": [bounds[k+3]-bounds[k] for k in range(3)]})
    BRepMesh_IncrementalMesh(shape, .06, False, .15, True)
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    assert writer.Write(shape, str(out / f"solid-{i}.stl"))
    i += 1
    ex.Next()
(ROOT / "reference/original-inspection.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
