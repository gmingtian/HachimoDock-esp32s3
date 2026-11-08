"""Read-only baseline or explicit, bounded Gomoku acceptance on a chosen device."""
import argparse
import json
from pathlib import Path
import time
import serial

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/gomoku-a4'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('mode', choices=('before', 'verify'))
parser.add_argument('--port', required=True, help='Explicit serial port of the authorized device')
parser.add_argument('--board', required=True, help='Expected HELLO boardDeviceId; no auto-selection')
args = parser.parse_args()
MODE = args.mode
BOARD = args.board.strip()
assert BOARD and args.port.strip(), 'explicit, nonempty board and port are required'
messages = []
connection = serial.Serial(port=None, baudrate=4000000, timeout=.12, write_timeout=4)
connection.dtr = False
connection.rts = False
connection.port = args.port
connection.open()
sequence = 0


def read():
    try:
        value = json.loads(connection.readline())
    except (ValueError, UnicodeDecodeError):
        return None
    if isinstance(value, dict):
        messages.append(value)
        return value


def request(topic, data=None, response=None):
    global sequence
    sequence += 1
    request_id = f'gomoku-{MODE}-{sequence}'
    connection.write((json.dumps({'topic': topic, 'payload': {**(data or {}), 'requestId': request_id}}) + '\n').encode())
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        m = read()
        if not m:
            continue
        p = m.get('payload', {})
        if p.get('requestId') != request_id:
            continue
        if m.get('topic') == 'protocol/ack':
            assert p.get('ok') is True, (topic, p)
            if response is None:
                return p
        if m.get('topic') == response:
            return p
    raise TimeoutError((topic, request_id))


def state():
    return request('miniapp/query', response='miniapp/state')


def action(name):
    request('miniapp/event', {'action': name})


try:
    connection.write(b'\n{"type":"hello"}\n')
    deadline = time.monotonic() + 8
    hello = None
    while time.monotonic() < deadline:
        m = read()
        if m and m.get('topic') == 'hello':
            hello = m['payload']
            break
    assert hello and hello['boardDeviceId'] == BOARD
    assert hello['runtime'] == 'esp-s3'
    assert hello['fw'] == '0.7.103-s3-r15-80m-l320'
    inventory = request('widget/list', response='widget/inventory')
    diagnostics = request('diagnostics/query', response='diagnostics/status')
    firmware = request('firmware/query', response='firmware/status')
    inputs = request('input/config-query', response='input/config-state')
    assert inventory['boardDeviceId'] == BOARD and diagnostics['boardDeviceId'] == BOARD
    assert firmware['runtimeReady'] and not firmware['pendingVerify']
    assert inputs['config']['inputModel'] == 's3-a4-buttons-joystick-v1' and inputs['bindingCount'] == 16
    checks = []
    if MODE == 'verify':
        baseline = json.loads((OUT / 'device-before.json').read_text(encoding='utf-8'))
        assert baseline['hello']['boardDeviceId'] == BOARD, 'baseline must belong to the authorized board'
        assert inputs['config'] == baseline['inputs']['config'], 'hardware mapping preserved'
        assert diagnostics['faultResetCount'] == baseline['diagnostics']['faultResetCount']
        request('widget/activate', {'widgetId': 'gomoku-a4', 'show': True})
        time.sleep(1.5)
        s = state()
        assert (s['widgetId'], s['state'], s['gameType'], s['gameGridWidth'], s['gameGridHeight']) == ('gomoku-a4', 'ready', 'gomoku', 15, 15), s
        checks.append({'case': 'ready', 'state': s})
        action('gomoku.place')
        assert state()['gameScore'] == 0
        action('gomoku.place')
        time.sleep(.55)
        assert state()['gameScore'] == 2, 'human and AI opening'
        action('gomoku.place')  # occupied point must keep the stone count
        assert state()['gameScore'] == 2
        action('gomoku.undo')
        assert state()['gameScore'] == 0
        for name in ['left', 'right', 'up', 'down']:
            action('gomoku.' + name)
        checks.append({'case': 'opening-direction-occupied-undo', 'state': state()})
        plan = json.loads((OUT / 'match-plan.json').read_text(encoding='utf-8'))
        for index, round_ in enumerate(plan['rounds']):
            for name in round_['actions']:
                action(name)
            time.sleep(.55)
            s = state()
            assert s['gameScore'] == round_['score'], (index, s)
            assert s['gameOver'] == round_['over'], (index, s)
            checks.append({'case': f'match-round-{index + 1}', 'state': s})
        time.sleep(.2)
        s = state()
        assert s['state'] == 'result' and s['headline'] == '白棋获胜', s
        action('gomoku.place')
        s = state()
        assert s['state'] == 'playing' and s['gameScore'] == 0 and not s['gameOver']
        checks.append({'case': 'restart-empty', 'state': s})
        for _ in range(5):
            request('control/screen-page', {'page': 'main'})
            time.sleep(1.5)
            d = request('diagnostics/query', response='diagnostics/status')
            stages = d['runtime']['renderStages']
            assert d['runtime']['screenPage'] == 'main' and stages['nativeComposition'] and stages['nativeAssetReady'], d
            request('widget/activate', {'widgetId': 'gomoku-a4', 'show': True})
            time.sleep(1)
            assert state()['widgetId'] == 'gomoku-a4'
        # Leave a clean ready board for the user's first physical play.
        request('widget/activate', {'widgetId': 'gomoku-a4', 'show': True})
        time.sleep(1)
        s = state()
        assert (s['widgetId'], s['state'], s['gameScore'], s['gameOver']) == ('gomoku-a4', 'ready', 0, False), s
        checks.append({'case': 'final-ready', 'state': s})
        diagnostics = request('diagnostics/query', response='diagnostics/status')
        assert diagnostics['faultResetCount'] == baseline['diagnostics']['faultResetCount']
        assert diagnostics['bootCount'] == baseline['diagnostics']['bootCount']
        assert diagnostics['runtime']['inputDroppedEvents'] == 0
    record = dict(hello=hello, inventory=inventory, diagnostics=diagnostics, firmware=firmware, inputs=inputs, checks=checks)
    (OUT / f'device-{MODE}.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'mode': MODE, 'firmware': firmware['version'], 'components': len(inventory['items']),
        'faultResetCount': diagnostics['faultResetCount'], 'checks': len(checks)}, ensure_ascii=True))
finally:
    connection.close()
    (OUT / f'protocol-{MODE}.json').write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding='utf-8')
