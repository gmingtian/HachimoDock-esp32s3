"""Check an actual KiCad-exported schematic netlist against native PCB pads."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from pathlib import PureWindowsPath

from build_design import ROOT, STEM


def normalize_export_paths(tree):
    """Keep native connectivity intact while removing machine-local CAD paths."""
    changed = False
    nodes = list(tree.findall('./design/source')) + list(tree.findall('./libraries/library/uri'))
    for node in nodes:
        text = node.text or ''
        if Path(text).is_absolute() or PureWindowsPath(text).is_absolute():
            node.text = PureWindowsPath(text).name if '\\' in text else Path(text).name
            changed = True
    return changed


def compare_netlist(tree, pads):
    expected = {}
    for p in pads:
        key = (p['ref'], p['pin'])
        if key in expected and expected[key] != p['net']:
            raise ValueError(f'PCB has conflicting repeated pin: {key}')
        expected[key] = p['net']
    components = [c for c in tree.findall('./components/comp') if not c.get('ref').startswith('#')]
    actual_refs = {c.get('ref') for c in components}
    if actual_refs != {r for r, p in expected}:
        raise ValueError('Schematic component set differs from the PCB')
    libparts = {(p.get('lib'), p.get('part')): {n.get('num') for n in p.findall('./pins/pin')}
                for p in tree.findall('./libparts/libpart')}
    universe = set()
    for c in components:
        source = c.find('libsource')
        for number in libparts[(source.get('lib'), source.get('part'))]:
            universe.add((c.get('ref'), number))
    if universe != set(expected):
        raise ValueError(f'Schematic pin set differs: {universe ^ set(expected)}')
    actual = {}
    for net in tree.findall('./nets/net'):
        name = net.get('name').lstrip('/')
        nodes = net.findall('node')
        if name.startswith('unconnected-'):
            if len(nodes) != 1:
                raise ValueError('An unconnected net contains multiple nodes')
            name = ''
        for n in nodes:
            if n.get('ref').startswith('#'):continue  # Virtual power annotation.
            key = (n.get('ref'), n.get('pin'))
            if key in actual:
                raise ValueError(f'Pin appears more than once in native netlist: {key}')
            actual[key] = name
    for key, net in expected.items():
        if actual.get(key, '') != net:
            raise ValueError(f'{key}: PCB={net!r}, schematic={actual.get(key)!r}')
    if set(actual) - set(expected):
        raise ValueError('Unexpected schematic nodes')
    return {'components': len(actual_refs), 'uniquePins': len(expected), 'physicalPads': len(pads),
            'connectedUniquePins': sum(bool(n) for n in expected.values()),
            'netCount': len({n for n in expected.values() if n})}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=ROOT / 'output')
    args = parser.parse_args(); out = args.directory
    audit = json.loads((out / 'electrical-audit.json').read_text())
    board = out / f'{STEM}.kicad_pcb'
    board_sha = hashlib.sha256(board.read_bytes()).hexdigest()
    if board_sha != audit['boardSha256']:
        raise SystemExit('Native PCB audit is stale')
    erc = json.loads((out / 'schematic-erc.json').read_text())
    if erc.get('source') != f'{STEM}.kicad_sch' or any(s.get('violations') for s in erc['sheets']):
        raise SystemExit('Native schematic ERC is missing or contains violations')
    netlist_path = out / 'schematic-netlist.xml'
    netlist = ET.parse(netlist_path)
    report = compare_netlist(netlist.getroot(), audit['nativeElectricalPads'])
    if normalize_export_paths(netlist.getroot()):
        netlist.write(netlist_path, encoding='utf-8', xml_declaration=True)
    report.update(result='PASS', boardSha256=board_sha,
                  schematicSha256=hashlib.sha256((out / f'{STEM}.kicad_sch').read_bytes()).hexdigest(),
                  netlistSha256=hashlib.sha256((out / 'schematic-netlist.xml').read_bytes()).hexdigest(),
                  ercSha256=hashlib.sha256((out / 'schematic-erc.json').read_bytes()).hexdigest(),
                  ercViolations=0,
                  scope='Carrier module interfaces; module internals and automatic PCB UUID relinking excluded')
    (out / 'schematic-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
