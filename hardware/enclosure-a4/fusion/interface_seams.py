"""Explicitly identify only the designed 0.15 mm cover-tab parting seams."""
import math


def is_driver_cover_seam(x,y,z,working):
    spec=working.get('screen_driver_access')
    if not spec:return False
    ox,oy,oz=working['screen_origin_mm'];q=math.sqrt(.5)
    u=x-ox;v=q*(y-oy+z-oz);n=q*(-y+oy+z-oz)
    if not -17.5<n<spec['cap_n_limit_mm']+.05:return False
    inner=spec['lower_cover_tab_radius_mm']-.035
    outer=spec['upper_clearance_radius_mm']+.035
    return any(inner<math.hypot(u-cu,v-cv)<outer for cu,cv in spec['centers_uv'])
