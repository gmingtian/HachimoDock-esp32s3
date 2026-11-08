"""Design preview from package nodes; not a screenshot of the physical screen."""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
package = root / 'pc/local-clawpkgs/gomoku-a4'
runtime = json.loads((package / 'runtime/widget.json').read_text(encoding='utf-8'))
dashboard = json.loads((package / 'negative-screen.json').read_text(encoding='utf-8'))['dashboard']


def color(v):
    return ((v >> 11) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31)


image = Image.new('RGB', (640, 480), color(runtime['surface']['background']))
draw = ImageDraw.Draw(image)
for n in runtime['surface']['elements']:
    x, y, w, h = [n[k] for k in ('x', 'y', 'w', 'h')]
    if n['type'] == 'image':
        im = next(i for i in runtime['surface']['images'] if i['id'] == n['image'])
        image.paste(Image.open(package / im['asset']).convert('RGB').resize((w, h), Image.Resampling.NEAREST), (x, y))
    elif n['type'] == 'panel':
        draw.rounded_rectangle((x, y, x+w-1, y+h-1), radius=n.get('radius', 0), fill=color(n['color']),
            outline=color(n.get('stroke', n['color'])), width=n.get('stroke_width', 0))
    elif n['type'] == 'text':
        font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', n['font_size'])
        draw.text((x, y), n.get('text', dashboard.get(n.get('bind'), '')), font=font, fill=color(n['color']))
image = image.resize((320, 240), Image.Resampling.LANCZOS)
image.save(root / 'artifacts/gomoku-a4/design-preview.png')
