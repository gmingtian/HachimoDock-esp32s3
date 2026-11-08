"""Code-native wordmark vectors for preview and subsequent real CAD engraving."""
import json
from pathlib import Path
import numpy as np
import manifold3d as mf
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/r4-original-copy/lettering-preview'
OUT.mkdir(exist_ok=True)


class OutlinePen(BasePen):
    def __init__(self,glyphs):super().__init__(glyphs);self.contours=[];self.points=[]
    def _moveTo(self,p):self.points=[p]
    def _lineTo(self,p):self.points.append(p)
    def _qCurveToOne(self,a,b):
        p=np.array(self._getCurrentPoint());a=np.array(a);b=np.array(b)
        for t in np.linspace(0,1,13)[1:]:self.points.append(((1-t)**2*p+2*(1-t)*t*a+t*t*b).tolist())
    def _curveToOne(self,a,b,c):
        p=np.array(self._getCurrentPoint());a=np.array(a);b=np.array(b);c=np.array(c)
        for t in np.linspace(0,1,17)[1:]:self.points.append(((1-t)**3*p+3*(1-t)**2*t*a+3*(1-t)*t*t*b+t**3*c).tolist())
    def _closePath(self):
        if len(self.points)>2:self.contours.append(self.points)
        self.points=[]
    def _endPath(self):self._closePath()


def text_shape(path,word,replace_i_dot=False):
    font=TTFont(path);glyphs=font.getGlyphSet();cmap=font.getBestCmap();advance=0;shapes=[];idata=None;odata=None
    for char in word:
        name=cmap[ord(char)];p=OutlinePen(glyphs);glyphs[name].draw(p)
        contours=[(np.array(a)+[advance,0]).tolist() for a in p.contours]
        s=mf.CrossSection(contours,mf.FillRule.NonZero)
        if char=='i':idata=s
        if char=='o':odata=s
        shapes.append(s);advance+=font['hmtx'][name][0]
    combined=mf.CrossSection.batch_boolean(shapes,mf.OpType.Add)
    x0,y0,x1,y1=combined.bounds();scale=5.5/(y1-y0)
    combined=combined.translate([-x0,-y0]).scale([scale,scale]).offset(.075).simplify(.004)
    if replace_i_dot:
        pieces=idata.decompose();dot=max(pieces,key=lambda a:a.bounds()[1]);dx0,dy0,dx1,dy1=dot.bounds()
        dot=dot.translate([-x0,-y0]).scale([scale,scale]).offset(.08)
        center=[((dx0+dx1)/2-x0)*scale,((dy0+dy1)/2-y0)*scale]
        combined=combined-dot+mf.CrossSection.circle(.48,48).translate(center)
    return combined,(odata.translate([-x0,-y0]).scale([scale,scale]).offset(.075).simplify(.004) if odata else None)


def pixel_shape():
    glyphs={'H':['10001','10001','10001','11111','10001','10001','10001'],
        'a':['00000','00000','01110','00001','01111','10001','01111'],
        'c':['00000','00000','01111','10000','10000','10000','01111'],
        'h':['10000','10000','10110','11001','10001','10001','10001'],
        'i':['00100','00000','01100','00100','00100','00100','01110'],
        'm':['00000','00000','11011','10101','10101','10101','10101'],
        'o':['00000','00000','01110','10001','10001','10001','01110']}
    boxes=[]
    for i,char in enumerate('Hachimo'):
        for row,line in enumerate(glyphs[char]):
            for col,bit in enumerate(line):
                if bit=='1':boxes.append(mf.CrossSection.square([.76,.76]).translate([(i*6+col)*.75,(6-row)*.75]))
    return mf.CrossSection.batch_boolean(boxes,mf.OpType.Add).simplify(.004)


def render(shape,draw,rect):
    x0,y0,x1,y1=shape.bounds();cx=(rect[0]+rect[2])/2;cy=(rect[1]+rect[3])/2
    scale=min((rect[2]-rect[0])/(x1-x0),(rect[3]-rect[1])/(y1-y0))
    polygons=shape.to_polygons()
    def signed_area(a):return (a[:,0]*np.roll(a[:,1],-1)-a[:,1]*np.roll(a[:,0],-1)).sum()
    polygons=sorted(polygons,key=lambda a:abs(signed_area(a)),reverse=True)
    for outline in polygons:
        area=signed_area(outline)
        pts=[(cx+(p[0]-(x0+x1)/2)*scale,cy-(p[1]-(y0+y1)/2)*scale) for p in outline]
        draw.polygon([(x+1.5,y-1.5) for x,y in pts],fill='#f8fafb' if area>0 else '#e7edf0')
        draw.polygon(pts,fill='#60747d' if area>0 else '#e7edf0')


def svg(shape):
    x0,y0,x1,y1=shape.bounds();paths=[]
    for loop in shape.to_polygons():
        paths.append('M '+' L '.join(f'{p[0]:.5f},{p[1]:.5f}' for p in loop)+' Z')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0-1} {-y1-1} {x1-x0+2} {y1-y0+2}"><g transform="scale(1,-1)"><path d="'+ ' '.join(paths)+'" fill="#243a44" fill-rule="nonzero"/></g></svg>'


def main():
    a,_=text_shape('C:/Windows/Fonts/segoescb.ttf','Hachimo',True)
    b=pixel_shape()
    c,old_o=text_shape('C:/Windows/Fonts/segoeprb.ttf','Hachimo')
    x0,y0,x1,y1=old_o.bounds();center=[(x0+x1)/2,(y0+y1)/2];radius=min((x1-x0)/2,(y1-y0)/2)*.94
    knob=mf.CrossSection.circle(radius,64).translate(center)-mf.CrossSection.circle(radius-.52,64).translate(center)
    stem=mf.CrossSection.square([.6,1.05]).translate([center[0]-.3,center[1]-radius-.85])
    base=mf.CrossSection.square([1.9,.5]).translate([center[0]-.95,center[1]-radius-1.05])
    c=(c-old_o)+knob+stem+base
    designs=[('A','signature','签名球点 · 推荐','手写字 + 放大的 i 圆点，呼应球帽',a),
        ('B','pixel','复古像素','保留 Hachimo 拼写，像素笔画更有掌机感',b),
        ('C','joystick','摇杆字标','把末尾 o 融入一个小摇杆图形',c)]
    im=Image.new('RGB',(1800,1250),'#f2f5f7');draw=ImageDraw.Draw(im)
    chinese='C:/Windows/Fonts/msyh.ttc'
    draw.text((65,35),'Hachimo · 屏幕下方凹嵌字标',font=ImageFont.truetype(chinese,44),fill='#233e49')
    draw.text((68,105),'三款均为实际矢量轮廓；最终居中凹刻，建议字高约5–6 mm、深0.5 mm',font=ImageFont.truetype(chinese,25),fill='#69818b')
    manifest={}
    for i,(letter,key,title,subtitle,shape) in enumerate(designs):
        top=180+i*330
        draw.rounded_rectangle((60,top,1740,top+290),radius=25,fill='#e7edf0',outline='#d6e0e5',width=2)
        draw.text((95,top+28),letter+'  '+title,font=ImageFont.truetype(chinese,30),fill='#2b4652')
        draw.text((95,top+83),subtitle,font=ImageFont.truetype(chinese,22),fill='#6d858e')
        render(shape,draw,(690,top+54,1640,top+214))
        bounds=shape.bounds();draw.text((95,top+231),f'字形约 {bounds[2]-bounds[0]:.1f} × {bounds[3]-bounds[1]:.1f} mm',font=ImageFont.truetype(chinese,20),fill='#6d858e')
        (OUT/(key+'.svg')).write_text(svg(shape),encoding='utf-8')
        groups=[[a.tolist() for a in part.to_polygons()] for part in shape.decompose()]
        manifest[key]={'text':'Hachimo','bounds_mm':list(bounds),'components':groups,'style':title}
    im.save(OUT/'hachimo-lettering-options.png')
    (OUT/'lettering-options.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print({k:{'bounds_mm':v['bounds_mm'],'components':len(v['components'])} for k,v in manifest.items()})


if __name__=='__main__':main()
