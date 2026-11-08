"""Audit final native PCB pad nets against current S3 code and module pinouts.

Run with KiCad's pcbnew Python module. This checks the PCB that will be shipped,
not only the generator's in-memory net labels. Native DRC is a separate check.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import pcbnew
from build_design import ROOT, STEM, REVISION


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--board',type=Path,default=ROOT/'output'/f'{STEM}.kicad_pcb')
    parser.add_argument('--report',type=Path,default=ROOT/'output/electrical-audit.json')
    args=parser.parse_args()
    repo=ROOT.parents[1]
    files=[repo/'firmware/s3'/name for name in
           ['pet_s3_board.h','pet_s3_audio_codec.h','pet_s3_lcd.inc']]
    files.append(repo/'firmware/main/pet_p4_input.c')
    code={k:int(v) for k,v in re.findall(r'^#define PET_S3_(\w+) (\d+)$',files[0].read_text(),re.M)}
    board=pcbnew.LoadBoard(str(args.board))
    native=[]
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if not pad.GetNumber():continue
            native.append({'ref':fp.GetReference(),'pin':pad.GetNumber(),'net':pad.GetNetname(),
                'x':round(pcbnew.ToMM(pad.GetPosition().x)-100,6),
                'y':round(pcbnew.ToMM(pad.GetPosition().y)-80,6),
                'drill':round(pcbnew.ToMM(pad.GetDrillSize().x),6)})
    assert len(native)==86,'Electrical pad count differs from reviewed layout'
    design=json.loads((ROOT/'output/design.json').read_text())
    # Rounding each serialized anchor/local offset may shift their sum by 1nm;
    # compare at 0.01um rather than failing on that rounding boundary.
    expected=Counter((c['ref'],p['number'],p['net'],round(p['x'],5),round(p['y'],5))
                     for c in design['components'] for p in c['pads'])
    actual=Counter((p['ref'],p['pin'],p['net'],round(p['x'],5),round(p['y'],5)) for p in native)
    # Net-specific checks below produce actionable errors for fault injection.
    positions_match=actual==expected
    grounds=[z for z in board.Zones() if not z.GetIsRuleArea()]
    assert len(grounds)==2 and {z.GetLayer() for z in grounds}=={pcbnew.F_Cu,pcbnew.B_Cu},'Two ground pours required'
    assert all(z.GetNetname()=='GND' and z.IsFilled() and
               z.GetFilledPolysList(z.GetLayer()).OutlineCount()>0 for z in grounds),'Ground pour missing or unfilled'
    assert any(z.GetIsRuleArea() and z.GetDoNotAllowCopperPour() for z in board.Zones()),'Antenna copper keepout missing'
    rows=[]
    # Expected numbered devkit pins and peripheral terminals are explicit,
    # independent of the generator's maps and of the PCB's net labels.
    connections=[('LCD_CLK','39','J1','3'),('LCD_MOSI','38','J1','4'),
        ('LCD_RST','36','J1','5'),('LCD_DC','29','J1','6'),
        ('LCD_CS','28','J1','7'),('LCD_BL','27','J1','8'),
        ('MIC_WS','4','U3','5'),('MIC_BCLK','5','U3','6'),('MIC_DIN','6','U3','3'),
        ('SPEAKER_DOUT','7','U2','5'),('SPEAKER_BCLK','8','U2','6'),('SPEAKER_WS','9','U2','7'),
        ('SW1_GPIO','30','SW1','1'),('SW2_GPIO','31','SW2','1'),('SW3_GPIO','35','SW3','1')]
    for macro,devpin,ref,pin in connections:
        net=f'GPIO{code[macro]}'
        actual=Counter((p['ref'],p['pin']) for p in native if p['net']==net)
        expected=Counter([('U1',devpin),(ref,pin)])
        assert actual==expected,f'{macro}: expected {net} between {expected}; got {actual}'
        rows.append({'codeDefine':'PET_S3_'+macro,'gpio':code[macro],'devkitPin':devpin,
                     'terminal':ref+'.'+pin,'nativePadNetVerified':True})
    power={'+3V3':[('U1','2'),('U1','21'),('U2','1'),('U2','3'),('U3','2'),('J1','2'),('JS1','A1'),('JS1','B3'),('JP1','1')],
           '+5V':[('U1','42')],
           'GND':[('U1','1'),('U1','22'),('U2','2'),('U3','1'),('U3','4'),('J1','1'),
                  ('SW1','2'),('SW2','2'),('SW3','2'),('JS1','A3'),('JS1','B1'),('JP1','3'),
                  ('JS1','A'),('JS1','C')]+[('JS1','0')]*4}
    for net,expected in power.items():
        actual=Counter((p['ref'],p['pin']) for p in native if p['net']==net)
        assert actual==Counter(expected),f'{net} power/ground mapping mismatch: {actual}'
    for net,expected in {'GPIO1':[('U1','23'),('JS1','B2')],
                         'GPIO2':[('U1','24'),('JS1','A2')],
                         'GPIO8':[('U1','12'),('JS1','B'),('JS1','D')]}.items():
        assert Counter((p['ref'],p['pin']) for p in native if p['net']==net)==Counter(expected),net
    assert Counter((p['ref'],p['pin']) for p in native if p['net']=='AMP_GAIN')==Counter([('U2','4'),('JP1','2')]),'GAIN selector mapping mismatch'
    jp={p['pin']:p for p in native if p['ref']=='JP1'}
    assert {pin:p['net'] for pin,p in jp.items()}=={'1':'+3V3','2':'AMP_GAIN','3':'GND'},'GAIN selector pin order mismatch'
    assert all(abs(math.dist((jp[a]['x'],jp[a]['y']),(jp[b]['x'],jp[b]['y']))-2.54)<1e-5
               for a,b in [('1','2'),('2','3')]),'GAIN selector pitch mismatch'
    assert not any(p['net'] in ['SPK+','SPK-'] for p in native),'Speaker terminals must stay off carrier'
    assert not any(p['ref']=='U2' and p['pin'] in ['8','9'] for p in native),'Speaker pads remain'
    for p in native:
        if p['ref'] in ['U1','U2','U3']:
            assert p['drill']>=1.19,f'Socket tail hole too small: {p}'
        if p['ref']=='U1' and p['pin'] in ['13','14','32','33','34']:
            assert p['net']=='','USB or PSRAM pins must not connect to carrier peripherals'
    audio=files[1].read_text();inputs=files[3].read_text();lcd=files[2].read_text()
    assert 'I2S_STD_SLOT_LEFT' in audio,'Recheck INMP441 LR=GND for changed audio slot config'
    assert 'GPIO_PULLUP_ENABLE' in inputs and 'gpio_get_level(buttons[i].gpio) == 0' in inputs,'Recheck key polarity'
    assert 'ADC1_GPIO1_CHANNEL' in inputs and 'ADC1_GPIO2_CHANNEL' in inputs
    assert code['JOYSTICK_X_GPIO']==1 and code['JOYSTICK_Y_GPIO']==2 and code['JOYSTICK_PRESS_GPIO']==8
    assert 'gpio_set_level(PET_S3_LCD_BL,1)' in lcd,'Recheck BL active-high polarity'
    assert positions_match,'Native pad coordinates differ from reviewed design'
    report={'revision':REVISION,'result':'PASS','boardSha256':sha(args.board),'codeSha256':{p.name:sha(p) for p in files},
            'designSha256':sha(ROOT/'output/design.json'),'allNativePadPositionsVerified':True,
            'filledGroundLayers':['F.Cu','B.Cu'],'nativeAntennaKeepoutVerified':True,
            'existingFirmwareSignalsVerified':rows,'powerPadMappingsVerified':power,
            'micChannel':'left; LR grounded','keys':'active-low with firmware internal pull-ups',
            'joystick':'X=GPIO1/B2, Y=GPIO2/A2, press=GPIO8/B+D; official input semantics',
            'amplifierSupply':'3V3; confirmed by user; SD tied to 3V3; GAIN through JP1',
            'gainSelector':{'nativePinOrderVerified':True,'pins':{'1':'+3V3','2':'AMP_GAIN','3':'GND'},
                            'singleShuntModesDb':{'1-2':6,'open':9,'2-3':12},
                            'moduleGainStrappingVerified':False},
            'socketHoles':'U1/U2/U3 finished-hole design diameter 1.2mm',
            'manufacturingReady':False,
            'microphoneMounting':'Label side outward, pre-soldered long pins down; user photo checked',
            'screenConnectorOrder':['GND','VCC','SCL','SDA','RES','DC','CS','BLK'],
            'unverified':['actual socket/module heights','Unvision screen outline and BL current',
                'USB connector face and enclosure alignment','sustained load/thermal and Wi-Fi tests on fabricated PCB'],
            'nativeElectricalPads':native}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    md=[f'# {REVISION} 电气与固件对应核对','',
        '已直接读取最终 KiCad PCB 焊盘，按当前 S3 代码和编号引脚逐项核对；不只检查生成器的网络表。',
        '', '| 代码信号 | GPIO | 果云排母引脚号 | 目标端子 |','|---|---:|---:|---|']
    md += [f'| {r["codeDefine"]} | {r["gpio"]} | {r["devkitPin"]} | {r["terminal"]} |' for r in rows]
    md += ['', '麦克风 L/R 接地匹配当前左声道采集；按键另一端接地匹配内部上拉、低电平按下逻辑。',
        '功放 VIN 保持用户确认的 3V3，SD 接 3V3；GAIN 连接 JP1 中间2脚，1脚接3V3、3脚接GND。I²S模式下单帽1-2为6dB，拔帽为9dB，2-3为12dB（模块自身若有增益电阻需先核实）。喇叭直接接模块端子。',
        'JP1仅使用一个2.54mm跳线帽，断电后切换；禁止同时跨接1-2和2-3，否则短接3V3与GND。不占用GPIO，不新增电阻电容。',
        '摇杆 X=GPIO1（B2）、Y=GPIO2（A2）、按压=GPIO8（B/D），固件启用官方按钮/摇杆操作。',
        '果云使用两条 1×21P 排母；功放 1×7P；圆形麦克风两条 1×3P、排距 7.62mm。模块按元件面安装，不能照背面视图把引脚顺序镜像。',
        '麦克风预焊照片已核对：带字面朝外、长针向下；元件面左列由上到下 SD/3V3/GND，右列 SCK/WS/L/R。',
        '屏幕接口由左到右 GND/VCC/SCL/SDA/RES/DC/CS/BLK，VCC=3V3；与用户屏幕图片同序。',
        '未上电焊接检查：按连接表确认排母每脚与对应端子通断、相邻焊脚无锡桥，3V3 与 GND 无焊接短路。预留 GPIO 和 NC 脚不能当成地线连接。',
        '本次是设计文件审核，不代替打样板的断电通断检查、上电电压测量、负载和温升测试。高度/屏幕/USB 对壳尚未核实，因此没有制造放行。','']
    args.report.with_suffix('.md').write_text('\n'.join(md))
    print(f'PASS: {len(rows)} firmware signal paths, power/ground, socket holes and reserved pins audited from native PCB.')


if __name__=='__main__':main()
