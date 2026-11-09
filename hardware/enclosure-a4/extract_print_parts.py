#!/usr/bin/env python3
"""Extract the explicitly named original controls from the supplied 3MF.

Only Python's standard library is required. The source project (including its
printer profile and private metadata) is never copied into the public output.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib

ROOT = Path(__file__).resolve().parent
EXPECTED_SOURCE_SHA256 = '766b57fe7ed751a912be640ca9cb538da702cf437b72fbee112a83adadb6ca65'
C = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
P = '{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}'
PARTS = [
    ('6', '\u6309\u952e1', 'keycap-1.stl'),
    ('8', '\u6309\u952e2', 'keycap-2.stl'),
    ('10', '\u6309\u952e3', 'keycap-3.stl'),
    ('14', '\u6447\u6746\u5e3dA', 'joystick-cap-a.stl'),
    ('16', '\u6447\u6746\u5e3dB', 'joystick-cap-b.stl'),
    ('12', '\u6447\u6746\u76d6\u677f', 'joystick-cover.stl'),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def matrix(text):
    values = [float(x) for x in text.split()]
    if len(values) != 12 or not all(math.isfinite(x) for x in values):
        raise ValueError('Expected a finite 3MF 4x3 transform')
    return values


def transform(point, values):
    # 3MF row-vector layout: three basis rows, then the translation row.
    return tuple(sum(point[k] * values[k * 3 + axis] for k in range(3)) + values[9 + axis]
                 for axis in range(3))


def bounds(vertices):
    return [[min(p[k] for p in vertices) for k in range(3)],
            [max(p[k] for p in vertices) for k in range(3)]]


def subtract(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def mesh_stats(vertices, faces):
    # Merge coincident coordinates only for analysis, never for exported mesh.
    unique = {}; ids = []
    for vertex in vertices:
        ids.append(unique.setdefault(tuple(vertex), len(unique)))
    edges = Counter(); directed = Counter(); neighbors = defaultdict(set)
    used = set(); volume = 0.0; degenerate = 0
    for face in faces:
        a, b, c = [vertices[i] for i in face]
        if dot(cross(subtract(b, a), subtract(c, a)), cross(subtract(b, a), subtract(c, a))) <= 1e-22:
            degenerate += 1
        volume += dot(a, cross(b, c)) / 6
        tri = [ids[i] for i in face]
        used.update(tri)
        for x, y in zip(tri, tri[1:] + tri[:1]):
            edges[tuple(sorted((x, y)))] += 1
            directed[(x, y)] += 1
            neighbors[x].add(y); neighbors[y].add(x)
    components = 0
    while used:
        components += 1; stack = [used.pop()]
        while stack:
            for neighbor in neighbors[stack.pop()]:
                if neighbor in used:
                    used.remove(neighbor); stack.append(neighbor)
    return {'vertices': len(vertices), 'triangles': len(faces), 'closed': all(x == 2 for x in edges.values()),
            'windingConsistent': all(directed[(y, x)] == count for (x, y), count in directed.items()),
            'connectedComponents': components, 'degenerateTriangles': degenerate, 'signedVolumeMm3': volume}


def stl_bytes(vertices, faces, name):
    data = bytearray(('HachimoDock original control / mm / ' + name).encode('ascii').ljust(80, b'\0'))
    data.extend(struct.pack('<I', len(faces)))
    for face in faces:
        tri = [vertices[i] for i in face]
        normal = cross(subtract(tri[1], tri[0]), subtract(tri[2], tri[0]))
        length = math.sqrt(dot(normal, normal))
        normal = tuple(x / length for x in normal) if length else (0., 0., 0.)
        data.extend(struct.pack('<12fH', *normal, *tri[0], *tri[1], *tri[2], 0))
    return bytes(data)


def verify_stl(data, vertices, faces):
    assert struct.unpack_from('<I', data, 80)[0] == len(faces)
    assert len(data) == 84 + 50 * len(faces)
    maximum_error = 0.0
    decoded = []; decoded_faces = []
    for index, face in enumerate(faces):
        points = struct.unpack_from('<9f', data, 84 + index * 50 + 12)
        first = len(decoded)
        for j, source in enumerate(face):
            point = tuple(points[j * 3:j * 3 + 3])
            maximum_error = max(maximum_error, *(abs(x - y) for x, y in zip(point, vertices[source])))
            decoded.append(point)
        decoded_faces.append((first, first + 1, first + 2))
    assert maximum_error < .000005
    stats = mesh_stats(decoded, decoded_faces)
    assert stats['closed'] and stats['windingConsistent'] and stats['connectedComponents'] == 1
    assert stats['signedVolumeMm3'] > 0
    return {'float32MaxVertexErrorMm': maximum_error, **stats}


def write_preview(meshes, destination):
    """Two exact-mesh orthographic views per part; no CAD reshaping or AI image."""
    width, height = 960, 640
    pixels = bytearray([246, 248, 250] * (width * height))
    depth = [-float('inf')] * (width * height)
    right = (.70710678, -.70710678, 0.)
    up = (.40557979, .40557979, .81915204)
    camera = (-.57922797, -.57922797, .57357644)
    light = (-.3, -.5, 1.)
    ll = math.sqrt(dot(light, light)); light = tuple(x / ll for x in light)
    glyphs = {
        ' ': ['000'] * 7, '-': ['000', '000', '000', '111', '000', '000', '000'],
        '1': ['010','110','010','010','010','010','111'], '2': ['110','001','001','010','100','100','111'],
        '3': ['110','001','001','110','001','001','110'],
        'A': ['010','101','101','111','101','101','101'], 'B': ['110','101','101','110','101','101','110'],
        'C': ['011','100','100','100','100','100','011'], 'E': ['111','100','100','110','100','100','111'],
        'F': ['111','100','100','110','100','100','100'],
        'I': ['111','010','010','010','010','010','111'], 'J': ['001','001','001','001','101','101','010'],
        'K': ['101','101','110','100','110','101','101'], 'O': ['010','101','101','101','101','101','010'],
        'L': ['100','100','100','100','100','100','111'], 'N': ['101','111','111','111','111','111','101'],
        'P': ['110','101','101','110','100','100','100'], 'R': ['110','101','101','110','101','101','101'],
        'S': ['011','100','100','010','001','001','110'], 'T': ['111','010','010','010','010','010','010'],
        'V': ['101','101','101','101','101','101','010'], 'Y': ['101','101','101','010','010','010','010'],
    }
    def text(label, x, y, scale=2):
        for letter in label:
            for row, bits in enumerate(glyphs[letter]):
                for col, bit in enumerate(bits):
                    if bit == '1':
                        for yy in range(y + row * scale, y + (row + 1) * scale):
                            for xx in range(x + col * scale, x + (col + 1) * scale):
                                at = 3 * (yy * width + xx); pixels[at:at+3] = bytes((35, 47, 61))
            x += 4 * scale
    titles = ['KEY 1', 'KEY 2', 'KEY 3', 'JOYSTICK A', 'JOYSTICK B', 'COVER']
    for index, (vertices, faces) in enumerate(meshes):
        cell_x = index % 3 * 320; cell_y = index // 3 * 320
        text(titles[index], cell_x + 20, cell_y + 15)
        base = (235, 239, 243) if index < 3 else (225, 142, 167)
        for underside in (False, True):
            points = [(p[0], -p[1], -p[2]) if underside else p for p in vertices]
            projected = [(dot(p, right), dot(p, up), dot(p, camera)) for p in points]
            bb = bounds(projected); scale = min(140 / (bb[1][0] - bb[0][0]), 215 / (bb[1][1] - bb[0][1]))
            ox = cell_x + (160 if underside else 0) + 10 - bb[0][0] * scale
            oy = cell_y + 65 + bb[1][1] * scale
            screen = [(ox + p[0] * scale, oy - p[1] * scale, p[2]) for p in projected]
            text('FLIP' if underside else 'PRINT', cell_x + (175 if underside else 20), cell_y + 293)
            for face in faces:
                tri = [screen[j] for j in face]; a, b, c = tri
                area = (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
                if abs(area) < 1e-12: continue
                normal = cross(subtract(points[face[1]], points[face[0]]), subtract(points[face[2]], points[face[0]]))
                length = math.sqrt(dot(normal, normal))
                intensity = .58 + .42 * max(0., dot(normal, light) / length) if length else .58
                color = bytes(round(v * intensity) for v in base)
                for y in range(max(cell_y+48, math.floor(min(p[1] for p in tri))), min(cell_y+286, math.ceil(max(p[1] for p in tri))+1)):
                    for x in range(max(cell_x, math.floor(min(p[0] for p in tri))), min(cell_x+320, math.ceil(max(p[0] for p in tri))+1)):
                        u = ((b[0]-x-.5)*(c[1]-y-.5)-(b[1]-y-.5)*(c[0]-x-.5))/area
                        v = ((c[0]-x-.5)*(a[1]-y-.5)-(c[1]-y-.5)*(a[0]-x-.5))/area
                        w = 1-u-v
                        if min(u,v,w) < -1e-7: continue
                        z = u*a[2]+v*b[2]+w*c[2]; pos = y*width+x
                        if z > depth[pos]: depth[pos]=z; pixels[3*pos:3*pos+3]=color
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b''.join(b'\0' + bytes(pixels[y*width*3:(y+1)*width*3]) for y in range(height))
    destination.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>2I5B', width,height,8,2,0,0,0)) + chunk(b'IDAT',zlib.compress(raw,9)) + chunk(b'IEND',b''))


def extract(source, output):
    source_bytes = source.read_bytes()
    if sha(source_bytes) != EXPECTED_SOURCE_SHA256:
        raise ValueError('Source 3MF differs from the reviewed original project')
    output.mkdir(parents=True, exist_ok=True)
    records = []; meshes = []
    with zipfile.ZipFile(source) as archive:
        root = ET.fromstring(archive.read('3D/3dmodel.model'))
        if root.get('unit', 'millimeter') != 'millimeter': raise ValueError('Source unit must be millimeter')
        settings = ET.fromstring(archive.read('Metadata/model_settings.config'))
        names = {o.get('id'): o.find("metadata[@key='name']").get('value') for o in settings.findall('object')}
        objects = {o.get('id'):o for o in root.findall(C+'resources/'+C+'object')}
        items = {o.get('objectid'):o for o in root.findall(C+'build/'+C+'item')}
        for object_id, expected_name, filename in PARTS:
            if names.get(object_id) != expected_name: raise ValueError('Named original control does not match reviewed mapping')
            components = objects[object_id].findall(C+'components/'+C+'component')
            assert len(components) == 1
            comp = components[0]; member = comp.get(P+'path').lstrip('/')
            name = PurePosixPath(member)
            if name.is_absolute() or '..' in name.parts or '\\' in member: raise ValueError('Unsafe mesh member')
            model_bytes = archive.read(member); model = ET.fromstring(model_bytes)
            obj = next(o for o in model.findall(C+'resources/'+C+'object') if o.get('id') == comp.get('objectid'))
            mesh = obj.find(C+'mesh')
            raw = [tuple(float(v.get(k)) for k in ('x','y','z')) for v in mesh.find(C+'vertices')]
            faces = [tuple(int(t.get(k)) for k in ('v1','v2','v3')) for t in mesh.find(C+'triangles')]
            assert all(math.isfinite(x) for vertex in raw for x in vertex)
            assert all(0 <= i < len(raw) for face in faces for i in face)
            component_matrix = matrix(comp.get('transform')); build_matrix = matrix(items[object_id].get('transform'))
            placed = [transform(transform(p, component_matrix), build_matrix) for p in raw]
            bb = bounds(placed); offset = bb[0]
            vertices = [subtract(p, offset) for p in placed]
            before = mesh_stats(raw, faces); after = mesh_stats(vertices, faces)
            assert before['closed'] and before['windingConsistent'] and before['connectedComponents'] == 1
            assert after['closed'] and after['windingConsistent'] and after['connectedComponents'] == 1
            assert abs(after['signedVolumeMm3'] / before['signedVolumeMm3'] - 1) < 1e-7
            data = stl_bytes(vertices, faces, filename); verification = verify_stl(data, vertices, faces)
            (output/filename).write_bytes(data)
            records.append({'file':filename,'sourceObjectId':object_id,'sourceName':expected_name,'quantity':1,
                            'sourceModelMember':member,'sourceModelSha256':sha(model_bytes),
                            'sourceMeshObjectId':comp.get('objectid'),'componentTransform3mf':component_matrix,
                            'buildTransform3mf':build_matrix,'removedPlateTranslationMm':offset,
                            'exportBoundsMm':bounds(vertices),'sourceVolumeMm3':before['signedVolumeMm3'],
                            'bytes':len(data),'sha256':sha(data),'verification':verification})
            meshes.append((vertices, faces))
    write_preview(meshes, output/'parts-preview.png')
    report = {'format':'hachimo-original-print-parts-v1','unit':'millimeter',
              'sourceProjectBasename':'user-p1s-white-orange-two-plates.3mf','sourceProjectSha256':sha(source_bytes),
              'sourceCopyrightDesignerLicenseMetadata':'blank; preserve repository upstream attribution and license, no new license inferred',
              'upstreamProject':'https://github.com/YizhengWw/HachimoDock','upstreamAuthor':'Yizheng Wang',
              'geometryPolicy':'Original indexed vertices and triangles retained; original component then build transform applied; translation to XYZ minimum only; binary STL float32 quantization checked.',
              'sourcePrinterProfileAndPrivateMetadataPublished':False,'physicalPrintAndFitVerified':False,
              'parts':records,'preview':{'file':'parts-preview.png','sha256':sha((output/'parts-preview.png').read_bytes()),
                                       'description':'Exact exported mesh views: PRINT follows the source plate orientation, FLIP is its reverse. Colors are a display legend, not source material assignments.'}}
    (output/'source-and-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'parts':len(records),'quantities':{r['file']:r['quantity'] for r in records},'allClosed':True,'allSingleComponent':True,'unit':'millimeter'}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'reference/user-p1s-white-orange-two-plates.3mf')
    parser.add_argument('--output',type=Path,default=ROOT/'print-parts')
    args = parser.parse_args()
    extract(args.source,args.output)


if __name__ == '__main__':main()
