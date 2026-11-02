"""Read exported EasyEDA Pro archives while retaining their original units (mil)."""
import json
import zipfile


def read_archive(path):
    result = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.endswith('.epru'):
                continue
            document = None
            for line in archive.read(name).decode('utf-8').splitlines():
                if not line.startswith('{') or '||' not in line:
                    continue
                parts = line.split('||', 1)
                if not parts[1].rstrip('|'):
                    continue
                head, value = json.loads(parts[0]), json.loads(parts[1].rstrip('|'))
                if head['type'] == 'DOCHEAD':
                    document = {'head': value, 'records': []}
                    result[value['uuid']] = document
                elif document is not None:
                    document['records'].append((head, value))
    return result


def pads(document):
    return [dict(value, source_id=head['id']) for head, value in document['records']
            if head['type'] == 'PAD']


def symbol_pins(document):
    attributes = {}
    for head, value in document['records']:
        if head['type'] == 'ATTR' and value['key'] in ['Pin Name', 'Pin Number']:
            attributes.setdefault(value['parentId'], {})[value['key']] = value['value']
    return {value['Pin Number']: value['Pin Name'] for value in attributes.values()}


def board_geometry(document):
    components, attributes, outline, holes = {}, {}, [], []
    for head, value in document['records']:
        kind = head['type']
        if kind == 'COMPONENT':
            components[head['id']] = dict(value, source_id=head['id'])
        elif kind == 'ATTR' and value['key'] in ['Designator', 'Footprint']:
            attributes.setdefault(value['parentId'], {})[value['key']] = value['value']
        elif kind == 'POLY' and value.get('layerId') == 11:
            outline.append(value['path'])
        elif kind == 'FILL' and value.get('layerId') == 12:
            path = value['path'][0]
            if len(path) == 10 and path[2:4] == ['ARC', -180]:
                holes.append({'x': (path[0] + path[4]) / 2,
                              'y': (path[1] + path[5]) / 2,
                              'diameter': abs(path[0] - path[4])})
    for key, component in components.items():
        component.update(attributes.get(key, {}))
    return {'components': {item['Designator']: item for item in components.values()},
            'outline': outline, 'holes': holes}
