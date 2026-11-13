#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["Markdown==3.7"]
# ///
"""Import local CU research and build its static reading pages.

uv run scripts/build_cu_model.py --source /path/to/cu_model
uv run scripts/build_cu_model.py  # rebuild from the checked-in snapshots
The original research directory is read-only. No network access during rendering.
"""
import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import struct
from urllib.parse import unquote, urlsplit

import markdown

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "cu-model"
RECORDS = json.loads((SITE / "reports.json").read_text())
DOCS = {r["source"]: r["slug"] + ".html" for r in RECORDS}
GALLERY = "reports/agw_20261006/case_gallery/final-with-controls-r3-v2"
SNAPSHOTS = SITE / "sources"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_text(text):
    """Remove machine/account locations; keep numerical results and relative evidence paths."""
    text = text.replace("/mnt/dolphinfs/ssd_pool/docker/user/hadoop-aipnlp/RPG/luyuquan", "$DATA_ROOT")
    text = text.replace("/mnt/hdfs/checkpoint/EXE/luyuquan", "$CHECKPOINT_ROOT")
    text = text.replace("/home/hadoop-aipnlp", "$REMOTE_HOME")
    text = text.replace("/Users/qly", "$LOCAL_HOME").replace("~/QLY", "$LOCAL_HOME/QLY")
    text = re.sub(r"https?://[\w.-]*(?:sankuai|meituan)\.com[^\s<>`）)]*", "[内部作业地址已省略]", text)
    text = re.sub(r"\b(?:10|192\.168)\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?\b", "[内部地址]", text)
    return text


def import_sources(source):
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    provenance = {}
    for record in RECORDS:
        original = source / record["source"]
        raw = original.read_text(encoding="utf-8")
        cleaned = public_text(raw)
        dest = SNAPSHOTS / (record["slug"] + ".md")
        dest.write_text(cleaned, encoding="utf-8")
        provenance[record["source"]] = {
            "original_sha256": digest(original), "snapshot_sha256": digest(dest),
            "location_redaction": cleaned != raw,
        }
    # Only report figures, the reviewed gallery, and the small comparison tables.
    for rel in ["reports/figures_20260929", GALLERY, "grounding_comparison_20261030"]:
        for original in sorted((source / rel).rglob("*")):
            if not original.is_file() or original.suffix not in {".png", ".csv"}:
                continue
            dest = SITE / "media" / original.relative_to(source)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, dest)
            provenance[str(original.relative_to(source))] = {"original_sha256": digest(original)}
    original = source / GALLERY / "index.html"
    dest = SNAPSHOTS / "agw-gallery.html.txt"
    dest.write_text(public_text(original.read_text()), encoding="utf-8")
    provenance[GALLERY + "/index.html"] = {"original_sha256": digest(original)}
    (SITE / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")


def shell(title, body, crumb="研究报告"):
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="{html.escape(title, quote=True)} · CU Model 研究资料">
<title>{html.escape(title)} · CU Model</title>
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="../assets/site.css"><link rel="stylesheet" href="cu-model.css">
</head><body><a class="skip-link" href="#content">跳到正文</a><div class="wrap research-wrap">
<nav class="crumb" aria-label="面包屑"><a href="../">QLYYLQ</a><span>/</span><a href="./">CU Model</a><span>/</span><span>{html.escape(crumb)}</span></nav>
{body}
<footer class="site"><a href="./">CU Model</a><a href="./#reports">全部报告</a><a href="../">主页</a><a href="https://github.com/QLYYLQ/QLYYLQ.github.io">本站源码</a></footer>
</div></body></html>\n'''


class Relink(HTMLParser):
    """Map research-relative links to published pages; label unavailable local evidence."""
    def __init__(self, source, ids):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.ids = ids
        self.out = []
        self.anchor_stack = []
        self.missing = set()

    def target(self, value):
        url = urlsplit(html.unescape(value))
        if url.scheme or url.netloc:
            return value
        path = unquote(url.path)
        original = posixpath.normpath(posixpath.join(str(PurePosixPath(self.source).parent), path)) if path else self.source
        if original in DOCS:
            frag = unquote(url.fragment)
            if frag not in self.ids.get(original, set()):
                frag = ""
            return DOCS[original] + ("#" + frag if frag else "")
        if original == GALLERY + "/index.html":
            return "agw-gallery.html"
        asset = (SITE / "media" / original).resolve()
        if asset.is_relative_to(SITE / "media") and asset.is_file():
            return "media/" + original
        self.missing.add(value)
        return None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            mapped = self.target(attrs.get("href", ""))
            self.anchor_stack.append(mapped is not None)
            if mapped is None:
                self.out.append('<span class="unbundled" title="原报告引用；此证据文件未随本站发布">')
                return
            attrs["href"] = mapped
        if tag == "img":
            mapped = self.target(attrs.get("src", ""))
            if mapped is None:
                self.out.append('<p class="source-note">原报告配图未包含在本地副本中：' + html.escape(attrs.get("alt", "")) + '</p>')
                return
            attrs.update(src=mapped, loading="lazy", decoding="async")
            asset = SITE / mapped
            if asset.suffix == ".png":
                with asset.open("rb") as stream:
                    header = stream.read(24)
                width, height = struct.unpack(">II", header[16:24])
                attrs.update(width=str(width), height=str(height))
        if tag == "table":
            self.out.append('<div class="tablebox" tabindex="0" role="region" aria-label="报告数据表">')
        self.out.append("<" + tag + "".join(f' {k}="{html.escape(v or "", quote=True)}"' for k, v in attrs.items()) + ">")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor_stack:
            tag = "a" if self.anchor_stack.pop() else "span"
        self.out.append("</" + tag + ">")
        if tag == "table":
            self.out.append("</div>")

    def handle_data(self, data):
        self.out.append(data)

    def handle_entityref(self, name):
        self.out.append("&" + name + ";")

    def handle_charref(self, name):
        self.out.append("&#" + name + ";")


def build():
    groups = {}
    for record in RECORDS:
        groups.setdefault(record["group"], []).append(record)
    lists = []
    for group, records in groups.items():
        rows = ''.join(f'<li><div class="date">{r["date"]}</div><div><a class="t" href="{r["slug"]}.html">{html.escape(r["title"])}</a><div class="d">{html.escape(r["description"])}</div></div></li>' for r in records)
        lists.append(f'<div class="doc-group"><h3>{group}</h3><ul class="doclist">{rows}</ul></div>')
    index = SITE / "index.html"
    index.write_text(re.sub(r'<!-- REPORT_LIST_START -->.*?<!-- REPORT_LIST_END -->', '<!-- REPORT_LIST_START -->\n' + '\n'.join(lists) + '\n<!-- REPORT_LIST_END -->', index.read_text(), flags=re.S))
    rendered, ids = {}, {}
    for record in RECORDS:
        md = markdown.Markdown(extensions=["extra", "toc", "sane_lists"], extension_configs={"toc": {"toc_depth": "2-3"}})
        raw = (SNAPSHOTS / (record["slug"] + ".md")).read_text()
        # Page title is supplied by the site header; the source snapshot retains it.
        raw = re.sub(r"\A# [^\n]+\n", "", raw, count=1)
        body = md.convert(raw)
        rendered[record["source"]] = (body, md.toc)
        ids[record["source"]] = set(re.findall(r' id="([^"]+)"', body))
    unresolved = {}
    for record in RECORDS:
        body, toc = rendered[record["source"]]
        linker = Relink(record["source"], ids)
        linker.feed(body)
        unresolved[record["slug"]] = sorted(linker.missing)
        old = record["date"] < "2026-11-03"
        note = '这是按原日期保留的研究记录；后续方法选择以<a href="local-observation-brief.html">11 月 3 日路线</a>为准。' if old else '本页按 11 月 3 日更新的本地研究稿整理；方案、估算和待做实验沿用原文标记。'
        paired = record["slug"][:-6] if record["slug"].endswith("-brief") else record["slug"] + "-brief"
        related = next((r for r in RECORDS if r["slug"] == paired), None)
        alternate = f'<a href="{paired}.html">{html.escape(related["title"])}</a> · ' if related else ''
        body = f'''<header class="top"><div class="eyebrow">{record["date"]} · {record["group"]}</div>
<h1>{html.escape(record["title"])}</h1><p class="lead">{html.escape(record["description"])}</p>
<p class="source-note">{note}</p><p class="source-note">{alternate}<a href="sources/{record["slug"]}.md" download>下载 Markdown</a></p></header>
<details class="report-toc"><summary>目录 · 跳转到章节</summary>{toc}</details>
<main id="content" class="prose">{''.join(linker.out)}</main>
<aside class="source-note">来源：<code>{html.escape(record["source"])}</code>。正文保留原研究记录，机器路径已泛化；链接与配图适配本站。标记为虚线的引用未随本站发布。来源及页面校验值见 <a href="manifest.json">manifest</a>。</aside>'''
        (SITE / (record["slug"] + ".html")).write_text(shell(record["title"], body))
    # Retain every case and every control from the original gallery, with mobile-safe styling.
    gallery = (SNAPSHOTS / "agw-gallery.html.txt").read_text()
    gallery = gallery[gallery.index("<h1>"):]
    gallery = re.sub(r"<h1>.*?</h1>", "", gallery, count=1)
    gallery_ids = re.findall(r"<h2>([^<]+)</h2>", gallery)
    gallery = re.sub(r"<h2>([^<]+)</h2>", r'<h2 id="\1">\1</h2>', gallery)
    gallery = re.sub(r"<img ([^>]+)>", lambda m: '<img ' + m[1] + ' alt="AGW 案例原始审阅面板">', gallery)
    linker = Relink(GALLERY + "/index.html", ids)
    linker.feed(gallery)
    toc = ''.join(f'<li><a href="#{name}">{name}</a></li>' for name in gallery_ids)
    body = f'''<header class="top"><div class="eyebrow">2026-10-06 · 14 个案例 · 126 张原始审阅面板</div><h1>AGW 案例画廊</h1>
<p class="lead">逐例查看动作提议、受限观察与读取对照。保留原始审阅面板和失败分支。</p>
<p class="source-note">T1 是来源轨迹动作的离线代理；T2 的 strict 与事后适配分开看。完整目标屏与标注矩形是离线读取对照，不代表自主选区或在线任务成功。<a href="agw-results.html">先读实验设计与结果</a>。</p></header>
<details class="report-toc"><summary>选择案例</summary><ul>{toc}</ul></details>
<main id="content" class="prose gallery">{''.join(linker.out)}</main>'''
    (SITE / "agw-gallery.html").write_text(shell("AGW 案例画廊", body, "案例画廊"))
    (SITE / "unbundled-references.json").write_text(json.dumps(unresolved, ensure_ascii=False, indent=2) + "\n")
    files = {}
    for p in sorted(SITE.rglob("*")):
        if p.is_file() and p.name not in {"manifest.json", ".DS_Store"}:
            files[str(p.relative_to(SITE))] = {"sha256": digest(p), "bytes": p.stat().st_size}
    manifest = {"research_updated": "2026-11-03", "report_count": len(RECORDS), "gallery_cases": len(gallery_ids),
                "source_policy": "Local research snapshots; machine paths generalized. Original source hashes in provenance.json. Unavailable local references are labelled, not linked.", "files": files}
    (SITE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Built {len(RECORDS)} reports and {len(gallery_ids)} gallery cases; tracked {len(files)} files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.source:
        import_sources(args.source.resolve())
    build()
