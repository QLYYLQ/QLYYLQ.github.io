#!/usr/bin/env python3
"""Verify archival fidelity, linked evidence and published numerical summaries.

Uses the standard library, no network, no mutation. Site-wide links are checked
separately by check_site.py. Optional --source verifies original provenance.
"""
import argparse
import base64
import csv
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'training-dynamics'


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Content(HTMLParser):
    def __init__(self, main_only=False):
        super().__init__()
        self.main_only = main_only
        self.active = not main_only
        self.text, self.images = [], []
    def handle_starttag(self, tag, attrs):
        if tag in {'article', 'main'}:
            self.active = True
        if tag == 'img' and self.active:
            self.images.append(dict(attrs)['src'])
    def handle_endtag(self, tag):
        if tag in {'article', 'main'} and self.main_only:
            self.active = False
    def handle_data(self, text):
        if self.active:
            self.text.append(text)


def check(source):
    manifest=json.loads((SITE/'manifest.json').read_text())
    actual={str(p.relative_to(SITE)) for p in SITE.rglob('*') if p.is_file() and p.name!='manifest.json'}
    assert set(manifest)==actual, 'Manifest file inventory mismatch'
    for rel, m in manifest.items():
        data=(SITE/rel).read_bytes()
        assert len(data)==m['bytes'] and sha(data)==m['sha256'], f'Manifest mismatch: {rel}'
        if Path(rel).suffix not in {'.png','.pdf','.jpg'}:
            text=gzip.decompress(data).decode() if rel.endswith('.gz') else data.decode()
            assert not any(term in text for term in ['/Users/qly','/home/hadoop-aipnlp','/mnt/','luyuquan','sankuai.com','meituan.com','BEGIN PRIVATE KEY']), f'Unprocessed machine location: {rel}'
            if rel.endswith('.json'):
                json.loads(text)
    for slug, count in [('overview',22),('p80-aime',8)]:
        before, after = Content(True), Content(True)
        before.feed((SITE/f'sources/{slug}.html.txt').read_text())
        after.feed((SITE/f'{slug}.html').read_text())
        assert ''.join(before.text)==''.join(after.text), f'Research body changed: {slug}'
        assert len(before.images)==len(after.images)==count
        for old,new in zip(before.images,after.images):
            assert base64.b64decode(old.split(';base64,')[1])==(SITE/new).read_bytes(), f'Figure changed: {new}'
    missing=json.loads((SITE/'unbundled-references.json').read_text())
    assert len(missing['overview'])==90 and not missing['p80-aime']
    records=json.loads((SITE/'reports.json').read_text())
    assert len(records)==8
    for r in records:
        assert (SITE/(r['slug']+'.html')).is_file()
        assert (SITE/('sources/'+r['slug']+'.md')).is_file()
    # Check primary numbers against their source table, not a duplicate fixture.
    cells=list(csv.DictReader((SITE/'evidence/p80_aime_report_20261025/statistics/cells.csv').open()))
    assert len(cells)==32
    index=(SITE/'index.html').read_text()
    primary_labels=['allenai__Olmo-3-7B-RL-Zero-Math-step_1600', 'allenai__Olmo-3-7B-RL-Zero-Math', 'ours__lin_elem__Math_p80__', 'ours__qh_maglin__Math_p80__', 'ours__qh_hybrid_k4096__Math_p80']
    for label in primary_labels:
        row=next(r for r in cells if r['label']==label)
        assert f"<td>{100*float(row['pass1']):.2f}%</td><td>{100*float(row['pass16']):.2f}%</td>" in index, f'Landing summary differs from source: {label}'
    # C7 is its own snapshot and must not duplicate a required cell.
    required=SITE/'evidence/followup_20261025_required'
    optional=SITE/'evidence/followup_20261025_C7'
    aime=list(csv.DictReader((required/'followup_cells_aime.csv').open()))
    math=list(csv.DictReader((required/'followup_cells_math500.csv').open()))
    c7=list(csv.DictReader((optional/'followup_cells_aime.csv').open()))
    assert (len(aime),len(math),len(c7))==(900,2000,90)
    assert len({r['label'] for r in aime+math})==14
    assert not ({r['label'] for r in aime} & {r['label'] for r in c7})
    summary=json.loads((optional/'summary.json').read_text())
    assert sum(int(r['correct']) for r in c7)==summary['correct_samples']==645
    assert sum(int(r['n_samples']) for r in aime+math)==44800
    assert abs(sum(float(r['pass16']) for r in c7)/90-summary['pass16'])<1e-12
    overlaps=list(csv.DictReader((required/'dolci_overlap.csv').open()))
    assert len(overlaps)==90
    # Original digests refer to untouched inputs, including members inside ZIPs.
    provenance=json.loads((SITE/'provenance.json').read_text())
    for dest,m in provenance.items():
        assert sha((SITE/dest).read_bytes())==m['published_sha256'], f'Snapshot changed: {dest}'
    if source:
        for dest,m in provenance.items():
            rel=m['source']
            first=rel.split('/')[0]
            if first.startswith('followup_'):
                with zipfile.ZipFile(source/(first+'.zip')) as archive:
                    data=archive.read('training_dynamics/'+rel)
            else:
                data=(source/rel).read_bytes()
            assert sha(data)==m['original_sha256'], f'Original provenance mismatch: {rel}'
    print(f'训练动力学检查通过：8 份阅读页，30 张原图逐字节一致，{len(manifest)} 个文件哈希匹配；历史缺失引用、研究正文、补充表格与来源校验通过。')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path)
    check(parser.parse_args().source)
