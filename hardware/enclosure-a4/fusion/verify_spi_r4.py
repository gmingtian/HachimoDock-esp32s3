"""Check the measured SPI connector stack and a possible eight-wire exit route.

User measurements: housing 14 mm, installed PCB-back-to-tail 17 mm.
Wire OD 1.2 mm and a 3 mm centreline bend radius are design assumptions.
The route turns right into the case, then runs 3 mm along U; it does not require bending
inside the rigid housing or treating housing length as installed height.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import manifold3d as mf
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_enclosure import D, P, solid, mesh, pcb_box

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/r4-original-copy'


def main():
    w = json.loads((ROOT / 'fusion/working-r4.json').read_text(encoding='utf-8'))
    origin = np.array(w['screen_origin_mm'])
    angle = w['screen_angle_deg']
    back = w['screen_pcb_front_n_mm'] - 1.6

    def place(s):
        return s.rotate([angle, 0, 0]).translate(origin.tolist())

    def box(u0, u1, v0, v1, n0, n1):
        return mf.Manifold.cube([u1-u0, v1-v0, n1-n0]).translate([u0, v0, n0])

    upper = solid(trimesh.load_mesh(OUT / 'a4-upper-r4-assembly.stl'))
    lower = solid(trimesh.load_mesh(OUT / 'a4-lower-r4-assembly.stl'))
    part = next(c for c in D['components'] if c['ref'] == 'U1')
    z = P['pcb_bottom_z'] + 12.6
    devboard = pcb_box(part['envelope'], z, z+5.1)

    # Include all eight separate housings and the projecting header base.
    installed = place(box(.2, 3.8, 14.3, 36.7, back-17, back+.1))
    segments = []; clearance_segments = []
    for v in np.linspace(16.61, 34.39, 8):
        points = [[2+3-3*math.cos(t), float(v), back-17-3*math.sin(t)]
                  for t in np.linspace(0, math.pi/2, 25)]
        points.append([8, float(v), back-20])
        for a, b in zip(points, points[1:]):
            segments.append(solid(trimesh.creation.cylinder(radius=.6, segment=[a, b], sections=16)))
            clearance_segments.append(solid(trimesh.creation.cylinder(radius=1, segment=[a, b], sections=16)))
        for p in points:
            segments.append(mf.Manifold.sphere(.6, 16).translate(p))
            clearance_segments.append(mf.Manifold.sphere(1, 16).translate(p))
    wires = place(mf.Manifold.batch_boolean(segments, mf.OpType.Add))
    reserve = place(mf.Manifold.batch_boolean(clearance_segments, mf.OpType.Add))
    rows = {}
    for name, envelope in [('installed_connector', installed), ('wire_clearance_route', reserve), ('wire_exit_route', wires)]:
        row = {label+'_overlap_mm3': (envelope ^ target).volume()
               for label, target in [('upper', upper), ('lower', lower), ('U1', devboard)]}
        row['U1_gap_mm'] = envelope.min_gap(devboard, 30)
        rows[name] = row
    report = {
        'housing_length_mm': 14, 'installed_height_from_pcb_back_mm': 17,
        'wire_od_assumed_mm': 1.2, 'wire_bend_radius_assumed_mm': 3,
        'rear_reserve_from_pcb_back_mm': 21,
        'physical_wire_route_verified': False,
        'screen_extension_v_mm': w['screen_extension_v_mm'],
        'checks': rows,
        'assembly_hashes': {label: hashlib.sha256((OUT / f'a4-{label}-r4-assembly.stl').read_bytes()).hexdigest()
                            for label in ['upper', 'lower']},
    }
    (OUT / 'spi-17mm-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    mesh(installed).export(OUT / 'analysis-installed-spi-17mm.stl')
    mesh(wires).export(OUT / 'analysis-spi-wire-route.stl')
    print(json.dumps(report, indent=2))
    assert all(row[key] < .025 for row in rows.values() for key in row if key.endswith('_overlap_mm3')), rows
    assert min(row['U1_gap_mm'] for row in rows.values()) >= .8, rows


if __name__ == '__main__':
    main()
