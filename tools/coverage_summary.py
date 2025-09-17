#!/usr/bin/env python3.11
"""Parse coverage XML files and produce a summary table.

Usage:
  python3.11 tools/coverage_summary.py --unit coverage-unit.xml --integration coverage-integration.xml --e2e coverage-e2e.xml --all coverage-all.xml

Produces `coverage-summary.md` and `coverage-summary.json` in the repo root.
"""
import argparse
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


def parse_coverage_xml(path: Path):
    if not path.exists():
        return None
    tree = ET.parse(path)
    root = tree.getroot()
    result = {}
    # coverage.py / cobertura puts totals as attributes on the root
    lv = root.get("lines-valid")
    lc = root.get("lines-covered")
    lr = root.get("line-rate")
    if lv is not None and lc is not None and lr is not None:
        try:
            result["lines-valid"] = int(lv)
            result["lines-covered"] = int(lc)
            result["line-rate"] = float(lr)
        except Exception:
            # fall back to computing from <line> elements below
            lv = lc = lr = None
    if not result:
        # older format or fallback: compute from <line> entries
        lines_valid = 0
        lines_covered = 0
        for l in root.findall(".//line"):
            lines_valid += 1
            if l.get("hits") and int(l.get("hits")) > 0:
                lines_covered += 1
        result["lines-valid"] = lines_valid
        result["lines-covered"] = lines_covered
        result["line-rate"] = (lines_covered / lines_valid) if lines_valid else 0.0
    # percent
    result["percent"] = round(result["line-rate"] * 100, 2)
    return result


def make_summary(unit, integration, e2e, allcov):
    data = {
        "unit": parse_coverage_xml(Path(unit)) if unit else None,
        "integration": parse_coverage_xml(Path(integration)) if integration else None,
        "e2e": parse_coverage_xml(Path(e2e)) if e2e else None,
        "all": parse_coverage_xml(Path(allcov)) if allcov else None,
    }
    return data


def write_outputs(data, out_md="coverage-summary.md", out_json="coverage-summary.json"):
    md_lines = [
        "# Coverage Summary",
        "",
        "| Category | Lines Covered | Lines Valid | Coverage % |",
        "|---|---:|---:|---:|",
    ]
    for k in ["unit", "integration", "e2e", "all"]:
        v = data.get(k)
        if not v:
            md_lines.append(f"| {k} | - | - | - |")
        else:
            md_lines.append(
                f"| {k} | {v['lines-covered']} | {v['lines-valid']} | {v['percent']}% |"
            )
    md = "\n".join(md_lines) + "\n"
    with open(out_md, "w") as f:
        f.write(md)
    with open(out_json, "w") as f:
        json.dump(data, f, indent=2)
    print(md)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--unit")
    p.add_argument("--integration")
    p.add_argument("--e2e")
    p.add_argument("--all")
    args = p.parse_args(argv)
    data = make_summary(args.unit, args.integration, args.e2e, args.all)
    write_outputs(data)


if __name__ == "__main__":
    main()
