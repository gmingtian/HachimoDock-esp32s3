"""File queue worker; all CAD dispatch occurs on Fusion's main thread."""
import importlib.util
import json
import queue
import threading
import time
import traceback
import uuid
from pathlib import Path
import adsk.core
from bridge_protocol import OPERATIONS,validate_request,atomic_json

EVENT_ID='gaomt.a4.enclosure.session.bridge'

class MainThreadHandler(adsk.core.CustomEventHandler):
    def __init__(self,runtime):
        super().__init__();self.runtime=runtime
    def notify(self,args):self.runtime.process()

class BridgeRuntime:
    def __init__(self,folder):
        self.folder=Path(folder)
        self.task_root=self.folder.parents[1]
        self.workspace=self.folder.parents[4]
        self.io=self.folder.parent/'io'
        self.output=self.task_root/'output/r2-fusion'
        self.session=uuid.uuid4().hex
        self.app=adsk.core.Application.get()
        self.stop_event=threading.Event();self.queue=queue.Queue(maxsize=1)
        self.seen=set();self.handlers=[];self.event=None
        self.context={'app':self.app,'workspace':self.workspace,'output':self.output,'session':self.session,'documents':{},'bodies':{}}

    def start(self):
        self.io.mkdir(parents=True,exist_ok=True);self.output.mkdir(parents=True,exist_ok=True)
        self.event=self.app.registerCustomEvent(EVENT_ID)
        handler=MainThreadHandler(self);self.event.add(handler);self.handlers.append(handler)
        atomic_json(self.io/'status.json',{'running':True,'session_id':self.session,'fusion_version':self.app.version,'operations':sorted(OPERATIONS),'output_directory':str(self.output),'network_listener':False,'startup_enabled':False})
        self.worker=threading.Thread(target=self.watch,name='A4EnclosureBridge',daemon=True)
        self.worker.start()
        self.app.log('A4 enclosure API bridge started: '+str(self.io))

    def watch(self):
        request_path=self.io/'request.json'
        while not self.stop_event.wait(.3):
            if not request_path.exists() or not self.queue.empty():continue
            try:
                if request_path.stat().st_size>1024*1024:raise ValueError('Request exceeds 1 MiB')
                request=validate_request(json.loads(request_path.read_text(encoding='utf-8-sig')))
                key=request['session_id']+':'+request['id']
                if key in self.seen:continue
                self.seen.add(key)
                if request['session_id']!=self.session:
                    self.reply(request,False,error='Session mismatch; read the current status.json')
                    continue
                self.queue.put_nowait(request)
                accepted=self.app.fireCustomEvent(EVENT_ID,request['id'])
                atomic_json(self.io/'event-diagnostic.json',{'request_id':request['id'],'returned':accepted,'time':time.time()})
            except Exception as exc:
                atomic_json(self.io/'last-error.json',{'error':str(exc),'time':time.time()})

    def process(self):
        try:request=self.queue.get_nowait()
        except queue.Empty:return
        try:
            if request['op'] not in ['ping','shutdown'] and self.app.userInterface.activeCommand not in ['', 'SelectCommand']:
                raise RuntimeError('Fusion is busy with a dialog or modeling command; finish or cancel it, then submit a new request ID')
            if request['op']=='shutdown':
                self.reply(request,True,result={'stopped':True});self.stop();return
            # Hot-load this one fixed, workspace-authored module. Request data
            # cannot supply code, an import path, or a Python expression.
            spec=importlib.util.spec_from_file_location('a4_fusion_session_ops',self.folder/'fusion_ops.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            result=module.dispatch(self.context,request['op'],request['args'])
            self.reply(request,True,result=result)
        except Exception as exc:self.reply(request,False,error=str(exc),traceback=traceback.format_exc())

    def reply(self,request,ok,**payload):
        atomic_json(self.io/'responses'/(request['id']+'.json'),{'id':request['id'],'session_id':self.session,'ok':ok,**payload})

    def stop(self):
        self.stop_event.set()
        if self.event is not None:
            for handler in self.handlers:self.event.remove(handler)
            self.app.unregisterCustomEvent(EVENT_ID)
            self.event=None;self.handlers.clear()
        atomic_json(self.io/'status.json',{'running':False,'session_id':self.session,'network_listener':False,'startup_enabled':False})
