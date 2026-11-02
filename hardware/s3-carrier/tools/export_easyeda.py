"""Export the same explicit pad/track design to editable EasyEDA Pro format."""
import copy
import json
import math
from pathlib import Path
import zipfile

from build_design import ROOT, REVISION, STEM, ORIGIN, MIL, uid
from source_geometry import read_archive


def identity(text):return uid(text).replace('-','')[:16]
def raw(x,y):return ORIGIN[0]+x/MIL,ORIGIN[1]-y/MIL


def main():
    output=ROOT/'output';design=json.loads((output/'design.json').read_text())
    reference=read_archive(ROOT/'reference/upstream-pcb-v1.2.epro2')
    template=reference['1ecf9d019d074243']
    records=[];ticket=0
    def put(kind,value,id=None):
        nonlocal ticket
        ticket+=1
        records.append(json.dumps({'type':kind,'ticket':ticket,'id':id or identity(f'{kind}/{ticket}')},ensure_ascii=False,separators=(',',':'))+
                       '||'+json.dumps(value,ensure_ascii=False,separators=(',',':'))+'|')
    netnames=sorted({p['net'] for c in design['components'] for p in c['pads'] if p['net']})
    for c in design['components']:
        fp=identity('footprint/'+c['ref'])
        put('DOCHEAD',{'docType':'FOOTPRINT','uuid':fp,'version':'1','editVersion':'4.1.78'})
        put('CANVAS',{'originX':0,'originY':0,'unit':'mm','gridXSize':5,'gridYSize':5,
                      'snapXSize':5,'snapYSize':5,'gridType':'NONE','multiGridType':'NONE','multiGridRatio':5})
        for i,p in enumerate(c['pads']):
            put('PAD',{'groupId':0,'netName':'','layerId':1 if c.get('mount')=='smd' else 12,
                'num':p['number'],'centerX':(p['x']-c['x'])/MIL,'centerY':-(p['y']-c['y'])/MIL,
                'padAngle':p['angle'],'hole':None if p['drill']==0 else {'holeType':'ROUND','width':p['drill']/MIL,'height':p['drill']/MIL},
                'defaultPad':{'padType':'RECT' if p['shape']=='rect' else 'ELLIPSE','width':p['width']/MIL,'height':p['height']/MIL,'radius':0},
                'specialPad':[],'padOffsetX':0,'padOffsetY':0,'relativeAngle':0,'plated':True,
                'padType':'NORMAL','locked':False,'zIndex':i},f'p{i}')
        for i,h in enumerate(c['holes']):
            put('FILL',{'groupId':0,'netName':'','layerId':12,'width':1,'fillStyle':'SOLID',
                'path':[['CIRCLE',(h['x']-c['x'])/MIL,-(h['y']-c['y'])/MIL,h['diameter']/MIL/2]],
                'locked':False,'zIndex':-1,'isBridgingCopper':False,'networkList':[],'refs':None})
        x1,y1,x2,y2=c['envelope'];a=(x1-c['x'])/MIL;b=-(y1-c['y'])/MIL;d=(x2-c['x'])/MIL;e=-(y2-c['y'])/MIL
        put('POLY',{'groupId':0,'netName':'','layerId':3,'width':6,
                    'path':[a,b,'L',d,b,d,e,a,e,a,b],'locked':False,'zIndex':-1,'polyType':'NORMAL'})
        put('META',{'title':c['ref']+' '+c['title'],'description':f'S3 carrier {REVISION}, see source attribution and validation report','tags':[]})
    board_id=identity('board/'+REVISION)
    put('DOCHEAD',{'docType':'PCB','uuid':board_id,'version':'1','editVersion':'4.1.78'})
    for h,d in template['records']:
        if h['type'] in ['LAYER','LAYER_PHYS','ACTIVE_LAYER','CANVAS','PRIMITIVE','RULE_TEMPLATE','RULE']:
            put(h['type'],copy.deepcopy(d),h['id'])
    for name in netnames:
        put('NET',{'netType':None,'specialColor':None,'retLine':True,'differentialName':None,
                   'isPositiveNet':False,'equalLengthGroupName':None},json.dumps(['NET',name],separators=(',',':')))
    for c in design['components']:
        component_id=identity('component/'+c['ref']);x,y=raw(c['x'],c['y'])
        put('COMPONENT',{'partitionId':'','groupId':0,'layerId':1,'x':x,'y':y,'angle':0,
                         'attrs':{},'locked':False,'zIndex':-1},component_id)
        for key,value in [('Footprint',identity('footprint/'+c['ref'])),('Designator',c['ref'])]:
            put('ATTR',{'partitionId':'','groupID':0,'parentId':component_id,'layerId':3,
                'x':x,'y':y,'key':key,'value':value,'keyVisible':False,'valueVisible':key=='Designator',
                'fontFamily':'default','fontSize':28,'strokeWidth':4,'bold':False,'italic':False,
                'origin':'LEFT_BOTTOM','angle':0,'reverse':False,'expansion':0,'mirror':False,
                'locked':False,'zIndex':-1})
        for i,p in enumerate(c['pads']):
            put('PAD_NET',{'partitionId':'','padNet':p['net'],'padLen':0},
                json.dumps(['PAD_NET',component_id,p['number'],f'p{i}'],separators=(',',':')))
    for h,d in template['records']:
        if h['type']=='POLY' and d.get('layerId')==11:
            put('POLY',copy.deepcopy(d))
        elif h['type']=='FILL' and d.get('layerId')==12:
            put('FILL',copy.deepcopy(d))
    for route in design['traces']:
        for a,b in zip(route['points'],route['points'][1:]):
            if a==b:continue
            x1,y1=raw(*a);x2,y2=raw(*b)
            put('LINE',{'partitionId':'','groupId':0,'netName':route['net'],'layerId':1 if route['layer']=='F.Cu' else 2,
                'startX':x1,'startY':y1,'endX':x2,'endY':y2,'width':route['width']/MIL,'locked':False,'zIndex':-1})
    for via in design['vias']:
        x,y=raw(via['x'],via['y'])
        put('VIA',{'partitionId':'','groupId':0,'netName':via['net'],'ruleName':'',
            'centerX':x,'centerY':y,'holeDiameter':.35/MIL,'viaDiameter':.7/MIL,
            'viaType':'NORMAL','topSolderExpansion':None,'bottomSolderExpansion':None,'locked':False,'unusedInnerLayers':[]})
    for label in design['silkscreen']:
        x,y=raw(label['x'],label['y'])
        # STRING fields/origin match the downloaded module reference archive.
        put('STRING',{'groupId':0,'layerId':3,'x':x,'y':y,'text':label['text'],
            'fontFamily':'default','fontSize':label['size']/MIL,
            'strokeWidth':label['thickness']/MIL,'bold':False,'italic':False,
            'origin':'CENTER_MIDDLE','angle':0,'reverse':False,'expansion':0,
            'mirror':False,'locked':False,'zIndex':-1})
    vertices=[raw(*p) for p in design['groundPourPolygon']]
    path=[*vertices[0],'L']+[n for p in vertices[1:]+vertices[:1] for n in p]
    paths=[path]
    for f in design.get('fastenerEnvelopes',[]):
        radius=f['copperKeepoutRadiusMm']/math.cos(math.pi/36)
        hole=[raw(f['x']+radius*math.cos(-i*math.pi/18),
                  f['y']+radius*math.sin(-i*math.pi/18)) for i in range(36)]
        paths.append([*hole[0],'L']+[n for p in hole[1:]+hole[:1] for n in p])
    for layer in [1,2]:
        put('POUR',{'partitionId':'','groupId':0,'netName':'GND','layerId':layer,
            'width':.2/MIL,'name':f'GND_{layer}','order':0,'path':paths,
            'pourType':{'pourType':'SOLID','fineness':8},'keepIsland':False,
            'locked':False,'zIndex':-1})
    put('META',{'title':STEM,'parent':'','source':'','board':'','zIndex':None})
    path=output/f'{STEM}.epro2'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('project2.json',json.dumps({'title':f'HachimoDock S3 carrier {REVISION}','cbb_project':False,
                      'editorVersion':'4.1.78','introduction':'Engineering draft; see README and validation.json'},ensure_ascii=False))
        z.writestr(f'{STEM}.epru','\n'.join(records)+'\n')
    print(path)


if __name__=='__main__':main()
