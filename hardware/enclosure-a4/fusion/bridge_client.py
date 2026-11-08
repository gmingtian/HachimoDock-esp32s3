"""Local file-queue client; CAD work executes inside the running Fusion add-in."""
import json
import os
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def call(op, _retry=True, **args):
    status = json.loads((ROOT / 'io/status.json').read_text(encoding='utf-8'))
    if not status.get('running'):
        raise RuntimeError('Fusion bridge is stopped')
    request_id = uuid.uuid4().hex
    request = dict(id=request_id, session_id=status['session_id'], op=op, args=args)
    temporary = ROOT / 'io/request.tmp'
    temporary.write_text(json.dumps(request), encoding='utf-8')
    os.replace(temporary, ROOT / 'io/request.json')
    response_path = ROOT / 'io/responses' / (request_id + '.json')
    deadline = time.monotonic() + 55
    while not response_path.exists():
        if time.monotonic() > deadline:
            raise TimeoutError(f'Fusion did not answer {op}: {request_id}')
        time.sleep(.15)
    response = json.loads(response_path.read_text(encoding='utf-8'))
    if not response.get('ok'):
        if _retry and response.get('error','').startswith('Fusion is busy'):
            info=call('ping')
            if info.get('active_command')=='OrbitCommand':
                call('ping',end_orbit=True)
                time.sleep(.6)
                return call(op,_retry=False,**args)
        raise RuntimeError(json.dumps(response, ensure_ascii=False))
    return response['result']

if __name__ == '__main__':
    import sys
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(json.dumps(call(sys.argv[1], **args), ensure_ascii=False, indent=2))
