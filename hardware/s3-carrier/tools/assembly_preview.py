"""Draw the confirmed microphone mounting direction and straight LCD cable."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle,Rectangle
from build_design import ROOT,REVISION


def main():
    out=ROOT/'output';d=json.loads((out/'design.json').read_text())
    mic=next(c for c in d['components'] if c['ref']=='U3')
    fig,axes=plt.subplots(1,3,figsize=(15,5.4),layout='constrained')
    fig.set_facecolor('#f6f7fa')
    ax=axes[0];ax.set_aspect('equal');ax.set_xlim(-15,15);ax.set_ylim(11,-11)
    ax.add_patch(Circle((0,0),7,facecolor='#25282c',edgecolor='#bfa45e',lw=3))
    ax.add_patch(Circle((0,0),1,facecolor='#f6f7fa',edgecolor='#bfa45e'))
    labels={'1':'GND','2':'VDD / 3V3','3':'SD / GPIO6','4':'L/R / GND','5':'WS / GPIO4','6':'SCK / GPIO5'}
    for p in mic['pads']:
        x,y=p['x']-(mic['envelope'][0]+mic['envelope'][2])/2,p['y']-(mic['envelope'][1]+mic['envelope'][3])/2
        ax.add_patch(Circle((x,y),.9,facecolor='#bfa45e',edgecolor='#eee1b4'))
        ax.add_patch(Circle((x,y),.6,facecolor='#f6f7fa'))
        edge=-8 if x<0 else 8
        ax.plot([x+(-.95 if x<0 else .95),edge],[y,y],color='#7891a2',lw=.8)
        ax.text(edge+(-.3 if x<0 else .3),y,labels[p['number']],ha='right' if x<0 else 'left',va='center',fontsize=8)
    ax.annotate('',xy=(-3.81,8.5),xytext=(3.81,8.5),arrowprops={'arrowstyle':'<->','color':'#54728a'})
    ax.text(0,9.8,'Socket rows: 7.62 mm',ha='center',fontsize=9)
    ax.text(0,-9,'Round module: 14 mm',ha='center',fontsize=10)
    ax.set_title('Microphone: top / label-side view',weight='bold',fontsize=11)
    ax.axis('off')
    ax=axes[1];ax.set_xlim(-1,11);ax.set_ylim(10,-1)
    ax.add_patch(Rectangle((0,2),10,.35,facecolor='#25282c',edgecolor='#bfa45e'))
    ax.text(5,1.1,'Printed labels face outward',ha='center',fontsize=10)
    for x in [2,8]:
        ax.add_patch(Rectangle((x-.32,1.55),.64,3.7,facecolor='#a9adb0'))
        ax.add_patch(Rectangle((x-.8,4),1.6,2.6,facecolor='#2c3036'))
        ax.plot([x,x],[6.6,7.55],color='#bfa45e',lw=2)
    ax.add_patch(Rectangle((0,7.1),10,.4,facecolor='#194f41'))
    ax.text(5,3.35,'Long male pins point DOWN',ha='center',fontsize=10)
    ax.text(5,5.55,'Female sockets',ha='center',fontsize=10)
    ax.text(5,8.5,'Carrier PCB',ha='center',fontsize=10)
    ax.text(5,9.4,'Direction only; heights not to scale',ha='center',fontsize=8,color='#657282')
    ax.set_title('Pre-soldered pins: keep this direction',weight='bold',fontsize=11);ax.axis('off')
    ax=axes[2];ax.set_xlim(-.8,8.2);ax.set_ylim(7,-2)
    for y,title in [(0,'CARRIER J1'),(4,'SCREEN')]:
        ax.add_patch(Rectangle((-.45,y-.35),8,.7,facecolor='#30343b',edgecolor='#14181d'))
        ax.text(3.5,y-1.1,title,ha='center',fontsize=10,weight='bold')
        for i,label in enumerate(d['screenConnectorOrder']):
            ax.add_patch(Circle((i,y),.16,facecolor='#bfa45e'))
            ax.text(i,y+.65,label,ha='center',fontsize=7,rotation=90,va='top')
    for i in range(8):ax.plot([i,i],[.2,3.8],color='#a15f38' if i==0 else '#7b9bab',lw=1.3,zorder=-1)
    ax.text(3.5,6.5,'1-to-1 cable  |  VCC = 3V3',ha='center',fontsize=10)
    ax.set_title('Same 8-pin order; no wire crossover',weight='bold',fontsize=11);ax.axis('off')
    fig.suptitle(f'HachimoDock S3 PCB {REVISION} | Assembly orientation',fontsize=17,weight='bold')
    fig.savefig(out/'assembly-orientation.png',dpi=180)
    fig.savefig(out/'assembly-orientation.svg')
    print(out/'assembly-orientation.png')


if __name__=='__main__':main()
