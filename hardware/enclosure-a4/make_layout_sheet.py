"""Static coordinate and socket-height review sheet, not a fabrication drawing."""
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle,Polygon,Rectangle,FancyArrowPatch
from matplotlib.font_manager import FontProperties
from build_enclosure import D,P,OUT

font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams['font.family']=font.get_name()
plt.rcParams['axes.unicode_minus']=False

def outline():
    todo=list(D['outline']);edge=todo.pop(0);cur=edge['start'];pts=[]
    while True:
        a,b=edge['start'],edge['end'];angle=edge['angle']
        if math.dist(cur,a)>.002:a,b=b,a;angle=-angle
        pts.append(a)
        if angle:
            t=math.radians(angle);sx,sy=a;ex,ey=b
            cx=(sx+ex)/2-(ey-sy)/(2*math.tan(t/2));cy=(sy+ey)/2+(ex-sx)/(2*math.tan(t/2))
            for f in np.linspace(0,1,24)[1:]:pts.append([cx+(sx-cx)*math.cos(t*f)-(sy-cy)*math.sin(t*f),cy+(sx-cx)*math.sin(t*f)+(sy-cy)*math.cos(t*f)])
        cur=b
        if not todo:break
        k=next(i for i,e in enumerate(todo) if min(math.dist(cur,e['start']),math.dist(cur,e['end']))<.002)
        edge=todo.pop(k)
    return pts

def main():
    fig,axs=plt.subplots(1,2,figsize=(15,8),gridspec_kw={'width_ratios':[1.2,1]},layout='constrained')
    fig.patch.set_facecolor('#f5f6f8')
    ax=axs[0];ax.set_aspect('equal');ax.set_xlim(-16,88);ax.set_ylim(82,-12)
    ax.add_patch(Polygon(outline(),facecolor='#e6eeea',edgecolor='#4b655b',lw=1.4))
    for ref in ['U1','U2','U3']:
        c=next(c for c in D['components'] if c['ref']==ref);x0,y0,x1,y1=c['envelope']
        ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor='#ccd4dc',edgecolor='#677383',alpha=.6))
        label={'U1':'果云开发板\n保留排母','U2':'功放\n低位安装','U3':'麦克风\n低位安装'}[ref]
        ax.text((x0+x1)/2,(y0+y1)/2,label,ha='center',va='center',fontsize=10,color='#293944',fontproperties=font)
    for c in D['keycapEnvelopes']:
        x0,y0,x1,y1=c['envelope'];ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor='#f8dec9',edgecolor='#ad6032',lw=1))
        ax.text((x0+x1)/2,(y0+y1)/2,c['ref'],ha='center',va='center',fontsize=10)
    cx,cy=D['joystickMotionReservation']['center']
    ax.add_patch(Circle((cx,cy),7.05,facecolor='#e87d32',edgecolor='#a74b1e'))
    ax.add_patch(Circle((cx,cy),18*math.sin(math.radians(32))+7.05,fill=False,edgecolor='#b5653f',ls='--',lw=1))
    ax.text(70,79,'原球帽运动投影\n与 SW3 原有干涉保留',ha='center',fontsize=10,color='#8b4b2b',fontproperties=font)
    for ref,label,pos,color in [
        ('H1','H1 塑料定位柱',(-12,29),'#32618b'),
        ('H3','H3 圆形螺丝柱',(24,26),'#a34d29'),
        ('H4','H4 圆形螺丝柱',(73,32),'#a34d29')]:
        h=next(h for h in D['mountingHoles'] if h['ref']==ref)
        ax.add_patch(Circle((h['x'],h['y']),3.4,facecolor='#ffffff',edgecolor=color,lw=1.6))
        ax.add_patch(Circle((h['x'],h['y']),1.3 if ref=='H1' else 1.8,facecolor=color))
        ax.annotate(label,(h['x'],h['y']),xytext=pos,fontsize=10,color=color,fontproperties=font,arrowprops={'arrowstyle':'-','color':color,'lw':.8})
    ax.add_patch(Circle((46,42.1),1.2,facecolor='#2c8063',edgecolor='white',lw=.5))
    ax.annotate('底部收音孔 Ø2.4',(46,42.1),xytext=(63,45),fontsize=10,color='#28634e',fontproperties=font,arrowprops={'arrowstyle':'-','color':'#28634e','lw':.8})
    ax.annotate('',(0,74),(73.47473748,74),arrowprops={'arrowstyle':'<->','color':'#667481'})
    ax.text(36.7,77,'PCB 73.47 mm',ha='center',fontsize=11)
    ax.annotate('',(-8,0),(-8,69.47474802),arrowprops={'arrowstyle':'<->','color':'#667481'})
    ax.text(-11.5,47,'69.47 mm',rotation=90,ha='center',fontsize=11)
    ax.set_title('A4 固定与开孔：采用工程原坐标',fontproperties=font,fontsize=14,pad=15)
    ax.axis('off')
    ax=axs[1];ax.set_xlim(-1,19);ax.set_ylim(-1,18);ax.set_aspect(.62)
    ax.axhline(0,color='#6a777f',lw=.9)
    bars=[('开发板 U1\n保持原插接',1,8.5),('原音频插接\n高度参考',7,8.5),('R1 功放/麦克风\n去排母低位安装',13,0)]
    for name,x,socket in bars:
        z=0
        for height,col in [(socket,'#8b959f'),(2.5,'#d8ac66'),(1.6,'#638b77'),(3.5,'#b7bec6')]:
            if height:ax.add_patch(Rectangle((x,z),3.5,height,facecolor=col,edgecolor='#f5f6f8',lw=1));z+=height
        ax.text(x+1.75,z+.4,f'{z:.1f} mm',ha='center',fontsize=13,color='#263844')
        ax.text(x+1.75,-.5,name,ha='center',va='top',fontproperties=font,fontsize=10)
    ax.annotate('预计降低 8.5 mm',(14.75,12),xytext=(10,17.5),fontsize=12,color='#a34d29',fontproperties=font,arrowprops={'arrowstyle':'->','color':'#a34d29'})
    ax.set_ylabel('相对大 PCB 上表面高度（mm）',fontproperties=font)
    ax.set_xticks([]);ax.set_yticks([0,2.5,7.6,12.6,16.1]);ax.grid(axis='y',color='#ccd3d8',lw=.5);ax.set_axisbelow(True)
    for spine in ax.spines.values():spine.set_visible(False)
    ax.set_title('按普通 8.5 mm 排母估算',fontproperties=font,fontsize=14,pad=15)
    fig.suptitle('HachimoDock A4 · R1 结构核对',fontproperties=font,fontsize=20)
    fig.savefig(OUT/'layout-and-height-r1.png',dpi=160)
    fig.savefig(OUT/'layout-and-height-r1.svg')
    print(OUT/'layout-and-height-r1.png')

if __name__=='__main__':main()
