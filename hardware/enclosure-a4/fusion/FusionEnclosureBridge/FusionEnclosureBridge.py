"""Fusion add-in entry point. Start manually in Scripts and Add-Ins."""
import importlib.util
import importlib
import adsk
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
_runtime=None

def run(context):
    global _runtime
    try:
        if _runtime is not None:_runtime.stop()
        import bridge_runtime
        importlib.reload(bridge_runtime)
        _runtime=bridge_runtime.BridgeRuntime(HERE)
        _runtime.start()
        adsk.autoTerminate(False)
    except Exception:
        import traceback
        from bridge_protocol import atomic_json
        atomic_json(HERE.parent/'io/startup-error.json',{'error':traceback.format_exc()})
        raise

def stop(context):
    global _runtime
    if _runtime is not None:
        _runtime.stop()
        _runtime=None
