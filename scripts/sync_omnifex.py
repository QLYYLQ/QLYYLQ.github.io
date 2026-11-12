#!/usr/bin/env python3
"""把 Omnifex 的 claude.ai artifact 本地副本同步到 omnifex/。

用法：python3 scripts/sync_omnifex.py <pcb_cad_gym_research/artifacts 目录>

只动页面外壳，正文不改：
- 去掉 claude.ai 下载时套在外面的那层 <html><head>…<body>；
- 没有 doctype 的页面补上 doctype、charset、viewport；
- 互相引用的 claude.ai artifact 链接改成站内相对链接。
每次同步把源文件和输出文件的 sha256 写进 omnifex/manifest.json。
"""
import hashlib
import json
import pathlib
import re
import sys

# 源文件名 -> (站内文件名, claude.ai artifact id)
PAGES = {
    "omnifex_progress.html": ("progress.html", "6NvXrEkq11p1oacy3Dvrmq"),
    "omnifex_task_sources.html": ("task-sources.html", "8nhGkYKYwhAJcbBwAHLLR2"),
    "omnifex_proposal_v2.html": ("proposal-v2.html", "3zowhsEogmzyMFHNhGunrK"),
    "omnifex_validation_report.html": ("validation-report.html", "Sa3GGATBuejjNoLcFC9sNG"),
}

HEAD = (
    '<!doctype html>\n<html lang="zh-CN">\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
)
# 个别页面在窄屏下被撑宽，只补 CSS，不动正文
CSS_PATCHES = {
    "progress.html": ".wrap > * { min-width: 0; }",
}
WRAPPER = re.compile(r"\A<!doctype html><html><head><meta charset=utf8>.*?</head><body>\n", re.S)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalise(text: str, site_name: str) -> str:
    stripped, n = WRAPPER.subn("", text, count=1)
    if n:
        body = stripped.rstrip()
        if body.endswith("</body></html>"):
            body = body[: -len("</body></html>")].rstrip()
        text = body + "\n"
    if not text.lstrip().lower().startswith("<!doctype"):
        text = HEAD + text
    if site_name in CSS_PATCHES:
        text = text.replace("</title>", "</title>\n<style>" + CSS_PATCHES[site_name] + "</style>", 1)
    for other, artifact_id in PAGES.values():
        text = re.sub(
            r'href="https://claude\.ai/artifact/' + artifact_id + r'(#[^"]*)?"',
            lambda m, s=other: f'href="{s}{m.group(1) or ""}"',
            text,
        )
    return text


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    src_dir = pathlib.Path(sys.argv[1]).expanduser()
    out_dir = pathlib.Path(__file__).resolve().parent.parent / "omnifex"
    manifest = []
    for src_name, (site_name, artifact_id) in PAGES.items():
        raw = (src_dir / src_name).read_bytes()
        out = normalise(raw.decode("utf-8"), site_name).encode("utf-8")
        (out_dir / site_name).write_bytes(out)
        manifest.append({
            "page": site_name,
            "source": src_name,
            "claude_artifact": f"https://claude.ai/artifact/{artifact_id}",
            "source_sha256": sha256(raw),
            "page_sha256": sha256(out),
            "bytes": len(out),
        })
        print(f"{src_name} -> omnifex/{site_name} ({len(out):,} B)")
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
