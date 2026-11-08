"""Identify only the approved wordmark groove in front-surface inspection."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def contours():
    return json.loads((Path(__file__).parent/'assets/hachimo-joystick-vectors.json').read_text(encoding='utf-8'))['components']


def in_loop(x,y,points):
    inside=False
    for a,b in zip(points,points[1:]+points[:1]):
        if (a[1]>y)!=(b[1]>y):
            cross=a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if x<cross:inside=not inside
    return inside


def is_wordmark_groove(u,v,working):
    spec=working.get('lettering')
    if not spec:return False
    du,dv=spec['offset_uv_mm'];x,y=u-du,v-dv
    return any(sum(in_loop(x,y,p) for p in component)%2==1 for component in contours())
