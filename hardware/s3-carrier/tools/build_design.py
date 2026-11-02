"""Generate an editable carrier from measured public EDA source geometry.

This is a board design, not proof of enclosure or radio validation. Millimetres
are used after importing the upstream mil coordinates. Original footprints and
their mechanical holes are retained rather than approximated with pictures.
"""
import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import uuid

from source_geometry import read_archive, board_geometry, pads, symbol_pins

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'A4'
STEM = f'HachimoDock-S3-carrier-{REVISION}'
ORIGIN = (2809.9375, 2905.4714)
MIL = .0254
FIXED_IO = {'LCD_CLK':21,'LCD_MOSI':47,'LCD_RST':45,'LCD_DC':40,'LCD_CS':41,
            'LCD_BL':42,'MIC_WS':4,'MIC_BCLK':5,'MIC_DIN':6,
            'SPEAKER_DOUT':7,'SPEAKER_BCLK':15,'SPEAKER_WS':16,
            'PREVIOUS_GPIO':39,'NEXT_GPIO':38,'CONFIRM_GPIO':0}


def uid(value):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'hachimodock-s3-carrier/' + value))


def norm(x, y):
    return ((x - ORIGIN[0]) * MIL, (ORIGIN[1] - y) * MIL)


def placement(x, y, angle=0):
    return {'x': ORIGIN[0] + x / MIL, 'y': ORIGIN[1] - y / MIL, 'angle': angle}


def transform(component, x, y):
    angle = math.radians(component['angle'])
    return norm(component['x'] + x * math.cos(angle) - y * math.sin(angle),
                component['y'] + x * math.sin(angle) + y * math.cos(angle))


def circle_holes(document):
    result = []
    for head, value in document['records']:
        if head['type'] != 'FILL' or value.get('layerId') != 12:
            continue
        for path in value['path']:
            if path[0] == 'CIRCLE':
                result.append((path[1], path[2], 2 * path[3]))
    return result


def build():
    upstream = read_archive(ROOT / 'reference/upstream-pcb-v1.2.epro2')
    reference = read_archive(ROOT / 'reference/goouuu-reference-carrier.epro2')
    source = board_geometry(upstream['1ecf9d019d074243'])
    design = {'schema':1, 'revision':REVISION, 'status':'engineering-draft',
              'units':'mm', 'fixedIo':FIXED_IO, 'components':[],
              'mountingHoles':[], 'outline':[], 'traces':[], 'vias':[],
              'fabricationApproved':False,
              'enclosureVerified':False, 'screenMechanicalDimensionsVerified':False,
              'usbSide':'left','usbOpeningAlignmentVerified':False,
              'moduleRotationFromA1Deg':180,'moduleShiftTowardUsbMm':3.0,
              'usbEndReferenceEnvelopeXmm':-.525,'usbFaceDimensionsVerified':False,
              'nylonMountingHoles':['H2']}
    for path in source['outline']:
        start = norm(path[0], path[1]); end = norm(path[-2], path[-1])
        design['outline'].append({'start':start, 'end':end,
                                  'angle':-path[3] if path[2]=='ARC' else 0})
    for i, hole in enumerate(source['holes'], 1):
        x, y = norm(hole['x'], hole['y'])
        design['mountingHoles'].append({'ref':f'H{i}', 'x':x, 'y':y,
                                       'diameter':hole['diameter']*MIL})

    def add(ref, document, where, netmap, envelope=None, title=None):
        cx, cy = norm(where['x'], where['y'])
        component = {'ref':ref,'title':title or ref,'sourceFootprint':document['head']['uuid'],
                     'x':cx,'y':cy,'pads':[],'holes':[], 'envelope':envelope}
        for pad in pads(document):
            x, y = transform(where, pad['centerX'], pad['centerY'])
            component['pads'].append({'number':pad['num'], 'sourceId':pad['source_id'],
                'x':x,'y':y, 'net':netmap.get(pad['num'], ''),
                'width':pad['defaultPad']['width']*MIL,
                'height':pad['defaultPad']['height']*MIL,
                'drill':pad['hole']['width']*MIL,
                'angle':-where['angle'],
                'shape':'rect' if pad['defaultPad']['padType']=='RECT' else 'circle'})
        for x, y, diameter in circle_holes(document):
            x, y = transform(where,x,y)
            component['holes'].append({'x':x,'y':y,'diameter':diameter*MIL})
        design['components'].append(component)
        return component

    s3_symbol = symbol_pins(reference['dec5ecc4336c40cd976d9e8e08c16bd8'])
    used = {f'GPIO{n}' for n in FIXED_IO.values()} | {'GPIO1','GPIO2','GPIO8'}
    s3nets = {pin: ('+3V3' if name=='3V3' else '+5V' if name=='5V+' else
                     name if name=='GND' or name in used else '')
              for pin, name in s3_symbol.items()}
    add('U1', reference['e7f74316ee0e465e9b94fc43b531cec9'],
        # Rotate the entire module 180 degrees about its A1 envelope centre
        # (36.365,14.897), then move 3mm toward the USB edge. All numbered
        # pins and GPIO nets move together. USB faces left, antenna right.
        # The USB-end reference envelope overhangs the carrier by 0.525mm;
        # actual connector face dimensions still need physical verification.
        placement(57.73,2.294,-90), s3nets, [-.525,.897,67.255,28.897],
        'GOOUUU S3 N16R8 / 2x21 sockets')
    for i, gpio in [(1,39),(2,38),(3,0)]:
        item=source['components'][f'SW{i}']; x,y=transform(item,-98.425,-190.945)
        add(f'SW{i}', upstream[item['Footprint']], item,
            {'1':f'GPIO{gpio}','2':'GND'}, [x-7.5,y-7.5,x+7.5,y+7.5],
            f'Original switch / GPIO{gpio}')
    joy = source['components']['U2']
    add('JS1',upstream[joy['Footprint']],joy,
        {'A1':'+3V3','A2':'GPIO2','A3':'GND','B1':'GND','B2':'GPIO1',
         'B3':'+3V3','0':'GND','A':'GND','B':'GPIO8','C':'GND','D':'GPIO8'},
        [56.32495,46.14864,73.02495,68.74864], 'Original YA13S joystick')
    # Preserve the lug positions and drill. Reduce copper diameter by 0.2mm
    # for 0.5mm clearance at the original curved board edge (0.3mm annulus).
    for pad in design['components'][-1]['pads']:
        if pad['number']=='0':pad['width']=pad['height']=1.8
    add('U2',reference['5aaf4eea8f904dbb8f7d8e8dc6f555cd'],placement(4.5,48),
        {'1':'+3V3','2':'GND','3':'+3V3','4':'AMP_GAIN','5':'GPIO7',
         '6':'GPIO15','7':'GPIO16'},
        [2.72,31.3,23.1,49.3], 'MAX98357A module')
    # Speaker terminals stay entirely on the amplifier module. No carrier
    # pads, holes or nets are needed underneath those two terminals.
    amplifier=design['components'][-1]
    amplifier['pads']=[p for p in amplifier['pads'] if p['number'] not in ['8','9']]
    add('U3',reference['73b7a759f9084adc8996032c26e82fc4'],placement(42.19,44.64),
        {'1':'GND','2':'+3V3','3':'GPIO6','4':'GND','5':'GPIO4','6':'GPIO5'},
        [39,35.1,53,49.1], 'Round INMP441 / 14mm')
    design['components'][-1]['holes'].append({'x':46,'y':42.1,'diameter':2.0})
    # Header only: preserve the user's working direct GPIO wiring.
    def generic(ref,title,x,y,entries,envelope):
        comp={'ref':ref,'title':title,'sourceFootprint':'generated', 'x':x,'y':y,
              'pads':[],'holes':[],'envelope':envelope}
        for number,px,py,net in entries:
            comp['pads'].append({'number':str(number),'x':px,'y':py,'net':net,
                'width':1.8,'height':1.8,'drill':1.0,'angle':0,
                'shape':'rect' if str(number)=='1' else 'circle'})
        design['components'].append(comp)
    generic('J1','LCD: GND VCC(3V3) SCL SDA RES DC CS BLK',27,31.0,
            [(i+1,27+2.54*i,31.0,net) for i,net in enumerate(
                ['GND','+3V3','GPIO21','GPIO47','GPIO45','GPIO40','GPIO41','GPIO42'])],
            [25.73,29.73,46.05,32.27])
    # Standard single 2.54mm shunt: 1-2=VDD/6dB, open=9dB,
    # 2-3=GND/12dB in I2S mode. Never fit two shunts simultaneously.
    generic('JP1','AMP GAIN / 1-2=6dB OPEN=9dB 2-3=12dB',28,41.54,
            [('1',28,39,'+3V3'),('2',28,41.54,'AMP_GAIN'),('3',28,44.08,'GND')],
            [26.73,37.73,29.27,45.35])
    design['gainSelector']={'reference':'JP1','pitchMm':2.54,
        'pins':{'1':'+3V3','2':'AMP_GAIN','3':'GND'},
        'modes':{'1-2':6,'open':9,'2-3':12},
        'headerBodyMaximumMm':[2.54,7.62],
        'shuntBodyMaximumMm':[4.0,5.5],
        'assemblyEnvelope':[26.0,37.3,30.0,45.8],
        'singleShuntOnly':True,'changeOnlyWhenUnpowered':True,
        'moduleGainStrappingVerified':False,'heightVerified':False}
    # Rotate the A1 antenna keepout with the actual module, not just its label.
    # Extend the translated antenna keepout to the carrier's right edge;
    # H2 is retained but must use a non-metallic (nylon) fastener nearby.
    design['antennaKeepout']=[61.73,.594,74.0,29.294]
    # Separate single-row female socket strips, viewed from the component side.
    # The body width is an assembly planning allowance, not a measured vendor
    # model; socket/module heights still need enclosure stack-up verification.
    design['mountingSockets']=[]
    for ref,groups in [('U1',[list(map(str,range(1,22))),list(map(str,range(22,43)))]),
                       ('U2',[list(map(str,range(1,8)))]),
                       ('U3',[['1','2','3'],['4','5','6']])]:
        component=next(c for c in design['components'] if c['ref']==ref)
        for index,numbers in enumerate(groups,1):
            group=[p for p in component['pads'] if p['number'] in numbers]
            xs=[p['x'] for p in group];ys=[p['y'] for p in group]
            design['mountingSockets'].append({'parent':ref,'strip':index,'pins':len(group),
                'padNumbers':numbers,'pitch':2.54,'centerX':sum(xs)/len(xs),'centerY':sum(ys)/len(ys),
                'bodyEnvelope':[min(xs)-1.27,min(ys)-1.27,max(xs)+1.27,max(ys)+1.27],
                'heightVerified':False})
    design['amplifierSupplyUserConfirmed']='3V3'
    design['joystickFirmwareStatus']='reserved-only; not initialized by current S3 code'
    design['microphoneMounting']={'source':'user-supplied pre-soldered module photo',
        'diameterMm':14.0,'socketRowPitchMm':7.62,
        'labelSide':'up/outward','longPins':'down/into-carrier-sockets',
        'leftTopToBottom':['SD','3V3','GND'],'rightTopToBottom':['SCK','WS','L/R'],
        'physicalPhotoOrientationChecked':True,'pcbAssemblyTested':False}
    design['screenConnectorOrder']=['GND','VCC','SCL','SDA','RES','DC','CS','BLK']
    # Include the mated female Dupont housing, not only male header pads.
    # Select a standard 8P housing within this explicit 22 x 3 mm envelope.
    design['connectorMatingEnvelopes']=[{'ref':'J1','maximumPlugBodyMm':[22,3],
        'envelope':[24.89,29.5,46.89,32.5],'heightVerified':False}]
    # The retained 3mm holes need head clearance, not just drill clearance.
    # This is a selected maximum head size, not a measured original screw.
    design['fastenerEnvelopes']=[{'ref':h['ref'],'x':h['x'],'y':h['y'],
        'maximumHeadDiameterMm':6.0,'headHeightAllowanceMm':3.0,
        'copperKeepoutRadiusMm':3.5,'actualFastenerVerified':False,
        'material':'nylon' if h['ref'] in design['nylonMountingHoles'] else 'unspecified'}
        for h in design['mountingHoles']]
    # Original STEP keycaps measure about 18.021mm; reserve 18.5mm here.
    design['keycapEnvelopes']=[]
    for c in design['components']:
        if c['ref'] not in ['SW1','SW2','SW3']:continue
        x1,y1,x2,y2=c['envelope'];cx=(x1+x2)/2;cy=(y1+y2)/2
        design['keycapEnvelopes'].append({'ref':c['ref'],'planningSizeMm':18.5,
            'envelope':[cx-9.25,cy-9.25,cx+9.25,cy+9.25]})
    # YA13S axis is the intersection of the two potentiometer centre lines,
    # not the footprint origin. Preserve the original shaft/key coordinates.
    # This is a conservative reserved XY area for *added* modules/cables,
    # not a claim that a 30mm cap is fitted or that original keycaps collide.
    design['joystickMotionReservation']={'center':[65.62495,59.44864],
        'radiusMm':15.0,'cap':'original 3D-printed spherical cap; user confirmed',
        'capDiameterFromStepMm':14.01,'nominalEachSideAngleDeg':30,
        'planningEachSideAngleDeg':32,'maximumCapCenterTravelAllowanceMm':7.99,
        'purpose':'keep new modules and cable housings outside a conservative motion reservation',
        'originalControlsRetained':True,'threeDimensionalSweepVerified':False,
        'unverified':['joystick pivot relative to printed cap','installed module/keycap/socket heights',
            'screen/back-cover geometry','full sweep and click clearance to original SW3 keycap']}
    # Ground pours explicitly avoid the antenna corner even in interchange
    # formats that cannot represent the native KiCad antenna rule area.
    design['groundPourPolygon']=[[-1,-1],[61.73,-1],[61.73,29.294],
        [75,29.294],[75,71],[-1,71]]
    # Stitch the small J1 ground pocket to the opposite plane so the cable
    # ground does not depend on thermal spokes ending on an isolated island.
    design['groundStitches']=[{'x':27,'y':32.0,'padRef':'J1','padNumber':'1'}]
    design['silkscreen']=[]
    def label(text,x,y,size=.8):
        design['silkscreen'].append({'text':text,'x':x,'y':y,'size':size,'thickness':.12})
    for text,x,y,size in [('GOOUUU S3 N16R8',36,14,1.15),(f'{REVISION} / USB LEFT',36,18,1),
        ('USB <',4,15,.8),('ANT NO CU',66,15,.8),('H2 NYLON',61.05,8.5,.8),
        ('AMP 3V3',13,40,.8),('MIC UP',50,35,.8),
        ('JP1',28,36,.8),('6dB',32,39,.8),('GAIN',32,41.54,.8),
        ('12dB',32,44.08,.8),('OPEN 9dB',29.5,47,.8),
        ('SW1/39',7.46,50,.8),('SW2/38',26.47,50,.8),('SW3/0',45.48,50,.8),
        ('JOY RSV',64,46,.8),('1/2/8',64,44.5,.8)]:label(text,x,y,size)
    for i,name in enumerate(design['screenConnectorOrder']):label(name,27+2.54*i,29.35)
    names={'U2':{'1':'3V3','2':'GND','3':'SD','4':'GAIN','5':'DIN','6':'BCLK','7':'LRC'},
           'U3':{'1':'GND','2':'3V3','3':'SD','4':'L/R','5':'WS','6':'SCK'}}
    for c in design['components']:
        if c['ref'] not in names:continue
        for p in c['pads']:
            x=p['x']+3.4 if c['ref']=='U2' else p['x']+(-3 if p['number'] in ['1','2','3'] else 3)
            label(names[c['ref']][p['number']],x,p['y'])
    design['limits']={'trackWidth':.25,'clearance':.2,'edgeClearance':.5,
                      'viaDiameter':.7,'viaDrill':.35,'pcbThickness':1.6}
    return design


def arc_mid(start, end, angle):
    sx,sy=start;ex,ey=end;theta=math.radians(angle)
    cx=(sx+ex)/2-(ey-sy)/(2*math.tan(theta/2))
    cy=(sy+ey)/2+(ex-sx)/(2*math.tan(theta/2))
    dx,dy=sx-cx,sy-cy;t=theta/2
    return cx+dx*math.cos(t)-dy*math.sin(t),cy+dx*math.sin(t)+dy*math.cos(t)


def kicad(design, output):
    def q(text):return json.dumps(text,ensure_ascii=False)
    def n(value):return f'{value:.6f}'
    def xy(point):return f'{n(point[0]+100)} {n(point[1]+80)}'
    netnames=sorted({p['net'] for c in design['components'] for p in c['pads'] if p['net']})
    nets={name:i+1 for i,name in enumerate(netnames)}
    s=['(kicad_pcb (version 20241229) (generator "pcbnew")',
       '(general (thickness 1.6)) (paper "A4")',
       '(layers (0 "F.Cu" signal) (31 "B.Cu" signal) (36 "B.SilkS" user "b.silkscreen")',
       '(35 "F.Paste" user) (37 "F.SilkS" user "f.silkscreen") (38 "B.Mask" user) (39 "F.Mask" user)',
       '(44 "Edge.Cuts" user) (46 "B.CrtYd" user "b.courtyard")',
       '(47 "F.CrtYd" user "f.courtyard") (49 "F.Fab" user))',
       '(setup (pad_to_mask_clearance 0.05))', '(net 0 "")']
    s += [f'(net {i} {q(name)})' for name,i in nets.items()]
    for c in design['components']:
        anchor=(c['x'],c['y']);ref=c['ref']
        s += [f'(footprint {q("S3_Carrier:"+ref)} (layer "F.Cu") (uuid {uid(ref)}) (at {xy(anchor)})',
              f'(property "Reference" {q(ref)} (at 0 -2) (layer "F.Fab") (effects (font (size 0.9 0.9) (thickness 0.15))))',
              f'(property "Value" {q(c["title"])} (at 0 0) (layer "F.Fab") hide (effects (font (size 1 1) (thickness 0.15))))',
              '(attr smd)' if c.get('mount')=='smd' else '(attr through_hole)']
        for i,p in enumerate(c['pads']):
            net=f'(net {nets[p["net"]]} {q(p["net"])})' if p['net'] else ''
            mount='smd' if c.get('mount')=='smd' else 'thru_hole'
            drill='' if mount=='smd' else f'(drill {n(p["drill"])})'
            layers='"F.Cu" "F.Paste" "F.Mask"' if mount=='smd' else '"*.Cu" "*.Mask"'
            s.append(f'(pad {q(p["number"])} {mount} {p["shape"]} (at {n(p["x"]-anchor[0])} {n(p["y"]-anchor[1])} {n(p["angle"])}) '
                     f'(size {n(p["width"])} {n(p["height"])}) {drill} '
                     f'(layers {layers}) {net} (uuid {uid(ref+"/pad/"+str(i))}))')
        for i,h in enumerate(c['holes']):
            s.append(f'(pad "" np_thru_hole circle (at {n(h["x"]-anchor[0])} {n(h["y"]-anchor[1])}) '
                     f'(size {n(h["diameter"])} {n(h["diameter"])}) (drill {n(h["diameter"])}) '
                     f'(layers "*.Cu" "*.Mask") (uuid {uid(ref+"/hole/"+str(i))}))')
        if c['envelope']:
            a,b,d,e=c['envelope']
            for layer,width in [('F.Fab',.1),('F.CrtYd',.05)]:
                s.append(f'(fp_rect (start {n(a-anchor[0])} {n(b-anchor[1])}) '
                         f'(end {n(d-anchor[0])} {n(e-anchor[1])}) '
                         f'(stroke (width {width}) (type default)) (fill none) (layer "{layer}"))')
        s.append(')')
    for i,h in enumerate(design['mountingHoles']):
        s.append(f'(footprint "MountingHole:Original_3mm" (layer "F.Cu") (at {xy((h["x"],h["y"]))}) '
                 f'(attr exclude_from_pos_files exclude_from_bom) '
                 f'(property "Reference" "{h["ref"]}" (at 0 -2.5) (layer "F.Fab") (effects (font (size .8 .8) (thickness .12)))) '
                 f'(pad "" np_thru_hole circle (at 0 0) (size {n(h["diameter"])} {n(h["diameter"])}) '
                 f'(drill {n(h["diameter"])}) (layers "*.Cu" "*.Mask")))')
    for edge in design['outline']:
        if edge['angle']:
            mid=arc_mid(edge['start'],edge['end'],edge['angle'])
            s.append(f'(gr_arc (start {xy(edge["start"])}) (mid {xy(mid)}) (end {xy(edge["end"])}) (stroke (width .05) (type default)) (layer "Edge.Cuts"))')
        else:
            s.append(f'(gr_line (start {xy(edge["start"])}) (end {xy(edge["end"])}) (stroke (width .05) (type default)) (layer "Edge.Cuts"))')
    for route in design.get('traces',[]):
        for a,b in zip(route['points'],route['points'][1:]):
            if a==b:continue
            s.append(f'(segment (start {xy(a)}) (end {xy(b)}) (width {route.get("width",.25)}) '
                     f'(layer "{route["layer"]}") (net {nets[route["net"]]}))')
    for via in design.get('vias',[]):
        s.append(f'(via (at {xy((via["x"],via["y"]))}) (size .7) (drill .35) (layers "F.Cu" "B.Cu") (net {nets[via["net"]]}))')
    a,b,c,d=design['antennaKeepout']
    s.append(f'(zone (net 0) (net_name "") (layers "F.Cu" "B.Cu") '
             f'(uuid {uid("antenna-keepout")}) (hatch edge .5) '
             '(keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed) (footprints allowed)) '
             f'(polygon (pts (xy {xy((a,b))}) (xy {xy((c,b))}) (xy {xy((c,d))}) (xy {xy((a,d))}))))')
    for fastener in design.get('fastenerEnvelopes',[]):
        # Circumscribe the polygon so its inradius is at least the specified
        # keepout radius, including midway between its vertices.
        radius=fastener['copperKeepoutRadiusMm']/math.cos(math.pi/36)
        points=' '.join(f'(xy {xy((fastener["x"]+radius*math.cos(t*math.pi/18),fastener["y"]+radius*math.sin(t*math.pi/18)))})' for t in range(36))
        s.append(f'(zone (net 0) (net_name "") (layers "F.Cu" "B.Cu") (uuid {uid("head-keepout/"+fastener["ref"])}) '
            '(hatch edge .5) (keepout (tracks not_allowed) (vias not_allowed) (pads not_allowed) '
            f'(copperpour not_allowed) (footprints allowed)) (polygon (pts {points})))')
    s.append(')')
    output.write_text('\n'.join(s)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'output')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    design=build();(args.output/'design.json').write_text(json.dumps(design,indent=2)+'\n')
    kicad(design,args.output/f'{STEM}.kicad_pcb')
    with (args.output/'connections.csv').open('w',newline='') as stream:
        w=csv.writer(stream);w.writerow(['reference','pin','net','x_mm','y_mm'])
        for c in design['components']:
            for p in c['pads']:w.writerow([c['ref'],p['number'],p['net'],f'{p["x"]:.4f}',f'{p["y"]:.4f}'])
    print(json.dumps({'components':len(design['components']), 'pads':sum(len(c['pads']) for c in design['components']),
                      'output':str(args.output)},ensure_ascii=False))


if __name__=='__main__':main()
