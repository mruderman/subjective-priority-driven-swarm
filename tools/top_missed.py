#!/usr/bin/env python3.11
"""Print top-N files by missed lines from a coverage XML (cobertura-style).

Usage: python3.11 tools/top_missed.py coverage-all.xml --top 10
"""
import sys
from xml.etree import ElementTree as ET
from collections import defaultdict
from pathlib import Path


def parse(path):
    tree = ET.parse(path)
    root = tree.getroot()
    files = defaultdict(lambda: {'total':0,'covered':0})
    for cls in root.findall('.//class'):
        filename = cls.get('filename')
        if not filename:
            continue
        lines = cls.findall('.//line')
        for l in lines:
            files[filename]['total'] += 1
            try:
                hits = int(l.get('hits','0'))
            except Exception:
                hits = 0
            if hits>0:
                files[filename]['covered'] += 1
    results = []
    for f, d in files.items():
        missed = d['total'] - d['covered']
        pct = (d['covered']/d['total']*100) if d['total'] else 100.0
        results.append((missed, f, d['total'], d['covered'], round(pct,2)))
    results.sort(reverse=True)
    return results


def main(argv):
    if len(argv) < 2:
        print('Usage: top_missed.py coverage.xml [--top N]')
        return 2
    path = Path(argv[1])
    top = 10
    if '--top' in argv:
        try:
            top = int(argv[argv.index('--top')+1])
        except Exception:
            pass
    res = parse(path)
    print(f"Top {top} files by missed lines (missed, filename, total, covered, pct_covered):\n")
    for missed, f, total, covered, pct in res[:top]:
        print(f"{missed:4d}  {f:40s}  total={total:4d}  covered={covered:4d}  pct={pct:6.2f}%")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
