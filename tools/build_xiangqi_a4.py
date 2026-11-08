"""Build the offline A4 Xiangqi package without changing firmware or builtins."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'pc/local-clawpkgs/xiangqi-a4'
OUT = ROOT / 'artifacts/xiangqi-a4'


def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def board_png():
    # Pixel centers agree with game_view's 44-logical-pixel cells at 1:2 scale.
    width, height = 198, 220
    pixels = bytearray(width * height)

    def put(x, y, tone=1):
        if 0 <= x < width and 0 <= y < height:
            pixels[y * width + x] = tone

    def line(x0, y0, x1, y1):
        steps = max(abs(x1-x0), abs(y1-y0))
        for k in range(steps+1):
            put(x0+(x1-x0)*k//steps, y0+(y1-y0)*k//steps)

    for row in range(10):
        line(11, 11+row*22, 187, 11+row*22)
    for col in range(9):
        x = 11+col*22
        line(x, 11, x, 99)
        line(x, 121, x, 209)
    line(11, 99, 11, 121)
    line(187, 99, 187, 121)
    for y in (11, 165):
        line(77, y, 121, y+44)
        line(121, y, 77, y+44)
    for col, row in [(1, 2), (7, 2), (1, 7), (7, 7)]+[(x, y) for y in (3, 6) for x in (0, 2, 4, 6, 8)]:
        x, y = 11+col*22, 11+row*22
        for side in (-1, 1):
            if col+side < 0 or col+side > 8:
                continue
            for vertical in (-1, 1):
                for d in range(3, 7):
                    put(x+side*3, y+vertical*d)
                    put(x+side*d, y+vertical*3)
    for x in range(width):
        put(x, 0, 2)
        put(x, height-1, 2)
    for y in range(height):
        put(0, y, 2)
        put(width-1, y, 2)

    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data))
    raw = b''.join(b'\0'+pixels[y*width:(y+1)*width] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 3, 0, 0, 0))
            + chunk(b'PLTE', bytes([234, 205, 157, 123, 89, 51, 185, 144, 88]))
            + chunk(b'IDAT', zlib.compress(raw, 9))+chunk(b'IEND', b''))


def build(package_only=False):
    (PACKAGE / 'runtime').mkdir(parents=True, exist_ok=True)
    (PACKAGE / 'assets').mkdir(exist_ok=True)
    description = ('离线人机中国象棋，红方先行，简单、普通、困难三档。摇杆选点；选棋后所有棋种均显示合法落点，青绿亮点可走、橙红圈可吃，摇杆快速切换落点。'
                   '1键开始/选棋/落子/重开，2键取消选中、未选中时撤回最近一轮，仅一级悔棋，3键退出。'
                   '按中国象棋走法、将军与将死/困毙判胜；休闲版不含竞赛级长将长捉裁定。退出后重新开局，不保存棋局。需要支持 xiangqi 原生预设的固件。')
    actions = {k: 'xiangqi.'+k for k in ('place', 'left', 'right', 'up', 'down', 'undo')}
    buttons = [dict(action=actions[k], control=c, event=e, label=label) for k, c, e, label in (
        ('place', 'SW1', 'button.sw1.short_press', '开始/选棋/落子/重开'),
        ('undo', 'SW2', 'button.sw2.short_press', '取消选中/一级悔棋'),
        ('left', '前方摇杆', 'knob.rotate_ccw', '向左/切换落点'),
        ('right', '前方摇杆', 'knob.rotate_cw', '向右/切换落点'),
        ('up', '前方摇杆', 'joystick.up', '向上/选难度/切点'),
        ('down', '前方摇杆', 'joystick.down', '向下/选难度/切点'),
    )]
    ink, muted, red = rgb565(60, 46, 32), rgb565(122, 98, 68), rgb565(180, 50, 46)

    def text(y, value, size=26, color=ink, show=None, x=424, w=204):
        node = dict(type='text', x=x, y=y, w=w, h=(size*5+3)//4,
                    color=color, font_size=size, line_height=(size*5+3)//4, text=value)
        if show:
            node['show'] = dict(var=show[0], min=show[1], max=show[1])
        return node

    elements = [dict(type='image', x=8, y=8, w=396, h=440, color=0, image='board'),
                text(16, '中国象棋', 34), text(72, '对手难度', 24, muted)]
    elements += [text(108, value, 30, red, ('level', i)) for i, value in enumerate(('简单', '普通', '困难'))]
    elements += [text(164, value, 28, red if i in (4, 5, 7) else ink, ('phase', i)) for i, value in enumerate(
        ('1键开始', '红方走棋', '请选择落点', '设备思考中', '你被将军', '此处不可走', '红方获胜', '设备获胜', '本局和棋'))]
    elements += [text(224, '亮点可走', 26, rgb565(37, 135, 121)),
                 text(258, '红圈可吃', 26, rgb565(223, 100, 61)),
                 text(306, '摇杆切换落点', 24), text(340, '1键确认', 26),
                 text(374, '2键取消/悔棋', 24), text(408, '3键退出', 24, muted),
                 text(450, '开局前上下选难度 · 红方先行 · 休闲规则', 24, muted, x=12, w=620)]
    dashboard = dict(title='中国象棋', eyebrow='红方先行 · 离线人机', headline={'switch_state': {'ready': '1键开始', 'playing': '人机对弈', 'result': '1键重开'}},
                     metricLabel='对手', metricValue='普通', metricUnit='', badge='',
                     note='亮点可走 · 红圈可吃', footer='摇杆选点 · 1键确认 · 2键取消/悔棋 · 3键退出',
                     visualStyle='clean', visualPalette='sunset', visualLayout='arcade', visualSprite='target')
    runtime = dict(schema_version=1, engine='p4-bounded-runtime-v4', logic='p4-logic-v1',
                   vars={'ui': {'type': 'int', 'init': 16}, 'level': {'type': 'int', 'init': 1}, 'phase': {'type': 'int', 'init': 0}},
                   states=['ready', 'playing', 'result'], initial_state='ready',
                   transitions=[{'from': '*', 'on': a} for a in actions.values()], tick=[],
                   game=dict(type='xiangqi', tick_ms=100, playing_state='playing', result_state='result', score_var='ui',
                             difficulty_var='level', status_var='phase', actions=actions), dashboard=dashboard,
                   surface=dict(engine='p4-app-surface-v1', graphics='p4-app-graphics-v1', bindings='p4-variable-bindings-v1',
                                typography='p4-app-type-v1', interaction='p4-app-interaction-v1', background=rgb565(250, 243, 226),
                                game_view=dict(engine='p4-game-surface-v1', x=8, y=8, w=396, h=440),
                                images=[dict(id='board', asset='assets/board.png', frame_width=198, frame_height=220, frames=1, fps=1)], elements=elements),
                   input=dict(engine='p4-input-v1', repeat=[actions[k] for k in ('left', 'right', 'up', 'down')]))
    files = {'component.json': dict(id='xiangqi-a4', name='中国象棋', kind='game', version='1.0.0', author='gaomt', description=description),
             'buttons.json': buttons, 'runtime/widget.json': runtime,
             'negative-screen.json': {'dashboard': {**dashboard, 'headline': '1键开始'}},
             'share.json': dict(title='中国象棋', summary=description)}
    for name, data in files.items():
        (PACKAGE/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (PACKAGE/'assets/board.png').write_bytes(board_png())
    if package_only:
        print(json.dumps(dict(id='xiangqi-a4', widgetCompactBytes=len(json.dumps(runtime, ensure_ascii=False, separators=(',', ':')).encode()), nodes=len(elements))))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    artifact = OUT/'xiangqi-a4-1.0.0.clawpkg'
    with zipfile.ZipFile(artifact, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(PACKAGE).as_posix())
    receipt = dict(id='xiangqi-a4', version='1.0.0', bytes=artifact.stat().st_size,
                   sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
                   widgetCompactBytes=len(json.dumps(runtime, ensure_ascii=False, separators=(',', ':')).encode()),
                   files={p.relative_to(PACKAGE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(PACKAGE.rglob('*')) if p.is_file()})
    (OUT/'build-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package-only', action='store_true')
    build(parser.parse_args().package_only)
