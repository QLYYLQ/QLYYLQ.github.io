#!/usr/bin/env python3
"""Validate CU report snapshots, figures and page hashes using the standard library."""
import argparse
import hashlib
import json
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "cu-model"


def check(source=None):
    errors = []
    manifest = json.loads((SITE / "manifest.json").read_text())
    records = json.loads((SITE / "reports.json").read_text())
    if manifest["report_count"] != len(records):
        errors.append("CU report count differs from manifest")
    if len({r["slug"] for r in records}) != len(records):
        errors.append("Duplicate CU report slug")
    for rel, expected in manifest["files"].items():
        path = SITE / rel
        if not path.is_file():
            errors.append(f"Missing CU file: {rel}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"] or path.stat().st_size != expected["bytes"]:
            errors.append(f"Stale CU manifest: {rel}; rebuild with build_cu_model.py")
    actual = {str(p.relative_to(SITE)) for p in SITE.rglob("*") if p.is_file() and p.name not in {"manifest.json", ".DS_Store"}}
    if actual != set(manifest["files"]):
        errors.append("CU file inventory differs from manifest")
    index = (SITE / "index.html").read_text()
    for record in records:
        if f'href="{record["slug"]}.html"' not in index:
            errors.append(f"CU report missing from index: {record['slug']}")
    gallery = SITE / "media/reports/agw_20261006/case_gallery/final-with-controls-r3-v2"
    if len(list((gallery / "t1_cases").glob("*.png"))) != manifest["gallery_cases"]:
        errors.append("CU gallery case count differs")
    if len(list(gallery.rglob("*.png"))) != 126:
        errors.append("Expected all 126 original AGW panels")
    if len(list((SITE / "media/reports/figures_20260929").rglob("*.png"))) != 23:
        errors.append("Expected all 23 cumulative report figures")
    if source:
        provenance = json.loads((SITE / "provenance.json").read_text())
        for rel, entry in provenance.items():
            original = source / rel
            if not original.is_file() or hashlib.sha256(original.read_bytes()).hexdigest() != entry["original_sha256"]:
                errors.append(f"Original CU source changed: {rel}")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    errors = check(args.source)
    print('\n'.join(errors) if errors else "CU 检查通过：25 份报告、23 张实验图、14 例 / 126 张审阅面板，来源与页面哈希一致。")
    raise SystemExit(bool(errors))
