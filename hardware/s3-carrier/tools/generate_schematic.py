"""Generate a module-level A4 schematic without modifying the reviewed PCB.

Symbols describe the carrier interfaces, not circuitry inside purchased modules.
Named wires keep all nine interfaces readable on one A3 sheet. A native KiCad
netlist export must be compared with the independently audited physical pads.
"""
import hashlib
import json
from pathlib import Path
import uuid

from build_design import ROOT, STEM
from source_geometry import read_archive, symbol_pins

OUT = ROOT / 'output'
SHEET = str(uuid.uuid5(uuid.NAMESPACE_URL, 'hachimodock/s3/a4/schematic'))


def uid(name):
    return str(uuid.uuid5(uuid.UUID(SHEET), name))


def q(value):
    return json.dumps(str(value), ensure_ascii=False)


def effects(size=1.27, justify='', hide=False, chinese=False):
    face = '(face "Noto Sans CJK SC") ' if chinese else ''
    return (f'(effects (font {face}(size {size} {size}))'
            + (f' (justify {justify})' if justify else '')
            + (' (hide yes)' if hide else '') + ')')


def property_(name, value, x, y, hide=False):
    return f'(property {q(name)} {q(value)} (at {x} {y} 0) {effects(hide=hide)})'


def make_symbol(ref, pins, width, height, switch=False, library=False):
    name = ref if library else 'S3_Carrier:' + ref
    pin_names = '(pin_names (offset 0.762) (hide yes))' if switch else '(pin_names (offset 0.762))'
    parts = [f'(symbol {q(name)} {pin_names}',
             '(exclude_from_sim no) (in_bom yes) (on_board yes)',
             property_('Reference', ref.rstrip('0123456789'), 0, height / 2 + 5.08),
             property_('Value', ref, 0, height / 2 + 2.54)]
    if switch:
        graphic = ('(polyline (pts (xy -2.54 0) (xy 2.54 2.54))'
                   ' (stroke (width 0.254) (type default)) (fill (type none)))'
                   '(circle (center -2.54 0) (radius 0.508)'
                   ' (stroke (width 0.254) (type default)) (fill (type none)))'
                   '(circle (center 2.54 0) (radius 0.508)'
                   ' (stroke (width 0.254) (type default)) (fill (type none)))')
    else:
        graphic = (f'(rectangle (start {-width/2} {height/2}) (end {width/2} {-height/2})'
                   ' (stroke (width 0.254) (type default)) (fill (type background)))')
    parts.append(f'(symbol {q(ref+"_0_1")} {graphic})')
    parts.append(f'(symbol {q(ref+"_1_1")}')
    for p in pins:
        parts.append(f'(pin {p["type"]} line (at {p["x"]} {p["y"]} {p["angle"]})'
                     f' (length {p["length"]}) (name {q(p["name"])} {effects(1.016)})'
                     f' (number {q(p["number"])} {effects(1.016)}))')
    parts.extend([')', ')'])
    return '\n'.join(parts)


def main():
    board = OUT / f'{STEM}.kicad_pcb'
    before = hashlib.sha256(board.read_bytes()).hexdigest()
    design = json.loads((OUT / 'design.json').read_text())
    reference = read_archive(ROOT / 'reference/goouuu-reference-carrier.epro2')
    u1names = symbol_pins(reference['dec5ecc4336c40cd976d9e8e08c16bd8'])
    names = {
        'U1': u1names,
        'J1': dict(zip(map(str, range(1, 9)), ['GND', 'VCC_3V3', 'SCL_CLK', 'SDA_MOSI', 'RES', 'DC', 'CS', 'BLK'])),
        'U2': dict(zip(map(str, range(1, 8)), ['VIN_3V3', 'GND', 'SD_EN', 'GAIN', 'DIN', 'BCLK', 'LRC'])),
        'U3': {'1': 'GND', '2': 'VDD_3V3', '3': 'SD_OUT', '4': 'LR_GND', '5': 'WS', '6': 'SCK'},
        'JP1': {'1': '3V3_6dB', '2': 'GAIN', '3': 'GND_12dB'},
        'JS1': {'A1': 'AXIS_A+', 'A2': 'AXIS_A_WIPER', 'A3': 'AXIS_A-',
                'B1': 'AXIS_B-', 'B2': 'AXIS_B_WIPER', 'B3': 'AXIS_B+',
                'A': 'PUSH_GND_A', 'B': 'PUSH_GPIO8_B',
                'C': 'PUSH_GND_C', 'D': 'PUSH_GPIO8_D', '0': 'CASE_4_TABS'},
    }
    values = {'U1': 'GOOUUU ESP32-S3 N16R8 / 42P', 'U2': 'MAX98357A MODULE',
              'U3': 'INMP441 ROUND MODULE', 'J1': 'LCD / 8P / 2.54mm',
              'JP1': 'GAIN SELECT / 3P', 'JS1': 'YA13S / GPIO RESERVED',
              'SW1': 'PREVIOUS / GPIO39', 'SW2': 'NEXT / GPIO38', 'SW3': 'CONFIRM / GPIO0'}
    positions = {'U1': (78.74, 114.3, 45.72, 111.76),
                 'J1': (185.42, 81.28, 35.56, 45.72),
                 'U2': (284.48, 81.28, 35.56, 40.64),
                 'U3': (185.42, 160.02, 35.56, 35.56),
                 'JP1': (284.48, 154.94, 35.56, 20.32),
                 'JS1': (373.38, 157.48, 40.64, 60.96),
                 'SW1': (175.26, 223.52, 5.08, 0),
                 'SW2': (256.54, 223.52, 5.08, 0),
                 'SW3': (337.82, 223.52, 5.08, 0)}
    definitions, instances, connections, library = [], [], [], []
    for c in design['components']:
        ref = c['ref']; x, y, width, height = positions[ref]
        # A single symbol pin 0 represents four electrically common shell pads.
        unique = {p['number']: p for p in c['pads']}
        order = list(unique)
        if ref == 'U1': order = list(map(str, range(1, 43)))
        elif ref == 'JS1': order = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'A', 'B', 'C', 'D', '0']
        elif not ref.startswith('SW'): order = sorted(unique, key=int)
        pins = []
        for i, number in enumerate(order):
            pin = unique[number]; right = ref == 'U1' and i >= 21 or ref.startswith('SW') and i == 1
            row = i % 21 if ref == 'U1' else i
            count = 21 if ref == 'U1' else len(order)
            py = round(((count - 1) / 2 - row) * 5.08, 5)
            if ref.startswith('SW'): py = 0
            px = width / 2 + (6.35 if ref.startswith('SW') else 5.08)
            px = px if right else -px
            name = names.get(ref, {}).get(number, 'CONTACT')
            kind = 'passive'
            if ref == 'U1':
                if number in ('1', '2', '42'): kind = 'power_out'  # Onboard USB/regulator supply.
                elif number not in ('21', '22'): kind = 'bidirectional'
            elif ref == 'U2': kind = 'power_in' if number in ('1', '2') else 'input'
            elif ref == 'U3': kind = 'output' if number == '3' else ('power_in' if number in ('1', '2') else 'input')
            p = dict(number=number, name=name, x=px, y=py, angle=180 if right else 0,
                     length=6.35 if ref.startswith('SW') else 5.08, type=kind)
            pins.append(p)
            wx, wy = round(x + px, 5), round(y - py, 5)
            net = pin['net']
            if not net:
                connections.append(f'(no_connect (at {wx} {wy}) (uuid {uid(ref+"/NC/"+number)}))')
                continue
            end = round(wx + (10.16 if right else -10.16), 5)
            connections.append(f'(wire (pts (xy {wx} {wy}) (xy {end} {wy}))'
                               f' (stroke (width 0) (type default)) (uuid {uid(ref+"/wire/"+number)}))')
            justify = 'left bottom' if right else 'right bottom'
            if not (ref == 'U1' and number == '42'):
                connections.append(f'(label {q(net)} (at {end} {wy} 0) {effects(1.016,justify)}'
                                   f' (uuid {uid(ref+"/label/"+number)}))')
        switch = ref.startswith('SW')
        definitions.append(make_symbol(ref, pins, width, height, switch))
        library.append(make_symbol(ref, pins, width, height, switch, True))
        instance = [f'(symbol (lib_id {q("S3_Carrier:"+ref)}) (at {x} {y} 0) (unit 1)',
                    '(in_bom yes) (on_board yes) (dnp no)', f'(uuid {uid("symbol/"+ref)})',
                    property_('Reference', ref, x, y - height / 2 - 6.35),
                    property_('Value', values[ref], x, y - height / 2 - 2.54),
                    property_('Footprint', 'S3_Carrier:' + ref, x, y, True)]
        for p in pins: instance.append(f'(pin {q(p["number"])} (uuid {uid(ref+"/pin/"+p["number"])}))')
        instance.append(f'(instances (project {q(STEM)} (path "/{SHEET}" (reference {q(ref)}) (unit 1)))))')
        instances.append('\n'.join(instance))
    # A power port documents the devkit's USB-derived 5V pin. This is an
    # annotation symbol, not an added physical carrier component.
    power_definition = ('(power) (pin_names (offset 0) (hide yes)) (pin_numbers (hide yes))'
        ' (in_bom no) (on_board no)'
        ' (property "Reference" "#PWR" (at 0 -2.54 0) (effects (font (size 1.27 1.27)) (hide yes)))'
        ' (property "Value" "+5V" (at 0 2.54 0) (effects (font (size 1.27 1.27))))'
        ' (symbol "VUSB_0_1" (polyline (pts (xy -1.27 0) (xy 0 1.27) (xy 1.27 0))'
        ' (stroke (width 0.254) (type default)) (fill (type none))))'
        ' (symbol "VUSB_1_1" (pin power_in line (at 0 0 90) (length 0)'
        ' (name "+5V" (effects (font (size 1.27 1.27))))'
        ' (number "1" (effects (font (size 1.27 1.27))))))')
    definitions.append('(symbol "S3_Carrier:VUSB" '+power_definition+')')
    library.append('(symbol "VUSB" '+power_definition+')')
    # U1.42: last right-side row, wire endpoint (116.84,165.1).
    instances.append(f'(symbol (lib_id "S3_Carrier:VUSB") (at 116.84 165.1 0) (unit 1)'
        f' (in_bom no) (on_board no) (dnp no) (uuid {uid("symbol/VUSB")})'
        +property_('Reference','#PWR01',116.84,167.64,True)
        +property_('Value','+5V',116.84,161.29)
        +f' (pin "1" (uuid {uid("VUSB/pin")}))'
        +f' (instances (project {q(STEM)} (path "/{SHEET}" (reference "#PWR01") (unit 1)))))')
    text = []

    def note(message, x, y, size=1.27, chinese=False):
        text.append(f'(text {q(message)} (at {x} {y} 0) {effects(size,"left top",chinese=chinese)}'
                    f' (uuid {uid("text/"+message)}))')

    note('HachimoDock S3 - A4 模块连接原理图', 20.32, 15.24, 2.54, True)
    note('与现有 PCB 对照；不是模块内部芯片原理图。相同网络标签表示电气相连。', 20.32, 23.495, 1.52, True)
    note('01  果云开发板与底板排母', 20.32, 40.64, 1.52, True)
    note('02  屏幕接口', 152.4, 40.64, 1.52, True)
    note('03  功放模块', 251.46, 40.64, 1.52, True)
    note('屏幕从 J1 接出：GND / VCC / SCL / SDA / RES / DC / CS / BLK', 150, 114.3, 1.016, True)
    note('VIN = 3V3；SD = 3V3。', 251.46, 107.95, 1.27, True)
    note('喇叭只接模块 SPK+ / SPK-；SPK- 不接 GND。', 251.46, 113.03, 1.016, True)
    note('04  数字麦克风', 152.4, 129.54, 1.52, True)
    note('05  增益跳线', 251.46, 129.54, 1.52, True)
    note('06  摇杆预留', 340.36, 109.22, 1.52, True)
    note('L/R 接地，使用左声道；供电 3V3。', 152.4, 187.96, 1.016, True)
    note('只装一个跳线帽，断电切换。', 251.46, 172.72, 1.016, True)
    note('1-2 = 6dB / OPEN = 9dB / 2-3 = 12dB', 251.46, 178.435, 1.016)
    note('GPIO1 / GPIO2 / GPIO8：当前固件尚未启用。', 322.58, 195.58, 1.016, True)
    note('07  三个按键：按下接地，使用芯片内部上拉', 152.4, 205.74, 1.52, True)
    note('供电由开发板板载 USB / 稳压电路提供；没有电池或充电电路。', 20.32, 190.5, 1.016, True)
    note('原生 USB GPIO19/20 不接底板外设；叉号表示本底板不使用该引脚。', 20.32, 197.485, 1.016, True)
    note('摇杆金属外壳 4 个固定焊脚均为 JS1.0，接 GND。', 20.32, 204.47, 1.016, True)
    note('GPIO0 上电 / 复位时松开；LCD BLK 直接连接 GPIO42。', 20.32, 211.455, 1.016, True)
    note('工程样板：供电余量、背光电流、声学效果与整机装配尚未完成实物验证。', 20.32, 248.92, 1.27, True)
    note('此图按已审核 A4 PCB 反向整理；未修改 PCB / Gerber，未重建自动更新 PCB 的 UUID 链接。', 20.32, 256.54, 1.016, True)
    header = (f'(kicad_sch (version 20250114) (generator "hachimo_carrier")'
              f' (uuid {SHEET}) (paper "A3")'
              ' (title_block (title "HachimoDock S3 A4 - Carrier Module Connections")'
              ' (date "2026-11-03") (rev "A4")'
              ' (company "gmingtian / based on HachimoDock")'
              ' (comment 1 "Engineering prototype - physical validation pending"))')
    result = '\n'.join([header, '(lib_symbols', *definitions, ')', *connections, *text, *instances, '(embedded_fonts no)', ')'])
    path = OUT / f'{STEM}.kicad_sch'; path.write_text(result + '\n')
    (OUT / 'S3_Carrier.kicad_sym').write_text('\n'.join([
        '(kicad_symbol_lib (version 20220914) (generator "hachimo_carrier")', *library, ')']) + '\n')
    (OUT / 'sym-lib-table').write_text('(sym_lib_table\n (lib (name "S3_Carrier") (type "KiCad")'
        ' (uri "${KIPRJMOD}/S3_Carrier.kicad_sym") (options "") (descr "Carrier module interfaces"))\n)\n')
    assert hashlib.sha256(board.read_bytes()).hexdigest() == before
    print(path)


if __name__ == '__main__':
    main()
