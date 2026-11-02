"""Report dimensioned XY checks separately from unverified Z/motion checks."""
import hashlib
import json
import math
from pathlib import Path
from build_design import ROOT,REVISION


def distance(a,b):
    return math.hypot(max(a[0]-b[2],b[0]-a[2],0),max(a[1]-b[3],b[1]-a[3],0))


def main():
    out=ROOT/'output';d=json.loads((out/'design.json').read_text())
    audit=json.loads((out/'electrical-audit.json').read_text())
    digest=hashlib.sha256((out/'design.json').read_bytes()).hexdigest()
    assert audit['designSha256']==digest and audit['allNativePadPositionsVerified']
    bodies={c['ref']:c['envelope'] for c in d['components']}
    sockets=[s['bodyEnvelope'] for s in d['mountingSockets'] if s['parent']=='U1']
    plug=d['connectorMatingEnvelopes'][0]['envelope']
    caps={c['ref']:c['envelope'] for c in d['keycapEnvelopes']}
    checks=[('屏幕插头—果云下排排母',min(distance(plug,s) for s in sockets),.5),
        ('屏幕插头—麦克风包络',distance(plug,bodies['U3']),1.0),
        ('麦克风包络—SW3键帽预留',distance(bodies['U3'],caps['SW3']),1.0),
        ('功放包络—SW1键帽预留',distance(bodies['U2'],caps['SW1']),.8),
        ('摇杆本体—SW3键帽预留',distance(bodies['JS1'],caps['SW3']),1.0)]
    checks += [(f'屏幕插头—{h["ref"]}螺丝头Ø6',distance(plug,[h['x'],h['y'],h['x'],h['y']])-3,.5)
               for h in d['mountingHoles']]
    jumper=d['gainSelector']['assemblyEnvelope']
    checks += [(f'JP1含跳线帽—{ref}模块',distance(jumper,bodies[ref]),1.0) for ref in ['U1','U2','U3']]
    checks += [('JP1含跳线帽—屏幕插头',distance(jumper,plug),1.0)]
    checks += [(f'JP1含跳线帽—{ref}键帽预留',distance(jumper,cap),1.0) for ref,cap in caps.items()]
    checks += [(f'JP1含跳线帽—{h["ref"]}螺丝头Ø6',distance(jumper,[h['x'],h['y'],h['x'],h['y']])-3,1.0)
               for h in d['mountingHoles']]
    for name,actual,minimum in checks:
        assert actual>=minimum-1e-5,(name,actual,minimum)
    motion=d['joystickMotionReservation'];x,y=motion['center'];r=motion['radiusMm']
    newparts={k:bodies[k] for k in ['U1','U2','U3','J1']};newparts['J1插头']=plug;newparts['JP1含跳线帽']=jumper
    motion_gaps={ref:round(distance([x,y,x,y],body)-r,4) for ref,body in newparts.items()}
    assert min(motion_gaps.values())>=1
    keygap=distance([x,y,x,y],caps['SW3'])-r
    report={'status':'dimensioned XY checks passed; complete 3D assembly and motion unverified',
        'designSha256':digest,'boardSha256':audit['boardSha256'],
        'layoutLockedToUpstream':['outline','five mounting holes','SW1','SW2','SW3','JS1'],
        'checks':[{'pair':name,'clearanceMm':round(actual,4),'minimumPlanningMm':minimum}
                  for name,actual,minimum in checks],
        'plugMaximumBodyMm':[22,3],'keycapPlanningSizeMm':18.5,
        'gainSelectorAssemblyEnvelope':jumper,'shuntBodyMaximumMm':[4,5.5],
        'joystickCap':'original 3D-printed cap; nominal sphere diameter 14mm',
        'newPartClearanceOutsideMotionReservationMm':motion_gaps,
        'motionReservationRadiusMm':r,'reservationIsMeasuredMotion':False,
        'SW3ToMotionReservationSignedXYGapMm':round(keygap,4),
        'SW3Interpretation':'Conservative XY reservation overlaps original SW3 cap projection. This is not a 3D collision result; original controls are retained. Installed pivot/height and full tilt/click require assembly verification.',
        'unverified':['socket heights and screw-head clearance under U1/U2',
            'joystick pivot/printed-cap fit; full sweep and click relative to SW3',
            'screen, housing, cable bend and USB plug stack-up'],
        'fabricationApproved':False}
    (out/'mechanical-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=[f'# {REVISION} 装配间隙核对','',
        '以下为已锁定布局的平面包络计算，并与最终 PCB 的焊盘坐标校验值关联；不是整机三维无干涉证明。',
        '', '| 检查对象 | 包络间隙 mm | 规划下限 mm |','|---|---:|---:|']
    lines += [f'| {name} | {actual:.3f} | {minimum:.1f} |' for name,actual,minimum in checks]
    lines += ['', 'JP1采用2.54mm三针直排针与一个跳线帽，帽体限4×5.5mm；两种插法与针座的总平面包络按4×8.5mm预留。实际高度和外壳可达性仍需装配确认。']
    lines += ['', '屏幕杜邦插头选型限制为外壳不超过 22×3mm；实际排母宽度、插头与线缆高度仍需核准。键帽按18.5mm预留，原版STEP中三个键帽约18.021mm。',
        '', '摇杆保持原版孔位、封装、朝向，使用用户确认的原版约14mm 3D打印圆帽。按厂家图纸使用角为±30°，角度公差另留2°；新模块与插头避开R15mm保守活动预留圈。这个圈包含较大的杆帽中心位移规划余量，不是实测帽子扫过边界，也不表示帽子直径30mm。',
        '', '该保守圈与原版SW3键帽在俯视投影中相交；高度差可能提供实际间隙，不能据此认定碰撞，也不能据此宣布无干涉。原版STEP有帽和键帽几何，但果云排母高度、摇杆支点对打印帽的位置和屏幕总装高度尚未核准，需完成全行程、按压及键帽按下的三维/实物检查。控制器件不因此改位。',
        '', 'U1/U2下方原安装孔的螺钉头与模块背面也需按实际排母高度检查。屏幕本体和背板、外壳、USB插头、线缆弯曲空间尚未完成三维核对。',
        '', '原版摇杆规格：YTL YA13S-L7.4-B10Ka(60)-0-DL01；厂家机械图通过立创数据手册获取：https://www.lcsc.com/datasheet/C37323748.pdf',
        '', '固定螺丝头选型限外径不超过6mm，螺丝头高度、实际型号及排母实际宽度仍待核准；H3孔保留原位，J1由A2的Y32.6改为Y31.0mm。屏幕插头与上侧ESP32排母、下侧H3螺丝头同时留有约0.54/0.56mm平面余量，不能再套用A2的2.14mm上侧间隙。两层螺丝头周围3.5mm半径内禁止走线、过孔和铺铜。',
        '', '结论：规定包络内的新增模块平面间距通过；整机无干涉及制造放行仍待核实。','']
    (out/'mechanical-audit.md').write_text('\n'.join(lines))
    print(f'PASS: {len(checks)} dimensioned XY gaps, including screw heads; Z/sweep remain unverified.')


if __name__=='__main__':main()
