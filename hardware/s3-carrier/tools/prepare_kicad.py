"""Finalize the editable KiCad project and its self-contained footprint library."""
import json
import argparse
import math
from pathlib import Path

import pcbnew
from build_design import REVISION, STEM, kicad,uid

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'
BOARD=OUT/f'{STEM}.kicad_pcb'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,default=OUT)
    args=parser.parse_args()
    out=args.directory
    design=json.loads((out/'design.json').read_text())
    boardfile=out/f'HachimoDock-S3-carrier-{design["revision"]}.kicad_pcb'
    # Regenerate from the routed data, so repeated finalization never
    # accumulates text or depends on SWIG ownership when removing drawings.
    kicad(design,boardfile)
    b=pcbnew.LoadBoard(str(boardfile));library=out/'S3_Carrier.pretty'
    library.mkdir(exist_ok=True)
    plugin=pcbnew.PCB_IO_KICAD_SEXPR()
    for fp in b.GetFootprints():
        fp.SetFPID(pcbnew.LIB_ID('S3_Carrier',fp.GetReference()))
        plugin.FootprintSave(str(library),fp)
    (out/'fp-lib-table').write_text('(fp_lib_table\n (lib (name "S3_Carrier") (type "KiCad") (uri "${KIPRJMOD}/S3_Carrier.pretty") (options "") (descr "Embedded carrier footprints"))\n)\n')
    for label in design['silkscreen']:
        text,x,y,size=label['text'],label['x'],label['y'],label['size']
        item=pcbnew.PCB_TEXT(b);item.SetText(text);item.SetLayer(pcbnew.F_SilkS)
        item.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size),pcbnew.FromMM(size)))
        item.SetTextThickness(pcbnew.FromMM(label['thickness']))
        item.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x+100),pcbnew.FromMM(y+80)));b.Add(item)
    rules=b.GetDesignSettings()
    rules.m_CopperEdgeClearance=pcbnew.FromMM(.5)
    rules.m_HoleClearance=pcbnew.FromMM(.25)
    rules.m_MinClearance=pcbnew.FromMM(.2)
    # Head keepouts are annular around the retained nonplated mounting hole.
    # The NPTH itself belongs inside its own keepout; cutting out only the
    # actual drill avoids falsely forbidding the mounting hole, while native
    # hole clearance still prohibits any copper in that inner opening.
    for f in design.get('fastenerEnvelopes',[]):
        z=next(z for z in b.Zones() if z.m_Uuid.AsString()==uid('head-keepout/'+f['ref']))
        h=next(h for h in design['mountingHoles'] if h['ref']==f['ref'])
        hole=z.Outline().NewHole(0);radius=h['diameter']/2+.025
        for i in range(36):
            angle=-i*math.pi/18
            z.Outline().Append(pcbnew.FromMM(f['x']+100+radius*math.cos(angle)),
                                  pcbnew.FromMM(f['y']+80+radius*math.sin(angle)),0,hole)
    for layer in [pcbnew.F_Cu,pcbnew.B_Cu]:
        zone=pcbnew.ZONE(b);zone.SetLayer(layer);zone.SetNet(b.FindNet('GND'))
        zone.SetLocalClearance(pcbnew.FromMM(.25));zone.SetMinThickness(pcbnew.FromMM(.2))
        zone.SetThermalReliefGap(pcbnew.FromMM(.25))
        zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(.35))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        zone.Outline().NewOutline()
        for x,y in design['groundPourPolygon']:
            zone.Outline().Append(pcbnew.FromMM(x+100),pcbnew.FromMM(y+80))
        b.Add(zone)
    if not pcbnew.ZONE_FILLER(b).Fill(b.Zones()):
        raise SystemExit('Native ground-zone fill failed.')
    pcbnew.SaveBoard(str(boardfile),b)
    project={'meta':{'filename':boardfile.with_suffix('.kicad_pro').name,'version':1},
             'board':{'design_settings':{'rules':{'min_clearance':.2,'min_track_width':.25,
                 'min_copper_edge_clearance':.5,'min_hole_clearance':.25,
                 'min_through_hole_diameter':.3,'min_via_annular_width':.15}}},
             'net_settings':{'classes':[{'name':'Default','clearance':.2,'track_width':.25,
                 'via_diameter':.7,'via_drill':.35,'microvia_diameter':.3,'microvia_drill':.1}]}}
    boardfile.with_suffix('.kicad_pro').write_text(json.dumps(project,indent=2)+'\n')
    print('Saved self-contained KiCad project and footprint library.')


if __name__=='__main__':main()
