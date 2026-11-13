#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["Markdown==3.7"]
# ///
"""Publish local research snapshots. Source is read-only; no research is rerun.

uv run scripts/build_training_dynamics.py --source /path/to/training_dynamics
uv run scripts/build_training_dynamics.py  # rebuild from checked-in snapshots
"""
import argparse
import base64
import csv
import gzip
import hashlib
import html
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import posixpath
import re
from urllib.parse import unquote, urlsplit
import zipfile
import markdown

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'training-dynamics'
RECORDS = json.loads((SITE / 'reports.json').read_text())
DOCS = {r['source']: r['slug'] + '.html' for r in RECORDS}
DOCS.update({'FINAL_REPORT.md': 'overview.html', 'p80_aime_report_20261025/REPORT.md': 'p80-aime.html'})


def sha(data):
    return hashlib.sha256(data).hexdigest()


def public_text(text):
    for old, new in [('/mnt/dolphinfs/ssd_pool/docker/user/hadoop-aipnlp/RPG/luyuquan', '$DATA_ROOT'),
                     ('/mnt/hdfs/checkpoint/EXE/luyuquan', '$CHECKPOINT_ROOT'),
                     ('/mnt/hdfs/zw04mlnn01/checkpoint/EXE/luyuquan', '$CHECKPOINT_ROOT'),
                     ('/mnt/hdfs/zw04mlnn01/checkpoint/', '$CHECKPOINT_STORAGE/'),
                     ('/mnt/hdfs/checkpoint/', '$CHECKPOINT_STORAGE/'),
                     ('/home/hadoop-aipnlp', '$REMOTE_HOME'), ('/Users/qly', '$LOCAL_HOME')]:
        text = text.replace(old, new)
    text = re.sub(r'(?:https?://)?[\w.-]*(?:sankuai|meituan)\.com[^\s<>`"\'）)]*', '[内部地址已省略]', text)
    text = re.sub(r'\bpsx[a-z0-9]+(?:-worker-\d+)?\b', '[运行节点]', text)
    return text


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = set()

    def handle_starttag(self, tag, attrs):
        for key, val in attrs:
            if key in {'href', 'src'} and val and not val.startswith(('#', 'data:')) and not urlsplit(val).scheme:
                self.refs.add(unquote(urlsplit(val).path))


def import_sources(source):
    provenance = {}
    archives = {name: zipfile.ZipFile(source / (name + '.zip')) for name in ['followup_20261025_required', 'followup_20261025_C7']}

    def read(rel):
        first = rel.split('/')[0]
        if first in archives:
            return archives[first].read('training_dynamics/' + rel)
        return (source / rel).read_bytes()

    def save(rel, dest):
        raw = read(rel)
        if rel.endswith('.gz'):
            clean = gzip.compress(public_text(gzip.decompress(raw).decode()).encode(), mtime=0)
        elif Path(rel).suffix in {'.png', '.pdf', '.jpg'}:
            clean = raw
        else:
            clean = public_text(raw.decode()).encode()
        target = SITE / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(clean)
        provenance[dest] = {'source': rel, 'original_sha256': sha(raw), 'published_sha256': sha(clean), 'locations_generalized': clean != raw}

    evidence = set()
    for r in RECORDS:
        if r['slug'] == 'short-horizon':
            continue
        suffix = '.html.txt' if r['format'] == 'html' else '.md'
        save(r['source'], 'sources/' + r['slug'] + suffix)
        if r['format'] == 'html':
            parser = References()
            parser.feed(read(r['source']).decode())
            for ref in parser.refs:
                rel = posixpath.normpath(posixpath.join(posixpath.dirname(r['source']), ref))
                if not rel.startswith('../') and rel not in DOCS and (source / rel).is_file():
                    evidence.add(rel)
            md_source = r['source'].replace('.html', '.md')
            save(md_source, 'sources/' + r['slug'] + '.md')
    # Local compact evidence only. No model files, generation corpora, launch configs or logs.
    for folder in ['results_20261012/diag_eval_analysis', 'results_20261012/round2', 'results_20261012/round3', 'results_20261012/ws_full']:
        evidence.update(str(p.relative_to(source)) for p in (source / folder).glob('*') if p.suffix in {'.csv', '.json'})
    evidence.add('results_20261012/analyse_diag_eval.py')
    evidence.add('make_diag_ckpts.py')
    for p in (source / 'results_20261012/diag_manifests').glob('*.json'):
        evidence.add(str(p.relative_to(source)))
    required = 'followup_20261025_required/'
    evidence.update(required + n for n in ['followup_cells_aime.csv', 'followup_cells_math500.csv', 'run_records.json', 'rw_matched.csv', 'rw_drift.csv', 'rw_matched_draws.csv', 'rw_drift_draws.csv', 'dolci_overlap.csv', 'evidence/rw_validation.json', 'evidence/dolci_validation.json', 'evidence/required_delivery_validation.json'])
    evidence.update('followup_20261025_C7/' + n for n in ['summary.json', 'followup_cells_aime.csv', 'run_records.json', 'evidence/C7_aggregate_validation.json'])
    for rel in sorted(evidence):
        save(rel, 'evidence/' + rel)
    # Reuse an existing scientific figure for the project index.
    save('p80_aime_report_20261025/figures/04_paired_contrasts.png', 'media/paired-contrasts.png')
    (SITE / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n')
    for archive in archives.values():
        archive.close()


class PublishHTML(HTMLParser):
    def __init__(self, source, slug):
        super().__init__(convert_charrefs=False)
        self.source, self.slug = source, slug
        self.out, self.anchors, self.missing = [], [], set()
        self.image_count = 0

    def target(self, value):
        url = urlsplit(html.unescape(value))
        if url.scheme or url.netloc or not url.path:
            return value
        rel = posixpath.normpath(posixpath.join(posixpath.dirname(self.source), unquote(url.path)))
        if rel in DOCS:
            return DOCS[rel] + ('#' + url.fragment if url.fragment else '')
        if rel in {'README.md', 'p80_aime_report_20261025/README.md'}:
            return 'index.html#materials'
        target = (SITE / 'evidence' / rel).resolve()
        if target.is_relative_to(SITE / 'evidence') and target.is_file():
            return 'evidence/' + rel
        self.missing.add(value)
        return None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'a':
            mapped = self.target(a.get('href', ''))
            self.anchors.append(mapped is not None)
            if mapped is None:
                self.out.append('<span class="unbundled" title="此引用文件未包含在本地交付包，本站未收录">')
                return
            a['href'] = mapped
        if tag == 'img':
            src = a.get('src', '')
            if src.startswith('data:image/'):
                mime, encoded = src.split(';base64,', 1)
                extension = {'data:image/png':'png', 'data:image/svg+xml':'svg', 'data:image/jpeg':'jpg'}[mime]
                self.image_count += 1
                src = f'media/{self.slug}-{self.image_count:02d}.{extension}'
                (SITE / 'media').mkdir(exist_ok=True)
                (SITE / src).write_bytes(base64.b64decode(encoded))
            else:
                src = self.target(src)
            if src is None:
                self.out.append('<p class="archive-note">原始配图未随本站收录。</p>')
                return
            a.update(src=src, loading='lazy', decoding='async')
        if tag == 'table' and self.source.endswith('.md'):
            self.out.append('<div class="tablebox" tabindex="0" role="region" aria-label="数据表，可横向滚动">')
        self.out.append('<' + tag + ''.join(' ' + k + (f'="{html.escape(v, quote=True)}"' if v is not None else '') for k,v in a.items()) + '>')

    def handle_endtag(self, tag):
        if tag == 'a' and self.anchors:
            tag = 'a' if self.anchors.pop() else 'span'
        self.out.append('</' + tag + '>')
        if tag == 'table' and self.source.endswith('.md'):
            self.out.append('</div>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_decl(self, decl): self.out.append('<!' + decl + '>')
    def handle_data(self, data): self.out.append(data)
    def handle_entityref(self, name): self.out.append('&' + name + ';')
    def handle_charref(self, name): self.out.append('&#' + name + ';')
    def handle_comment(self, data): self.out.append('<!--' + data + '-->')


def shell(record, body, toc):
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{record['title']} · 训练动力学</title><meta name="description" content="{record['description']}">
<link rel="stylesheet" href="../assets/site.css"><link rel="stylesheet" href="training-dynamics.css"><link rel="icon" href="favicon.svg">
</head><body><a class="skip-link" href="#content">跳到正文</a><div class="wrap research-wrap">
<nav class="crumb" aria-label="面包屑"><a href="../">QLYYLQ</a> / <a href="./">训练动力学</a> / 研究记录</nav>
<header class="top"><div class="eyebrow">{record['date']} · {record['group']}</div><h1>{record['title']}</h1><p class="lead">{record['description']}</p>
<p class="source-note">按原研究日期归档；后续补充见<a href="./#reports">报告目录</a>。<a href="sources/{record['slug']}.md" download>Markdown</a></p></header>
<details class="report-toc"><summary>章节目录</summary>{toc}</details><main id="content" class="prose">{body}</main>
<footer class="site"><a href="./">训练动力学</a><a href="./#materials">资料与来源</a><a href="../">主页</a></footer></div></body></html>\n'''


def short_horizon():
    root = SITE / 'evidence/results_20261012'
    contrasts = json.loads((root / 'diag_eval_analysis/contrasts.json').read_text())['contrasts']
    mult = {(x['name'],x['bench']): x for x in json.loads((root / 'round3/diag_multiplicity.json').read_text())}
    selected = ['s40 mag c1.88: SR vs saved RNE', 's64 mag c1.19: SR vs saved RNE', 's40 mag c1.88 SR vs donor u40', 's64 mag c1.19 SR vs donor u64', 's40 dose c2 vs donor', 's40 dose c3 vs donor', 's40 orth(D) vs donor', 's40 orth vs target u80']
    text = '''# 密集续训与短程外推诊断

本页依据 10 月 12—13 日保存在本地的结果表整理，不是原总报告的一章，也未重新运行实验。研究对象为 runA 的密集续训与短程构造，任务为 MATH-500 和 GSM8K。u40、u64、u80 表示续训 optimizer update；它们不是官方轨迹的 step400、step1600 等步号。

## 如何阅读这些对照

SR 为随机舍入，RNE 为最近偶数舍入。`s40`、`s64` 表示使用的前缀末端。幅度 c 表示沿当前累计更新方向的缩放。`orth(D)` 使用真实后续更新 D 的正交分量，包含未来信息，只是诊断。`supp(D)` 和 `comp(D)` 也依赖真实后续更新，不能当作可部署的预测器。

配对区间来自原分析脚本的题级 bootstrap（10,000 次，seed=0）；MATH-500 为 500 题，GSM8K 为 1,319 题，每题 8 个样本。下面同时给出原始 95% 区间和后续保存的 Holm p 值，二者的校正口径不同。结果条件于已有样本，不覆盖独立训练或解码种子的全部不确定性。

## 幅度收益依赖前缀，舍入对照未检出稳定差异

s40 的 c1.88 SR 相对 donor 在两项任务的点估计均提高，但 MATH-500 的 Holm p=0.084。s64 的 c1.19 SR 相对 donor 的两个区间均跨零。两组 SR 与已保存 RNE 的比较也均跨零，不能据此把舍入方式当作主要改善来源。s40 的 c2、c3 对照在本面板较好；事后扫描幅度不等于已经确定一个可泛化的缩放规则。

## 选定对照的原始数值

差值和区间均为 pass@1 百分点；比较方向严格沿用表内 a−b。含未来信息的 orth(D) 行用于解释信息位置。

| 对照 | 任务 | 差值（pp） | 原始 95% 区间 | Holm p |
|---|---|---:|---:|---:|
'''
    for name in selected:
        for c in contrasts:
            if c['name'] == name:
                m=mult[(name,c['bench'])]
                text += f"| {name} | {c['bench']} | {100*c['diff']:+.2f} | [{100*c['lo']:+.2f}, {100*c['hi']:+.2f}] | {m['p_holm']:.4f} |\n"
    text += '''
## 证据与范围

真实后续更新的正交分量可在本批测量中接近 u80 的功能，但它使用了目标信息，不能据此计算训练节省。没有检出差异也不等于等价。此处只整理已有诊断；实际加速仍需相同后续训练预算下的学习曲线对照。

[完整 cell 指标](results_20261012/diag_eval_analysis/cells.csv) · [全部配对区间](results_20261012/diag_eval_analysis/contrasts.json) · [多重比较结果](results_20261012/round3/diag_multiplicity.json) · [续训曲线对照](results_20261012/round3/curve_contrasts.json) · [原分析脚本](results_20261012/analyse_diag_eval.py) · [构造定义](make_diag_ckpts.py)
'''
    (SITE / 'sources/short-horizon.md').write_text(text)


def followup_table():
    root=SITE / 'evidence/followup_20261025_required'
    records=json.loads((root/'run_records.json').read_text())['records']
    text='''<h2 id="cell-summary">逐题表重算的 14 格汇总</h2><p>以下为本站根据交付 CSV 重算的描述性汇总；每行保留自己的采样协议。A 组 pass@k 的 k=8，B/C/D 组 k=16。D 组为 61,440-token 完整输出，不能与 32k 条件直接视作等预算对照。B2 追加的 user 指令沿用上文定义。C7 在<a href="code-seed.html">独立补充页</a>。</p><div class="tablebox" tabindex="0" role="region" aria-label="14 个条件的结果"><table><thead><tr><th>条件 / 模型</th><th>任务</th><th>T / top_p</th><th>token 上限</th><th>pass@1</th><th>pass@k</th><th>撞限率</th></tr></thead><tbody>'''
    tables={bench:list(csv.DictReader((root/f'followup_cells_{bench}.csv').open())) for bench in ['aime','math500']}
    for r in records:
        rows=[x for x in tables[r['bench']] if x['label']==r['label']]
        assert len(rows)==(90 if r['bench']=='aime' else 500)
        samples=sum(int(x['n_samples']) for x in rows)
        p1=sum(int(x['correct']) for x in rows)/samples
        pk=sum(float(x['pass16' if r['bench']=='aime' else 'pass8']) for x in rows)/len(rows)
        cap=sum(int(x['cap_hits']) for x in rows)/samples
        label=r['checkpoint_label'].replace('allenai__Olmo-3-7B-RL-Zero-','').replace('ours__','').strip('_')
        text+=f"<tr><td>{r['cell_id']} · {html.escape(label)}</td><td>{r['bench']}</td><td>{r['temperature']} / {r['top_p']}</td><td>{r['max_tokens']:,}</td><td>{100*p1:.2f}%</td><td>{100*pk:.2f}%</td><td>{100*cap:.2f}%</td></tr>"
    return text+'</tbody></table></div>'


def build():
    short_horizon()
    unresolved={}
    for r in RECORDS:
        slug=r['slug']
        if r['format']=='html':
            raw=(SITE / f'sources/{slug}.html.txt').read_text()
        else:
            md=markdown.Markdown(extensions=['extra','toc','sane_lists'],extension_configs={'toc':{'toc_depth':'2-3'}})
            raw=md.convert(re.sub(r'\A# [^\n]+\n','',(SITE / f'sources/{slug}.md').read_text(),count=1))
        parser=PublishHTML(r['source'],slug)
        parser.feed(raw)
        body=''.join(parser.out)
        unresolved[slug]=sorted(parser.missing)
        if r['format']=='html':
            note = ('总报告保留 10 月 10 日状态；后续结果见项目目录。原图已保留，虚线引用表示本地交付包缺少该文件。' if slug=='overview' else '本页保留 10 月 25 日的实验结论与原图；后续补充评测见项目目录。')
            bar=f'<nav class="archive-nav" aria-label="站点导航"><a href="../">QLYYLQ</a> / <a href="./">训练动力学</a> / {r["date"]}<a href="./#reports">全部报告</a><a href="sources/{slug}.md" download>Markdown</a></nav><aside class="archive-note">{note}</aside>'
            body=body.replace('</head>','<link rel="stylesheet" href="archive.css"><link rel="icon" href="favicon.svg"></head>',1)
            body=body.replace('<body>','<body>'+bar,1)
            body=body.replace('正文与图片已内嵌，可离线阅读。证据与原始数据链接是数据包内的相对路径，在本文件所在目录中打开即可。','正文与原图随本站归档。实线链接可打开本站证据，虚线引用表示本地包缺少该文件。')
        else:
            if slug=='followup':
                body='<p class="archive-note">状态更新：本快照冻结时 C7 尚未完成；10 月 27 日稍后的 <a href="code-seed.html">C7 补充包</a>已完成验收。下文保留原快照状态。</p>'+body+followup_table()
            # Plain filenames in source prose receive explicit evidence links here.
            prefix='followup_20261025_C7' if slug=='code-seed' else 'followup_20261025_required'
            extras={'followup':['followup_cells_aime.csv','followup_cells_math500.csv','run_records.json','evidence/required_delivery_validation.json'], 'random-walk':['rw_matched.csv','rw_drift.csv','rw_matched_draws.csv','rw_drift_draws.csv','evidence/rw_validation.json'], 'dataset-overlap':['dolci_overlap.csv','evidence/dolci_validation.json'], 'code-seed':['summary.json','followup_cells_aime.csv','run_records.json','evidence/C7_aggregate_validation.json']}.get(slug,[])
            if extras:
                body+='<h2 id="evidence-files">随页证据</h2><ul>'+''.join(f'<li><a href="evidence/{prefix}/{p}">{p}</a></li>' for p in extras)+'</ul>'
            body=shell(r,body,md.toc)
        (SITE / (slug+'.html')).write_text(body)
    (SITE / 'unbundled-references.json').write_text(json.dumps(unresolved,ensure_ascii=False,indent=2)+'\n')
    index=SITE / 'index.html'
    rows=''.join(f'<li><div class="date">{r["date"]}</div><div><a class="t" href="{r["slug"]}.html">{r["title"]}</a><div class="d">{r["description"]}</div><div class="m">{r["group"]}</div></div></li>' for r in RECORDS)
    index.write_text(re.sub(r'<!-- REPORT_LIST_START -->.*?<!-- REPORT_LIST_END -->','<!-- REPORT_LIST_START -->\n<ul class="doclist">'+rows+'</ul>\n<!-- REPORT_LIST_END -->',index.read_text(),flags=re.S))
    manifest={str(p.relative_to(SITE)):{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(SITE.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    (SITE / 'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(f'Built {len(RECORDS)} reading pages; {len(manifest)} files; {sum(len(x) for x in unresolved.values())} unbundled references explicitly marked.')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path)
    args=ap.parse_args()
    if args.source:
        import_sources(args.source.resolve())
    build()
