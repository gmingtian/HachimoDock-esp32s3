#!/usr/bin/env python3
"""Derive native landscape artwork from canonical packages without moving controls.

Generation uses Pillow; --check only needs the standard library. The shared P4
packages and caches remain canonical and untouched. Font atlases keep their
glyph grids and metrics, with lossless A8 coverage instead of RGBA quantization.
"""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import zlib

REPO = Path(__file__).resolve().parents[2]
DEFAULT = REPO/'firmware/assets/s3-landscape-ui'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pack_indices(indices):
    out = bytearray()
    at = 0
    while at < len(indices):
        run = 1
        while run < 128 and at+run < len(indices) and indices[at+run] == indices[at]:
            run += 1
        if run >= 3:
            out.extend((128 | (run-1), indices[at]))
            at += run
        else:
            start = at
            at += 1
            while at < len(indices) and at-start < 128:
                if at+2 < len(indices) and indices[at] == indices[at+1] == indices[at+2]:
                    break
                at += 1
            out.append(at-start-1)
            out.extend(indices[start:at])
    return out


def encode(image, font=False, jpeg=False):
    from PIL import Image
    w,h = image.size
    if jpeg:
        if (w,h) != (320,240) or image.getextrema()[3] != (255,255):
            raise ValueError('native background must be opaque 320x240')
        stream = io.BytesIO()
        image.convert('RGB').save(stream,'JPEG',quality=95,subsampling=0,optimize=True)
        data = b'P4J1'+struct.pack('<HHI',w,h,12+len(stream.getvalue()))+stream.getvalue()
    else:
        if font:
            indices = image.getchannel('A').tobytes()
            palette = bytes(v for a in range(256) for v in (255,255,255,a))
        else:
            quantized = image.quantize(colors=256,method=Image.Quantize.FASTOCTREE,
                                       dither=Image.Dither.NONE)
            palette = bytes(quantized.getpalette('RGBA')).ljust(1024,b'\0')
            indices = quantized.tobytes()
        header = b'P4I2'+struct.pack('<HHI',w,h,0) if w > 240 else b'P4I1'+bytes((w,h,1,0))+b'\0'*4
        data = bytearray(header+palette+pack_indices(indices))
        struct.pack_into('<I',data,8,len(data))
        data = bytes(data)
    if len(data) > 100000:
        raise ValueError(f'native artwork exceeds image budget: {w}x{h}, {len(data)} bytes')
    return data


def target_image(source, declaration, surface, font):
    from PIL import Image
    if font:
        return source.copy(), 'lossless-glyph-A8'
    nodes = [n for n in surface['elements'] if n.get('type') == 'image' and n.get('image') == declaration['id']]
    columns = max((n.get('tile',{}).get('columns',1) for n in nodes),default=1)
    rows = max((n.get('tile',{}).get('rows',1) for n in nodes),default=1)
    if any(n.get('tile',{}).get('columns',1) != columns or n.get('tile',{}).get('rows',1) != rows for n in nodes):
        raise ValueError('one image cannot have conflicting tile grids')
    cw = max((max(8,(n['w']+1)//2) for n in nodes),default=max(8,source.width//2//columns))
    ch = max((max(8,(n['h']+1)//2) for n in nodes),default=max(8,source.height//2//rows))
    if columns == rows == 1:
        return source.resize((cw,ch),Image.Resampling.LANCZOS), 'native-lanczos'
    if source.width % columns or source.height % rows:
        raise ValueError('invalid original tile grid')
    out = Image.new('RGBA',(cw*columns,ch*rows))
    sw,sh = source.width//columns,source.height//rows
    for row in range(rows):
        for col in range(columns):
            cell = source.crop((col*sw,row*sh,(col+1)*sw,(row+1)*sh))
            out.paste(cell.resize((cw,ch),Image.Resampling.LANCZOS),(col*cw,row*ch))
    return out, 'native-lanczos-per-tile'


def generate(output):
    from PIL import Image
    output = Path(output)
    if output.resolve() in ((REPO/'pc/builtin-clawpkgs').resolve(), REPO.resolve()):
        raise ValueError('refusing canonical source destination')
    sources = {}
    images = []

    def source(path):
        path = Path(path)
        sources[path.relative_to(REPO).as_posix()] = digest(path.read_bytes())
        return path

    def write(name,data):
        path = output/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)

    source(Path(__file__).resolve())
    config = json.loads(source(REPO/'firmware/factory-config.json').read_text())
    policy = json.loads(source(REPO/'firmware/s3/component-policy.json').read_text())
    identifiers = [i for i in config['components']['ids'] if i not in policy['unsupportedBuiltins']]
    for identifier in identifiers:
        original = REPO/'pc/builtin-clawpkgs'/identifier
        widget = json.loads(source(original/'runtime/widget.json').read_text())
        adapted = copy.deepcopy(widget)
        surface = adapted.get('surface',{})
        fonts = {f['image'] for f in surface.get('fonts',[])}
        records = {}
        for im in surface.get('images',[]):
            src = source(original/im['asset'])
            rgba = Image.open(src).convert('RGBA')
            native,method = target_image(rgba,im,surface,im['id'] in fonts)
            if native.width > (640 if im.get('encoding') == 'jpeg' else 512) or native.height > 240:
                raise ValueError(f'image bounds exceeded: {identifier}/{im["id"]}')
            im['frame_width'],im['frame_height'] = native.size
            png = io.BytesIO();native.save(png,'PNG',optimize=True)
            write(Path('packages')/identifier/im['asset'],png.getvalue())
            data = encode(native,font=im['id'] in fonts,jpeg=im.get('encoding') == 'jpeg')
            write(Path('surfaces')/identifier/(im['id']+'.p4i'),data)
            spec = json.dumps(im,sort_keys=True,separators=(',',':')).encode()
            records[im['id']] = {'source':digest(png.getvalue()),'spec':digest(spec),'encoded':digest(data)}
            images.append({'role':'component','component':identifier,'image':im['id'],
                           'source':str(src.relative_to(REPO)),'sourceSize':list(rgba.size),
                           'size':list(native.size),'method':method})
        if records:
            write(Path('surfaces')/identifier/'index.json',json.dumps(records,indent=2,sort_keys=True).encode()+b'\n')
        write(Path('packages')/identifier/'runtime/widget.json',json.dumps(adapted,ensure_ascii=False,indent=2).encode()+b'\n')
        for name in ('component.json','buttons.json'):
            write(Path('packages')/identifier/name,source(original/name).read_bytes())

    bg = source(REPO/'firmware/assets/component-center/background.png')
    image = Image.open(bg).convert('RGB').resize((320,240),Image.Resampling.LANCZOS)
    stream = io.BytesIO();image.save(stream,'JPEG',quality=95,subsampling=0,optimize=True)
    write(Path('launcher/center_background.jpg'),stream.getvalue())
    images.append({'role':'launcher-background','source':str(bg.relative_to(REPO)),'size':[320,240]})
    thumbs = bytearray()
    for identifier in config['components']['ids']:
        package = REPO/'pc/builtin-clawpkgs'/identifier
        surface = json.loads(source(package/'runtime/widget.json').read_text()).get('surface',{})
        art = next((i for i in surface.get('images',[]) if i.get('encoding') == 'jpeg'),None)
        if art is None:
            art = next(iter(surface.get('images',[])),None)
        if art:
            src = source(package/art['asset'])
            thumb = Image.open(src).convert('RGB').resize((32,24),Image.Resampling.LANCZOS)
            rgb = thumb.tobytes()
            for r,g,b in zip(rgb[0::3],rgb[1::3],rgb[2::3]):
                thumbs.extend(struct.pack('<H',(r>>3)<<11|(g>>2)<<5|(b>>3)))
            images.append({'role':'launcher-thumbnail','component':identifier,
                           'source':str(src.relative_to(REPO)),'size':[32,24]})
        else:
            thumbs.extend(b'\0'*(32*24*2))
    write(Path('launcher/center_thumbs.deflate'),zlib.compress(thumbs,9))
    for name,size in [('body',(160,122)),('mallet',(80,82))]:
        src = source(REPO/f'pc/public/instruments/wooden-fish/{name}.png')
        rgba = Image.open(src).convert('RGBA');rgba = rgba.crop(rgba.getbbox())
        rgba = rgba.resize(size,Image.Resampling.LANCZOS)
        raw = bytearray(struct.pack('<HH',*rgba.size))
        pixels = rgba.tobytes()
        for r,g,b,a in zip(pixels[0::4],pixels[1::4],pixels[2::4],pixels[3::4]):
            raw.extend(struct.pack('<HB',(r>>3)<<11|(g>>2)<<5|(b>>3),a))
        write(Path(f'instruments/wooden_fish_{name}.deflate'),zlib.compress(raw,9))
        images.append({'role':'instrument','source':str(src.relative_to(REPO)),'size':list(size)})
    files = {p.relative_to(output).as_posix():digest(p.read_bytes()) for p in sorted(output.rglob('*'))
             if p.is_file() and p.name != 'inventory.json'}
    inventory = {'format':'s3-native-ui-v1','display':[320,240],'logicalCanvas':[640,480],
                 'components':identifiers,'images':images,'sources':sources,'files':files}
    write(Path('inventory.json'),json.dumps(inventory,ensure_ascii=False,indent=2,sort_keys=True).encode()+b'\n')
    return inventory


def check(output):
    output = Path(output)
    inventory = json.loads((output/'inventory.json').read_text())
    for relative,expected in inventory['sources'].items():
        if digest((REPO/relative).read_bytes()) != expected:
            raise ValueError('stale original UI artwork: '+relative)
    for relative,expected in inventory['files'].items():
        if digest((output/relative).read_bytes()) != expected:
            raise ValueError('stale native UI artwork: '+relative)
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT)
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    inventory = check(args.output) if args.check else generate(args.output)
    print(json.dumps({'components':len(inventory['components']),
                      'adaptedImages':len(inventory['images']),'output':str(args.output)}))


if __name__ == '__main__':
    main()
