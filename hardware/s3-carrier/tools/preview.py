"""Draw engineering previews from actual design coordinates, not a mock render."""
import json
import math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon, Rectangle, Circle
from route_board import outline_polygon
from build_design import ROOT, REVISION


def main():
    out=ROOT/'output';d=json.loads((out/'design.json').read_text())
    poly=outline_polygon(d['outline'])
    fig,axes=plt.subplots(1,2,figsize=(13,7.1),layout='constrained')
    fig.set_facecolor('#f6f7fa')
    for ax in axes:
        ax.set_aspect('equal');ax.set_xlim(-3,82);ax.set_ylim(76,-3)
        ax.set_facecolor('#f6f7fa');ax.add_patch(MplPolygon(list(poly.exterior.coords),facecolor='#194f41',edgecolor='#102e27',lw=1.5,zorder=0))
        ax.spines[['top','right']].set_visible(False);ax.set_xlabel('mm');ax.set_ylabel('mm')
    axes[0].set_title(f'{REVISION} - direct GPIO / module placement',loc='left',weight='bold')
    axes[1].set_title('Two copper layers / actual routed tracks',loc='left',weight='bold')
    for t in d['traces']:
        xs,ys=zip(*t['points']);color='#ef805a' if t['layer']=='F.Cu' else '#55a8f5'
        axes[1].plot(xs,ys,color=color,lw=.45 if t['width']==.25 else .8,alpha=.85,zorder=1)
    colors={'U1':'#d7dde4','U2':'#9166b4','U3':'#3e4049','J1':'#262a33','JP1':'#d88f2b'}
    for c in d['components']:
        x1,y1,x2,y2=c['envelope'];color=colors.get(c['ref'],'#eedec5')
        if c['ref']=='U3':shape=Circle(((x1+x2)/2,(y1+y2)/2),7,facecolor=color,edgecolor='#111',lw=.8)
        else:shape=Rectangle((x1,y1),x2-x1,y2-y1,facecolor=color,edgecolor='#212a32',lw=.8)
        axes[0].add_patch(shape)
        text={'U1':'GOOUUU ESP32-S3 N16R8\n42 pins / 25.4 mm row spacing\n← USB                 ANTENNA →',
              'U2':'MAX\n98357A','U3':'INMP441\nround','J1':'LCD 1×8',
              'JS1':'','JP1':''}.get(c['ref'],c['ref'])
        axes[0].text((x1+x2)/2,(y1+y2)/2,text,ha='center',va='center',fontsize=6 if c['ref'][0] in ['R','Q'] else 8,
                     color='white' if c['ref'] in ['U2','U3','J1'] else '#18202b',weight='bold')
        if c['ref']=='JP1':
            axes[0].text(30.7,39,'6 dB',fontsize=6,va='center')
            axes[0].text(30.7,41.54,'GAIN',fontsize=6,va='center')
            axes[0].text(30.7,44.08,'12 dB',fontsize=6,va='center')
            axes[0].text(28,36,'JP1',fontsize=7,ha='center',weight='bold')
        for p in c['pads']:
            for ax in axes:
                ax.add_patch(Circle((p['x'],p['y']),max(p['width'],p['height'])/2,facecolor='#d4b268',edgecolor='#eada9c',lw=.2,zorder=3))
                if p['drill']:
                    ax.add_patch(Circle((p['x'],p['y']),p['drill']/2,facecolor='#111b1d',edgecolor='none',zorder=4))
        for h in c['holes']:
            for ax in axes:ax.add_patch(Circle((h['x'],h['y']),h['diameter']/2,facecolor='#f6f7fa',edgecolor='#263d36',lw=.3,zorder=4))
    for h in d['mountingHoles']:
        for ax in axes:
            ax.add_patch(Circle((h['x'],h['y']),3,fill=False,edgecolor='#aebbc3',lw=.7,zorder=5))
            ax.add_patch(Circle((h['x'],h['y']),h['diameter']/2,facecolor='#f6f7fa',edgecolor='#111',lw=.5,zorder=5))
            if h['ref'] in d.get('nylonMountingHoles',[]):
                ax.text(h['x']-1,h['y']-3,'H2: NYLON',ha='center',fontsize=6.5,color='#af6500',zorder=8)
    for v in d['vias']:
        axes[1].add_patch(Circle((v['x'],v['y']),.35,facecolor='#d4b268',edgecolor='none',zorder=3))
    for p in d['keycapEnvelopes']:
        a,b,c,e=p['envelope']
        axes[0].add_patch(Rectangle((a,b),c-a,e-b,fill=False,edgecolor='#f4b953',ls='--',lw=1,zorder=5))
    for p in d['connectorMatingEnvelopes']:
        a,b,c,e=p['envelope']
        axes[0].add_patch(Rectangle((a,b),c-a,e-b,fill=False,edgecolor='#dceaf4',ls='--',lw=1,zorder=5))
    a,b,c,e=d['gainSelector']['assemblyEnvelope']
    axes[0].add_patch(Rectangle((a,b),c-a,e-b,fill=False,edgecolor='#f8c97f',ls='--',lw=1,zorder=5))
    motion=d['joystickMotionReservation'];cx,cy=motion['center']
    axes[0].add_patch(Circle((cx,cy),motion['radiusMm'],fill=False,edgecolor='#c0b2ef',ls=':',lw=1.2,zorder=5))
    axes[0].add_patch(Circle((cx,cy),motion['capDiameterFromStepMm']/2,facecolor='#b9c0c9',edgecolor='#444b55',alpha=.8,zorder=5))
    axes[0].text(cx,cy,'14 mm\ncap',ha='center',va='center',fontsize=7,zorder=6)
    a,b,c,e=d['antennaKeepout']
    for ax in axes:
        ax.add_patch(Rectangle((a,b),c-a,e-b,facecolor='#f7ce7b',edgecolor='#b8790d',
                               alpha=.28,hatch='//',lw=.6,zorder=6))
    axes[1].text((a+c)/2,(b+e)/2,'ANT',rotation=90,ha='center',va='center',fontsize=8,color='#e5b963',zorder=7)
    axes[0].text(2,72,'Original outline, holes and controls retained',fontsize=7.5,color='#3a4655')
    axes[0].text(2,74.5,'Dashed: keycaps / plug; dotted: motion allowance (Z unverified)',fontsize=6.7,color='#3a4655')
    axes[1].text(2,72,'Red: top tracks   Blue: bottom tracks',fontsize=7.5,color='#3a4655')
    axes[1].text(2,74.5,'Two filled GND pours are in the native PCB; not shown here',fontsize=6.7,color='#3a4655')
    fig.suptitle(f'HachimoDock ESP32-S3  |  Carrier PCB {REVISION}',fontsize=17,weight='bold',ha='left',x=.025)
    fig.savefig(out/'pcb-preview.png',dpi=170)
    fig.savefig(out/'pcb-preview.svg')
    print(out/'pcb-preview.png')


if __name__=='__main__':main()
