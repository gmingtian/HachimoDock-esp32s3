"""Build the offline A4 Gomoku component; no firmware or builtin inventory changes."""
from pathlib import Path
import hashlib
import json
import struct
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'pc/local-clawpkgs/gomoku-a4'
OUT = ROOT / 'artifacts/gomoku-a4'


def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def board_png():
    # One native LCD pixel per source pixel. Lines match the C engine's centers.
    width = height = 220
    pixels = bytearray(width * height)
    def put(x, y, value):
        if 0 <= x < width and 0 <= y < height:
            pixels[y * width + x] = value
    for i in range(15):
        pos = 12 + i * 14
        for p in range(12, 209):
            put(pos, p, 1)
            put(p, pos, 1)
    for col, row in [(3, 3), (3, 11), (7, 7), (11, 3), (11, 11)]:
        cx, cy = 12 + col * 14, 12 + row * 14
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                if dx * dx + dy * dy <= 4:
                    put(cx + dx, cy + dy, 1)
    for p in range(width):
        put(p, 0, 2); put(p, 219, 2); put(0, p, 2); put(219, p, 2)
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    raw = b''.join(b'\0' + pixels[y * width:(y + 1) * width] for y in range(height))
    palette = bytes([225, 188, 132, 109, 79, 44, 172, 130, 78])
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 3, 0, 0, 0))
            + chunk(b'PLTE', palette) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def build():
    PACKAGE.mkdir(parents=True, exist_ok=True)
    (PACKAGE / 'runtime').mkdir(exist_ok=True)
    (PACKAGE / 'assets').mkdir(exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    description = '离线人机五子棋：15×15 无禁手，你执黑先行。摇杆选点，1键开始/落子/重开，2键悔棋，3键退出。'
    actions = {k: 'gomoku.' + k for k in ['place', 'left', 'right', 'up', 'down', 'undo']}
    buttons = [dict(action=actions[k], control=c, event=e, label=l) for k, c, e, l in [
        ('place', 'SW1', 'button.sw1.short_press', '开始/落子/重开'),
        ('undo', 'SW2', 'button.sw2.short_press', '悔棋一步'),
        ('left', '前方摇杆', 'knob.rotate_ccw', '向左'),
        ('right', '前方摇杆', 'knob.rotate_cw', '向右'),
        ('up', '前方摇杆', 'joystick.up', '向上'),
        ('down', '前方摇杆', 'joystick.down', '向下'),
    ]]
    dashboard = dict(title='五子棋', eyebrow='黑先 · 无禁手',
        headline={'switch_state': {'ready': '主键开始', 'playing': '人机对弈', 'result': {'var': 'outcome'}}},
        metricLabel='落子数', metricValue={'var': 'score'}, metricUnit='', badge='',
        note={'switch_state': {'ready': '黑棋先行', 'playing': '红点为末手', 'result': '主键重开'}},
        footer='摇杆选点 · 1键落子 · 2键悔棋 · 3键退出',
        visualStyle='clean', visualPalette='sunset', visualLayout='arcade')
    ink, muted, cream = rgb565(56, 43, 30), rgb565(115, 91, 63), rgb565(250, 243, 226)
    def text(y, *, value=None, bind=None, size=26, color=ink, x=460, w=168):
        n = dict(type='text', x=x, y=y, w=w, h=(size * 5 + 3) // 4, color=color, font_size=size)
        n.update({'bind': bind} if bind else {'text': value})
        return n
    elements = [
        dict(type='image', x=4, y=4, w=440, h=440, color=0, image='board'),
        text(16, bind='title', size=34),
        text(68, bind='headline', size=28),
        text(108, bind='note', size=24, color=muted),
        dict(type='panel', x=460, y=169, w=20, h=20, radius=10, color=rgb565(28, 28, 34)),
        text(160, value='黑棋 · 你', x=492, w=140),
        dict(type='panel', x=460, y=211, w=20, h=20, radius=10, color=rgb565(255, 255, 255), stroke=muted, stroke_width=2),
        text(202, value='白棋 · 设备', x=492, w=140),
        text(272, value='摇杆选点'),
        text(312, value='1键落子'),
        text(352, value='2键悔棋'),
        text(402, value='3键退出', size=24, color=muted),
        text(448, value='15×15 · 连五或以上胜 · 无禁手', size=24, x=12, w=620, color=muted),
    ]
    runtime = dict(schema_version=1, engine='p4-bounded-runtime-v4', logic='p4-logic-v1',
        vars={'score': {'type': 'int', 'init': 0}, 'outcome': {'type': 'string', 'init': '本局结束'}},
        states=['ready', 'playing', 'result'], initial_state='ready',
        transitions=[dict(**{'from': s}, on=actions['place'], to='playing', set={'score': 0, 'outcome': '本局结束'}) for s in ['ready', 'result']]
            + [dict(**{'from': 'playing'}, on=a) for a in actions.values()],
        tick=[dict(every_ms=100, while_state='result', when=c, then={'set': {'outcome': label}}) for c, label in [
            ({'var': 'score', 'op': 'lt', 'value': 2000}, '黑棋获胜'),
            ({'all': [{'var': 'score', 'op': 'gte', 'value': 2000}, {'var': 'score', 'op': 'lt', 'value': 3000}]}, '白棋获胜'),
            ({'var': 'score', 'op': 'gte', 'value': 3000}, '棋盘已满'),
        ]],
        game=dict(type='gomoku', tick_ms=300, playing_state='playing', result_state='result', score_var='score', actions=actions),
        dashboard=dashboard,
        surface=dict(engine='p4-app-surface-v1', graphics='p4-app-graphics-v1', background=cream,
            game_view=dict(engine='p4-game-surface-v1', x=14, y=14, w=420, h=420),
            images=[dict(id='board', asset='assets/board.png', frame_width=220, frame_height=220, frames=1, fps=1)], elements=elements),
        input=dict(engine='p4-input-v1', repeat=[actions[k] for k in ['left', 'right', 'up', 'down']]))
    files = {
        'component.json': dict(id='gomoku-a4', name='五子棋', kind='game', version='1.0.0', author='本地制作', description=description),
        'buttons.json': buttons,
        'negative-screen.json': {'dashboard': {**dashboard, 'headline': '主键开始', 'metricValue': '0', 'note': '黑棋先行'}},
        'share.json': dict(title='五子棋', summary=description),
        'runtime/widget.json': runtime,
    }
    for name, data in files.items():
        (PACKAGE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (PACKAGE / 'assets/board.png').write_bytes(board_png())
    artifact = OUT / 'gomoku-a4-1.0.0.clawpkg'
    with zipfile.ZipFile(artifact, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PACKAGE.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(PACKAGE).as_posix())
    receipt = dict(id='gomoku-a4', version='1.0.0', bytes=artifact.stat().st_size,
        sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        widgetCompactBytes=len(json.dumps(runtime, ensure_ascii=False, separators=(',', ':')).encode()),
        files={p.relative_to(PACKAGE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(PACKAGE.rglob('*')) if p.is_file()})
    (OUT / 'build-receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    build()
