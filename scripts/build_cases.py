#!/usr/bin/env python3
"""从 omnifex/cases/data/*.json 生成案例详情页和案例索引。

用法：python3 scripts/build_cases.py

每个案例一份 JSON，字段见 omnifex/cases/data/README.md。图片放 omnifex/cases/img/<id>/，
JSON 里写相对 omnifex/cases/ 的路径。正文是段落列表，支持 `代码`、**加粗**、[文字](链接)。
"""
import html
import json
import pathlib
import re
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES = ROOT / "omnifex" / "cases"
DATA = CASES / "data"

GROUPS = [
    ("grader", "判分本身会出错", "A 批 15 道里有 10 道的检查要修。误判有两个方向：太严会拒掉合理解，太松会放过错误解。题面本身也会写错。"),
    ("hard", "模型真做不到的", "修好检查后仍失败的几道里，最典型的三类：整板布线、板与外壳的空间关系、缩板。"),
    ("round2", "第二轮的新问题", "11-12 第二轮试做里最能说明问题的几道：检查全过但审计推翻、检查误判却另有真错、复核员判错、工作区泄题。"),
    ("source", "题源、加工与核验", "来自稚晖君仓库和专有格式重筛，逐例区分材料核实、题包加工、开发试做和构题撤回。"),
]
TONES = {"good", "bad", "warn", "info"}

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700'
         '&family=Noto+Serif+SC:wght@600;700&family=JetBrains+Mono:wght@400;500&display=swap">')
ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' "
        "height='32' fill='%23173a2d'/%3E%3Cpath d='M6 22h8l4-6h8' stroke='%23e0894c' stroke-width='3' fill='none'/%3E"
        "%3Ccircle cx='26' cy='16' r='3' fill='%23e0894c'/%3E%3C/svg%3E")
MODEL_VIEWER = '<script type="module" src="../../assets/vendor/model-viewer/model-viewer.min.js"></script>'

COMPARE_JS = """<script>
document.querySelectorAll('.compare input[type=range]').forEach(function (r) {
  var box = r.closest('.compare');
  function set() { box.style.setProperty('--pos', r.value + '%'); }
  r.addEventListener('input', set); set();
});
document.querySelectorAll('model-viewer').forEach(function (mv) {
  mv.addEventListener('load', function () { mv.classList.add('is-loaded'); });
  mv.addEventListener('error', function () { mv.classList.remove('is-loaded'); });
});
document.querySelectorAll('.mvtabs').forEach(function (tabs) {
  var mv = document.getElementById(tabs.dataset.for);
  tabs.querySelectorAll('button').forEach(function (b) {
    b.addEventListener('click', function () {
      if (b.getAttribute('aria-pressed') === 'true') return;
      tabs.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
      mv.classList.remove('is-loaded');
      mv.setAttribute('src', b.dataset.src);
      mv.setAttribute('alt', b.textContent + ' · 3D 模型');
      var fallback = mv.parentElement.querySelector('.model-fallback');
      if (b.dataset.poster) {
        mv.setAttribute('poster', b.dataset.poster);
        fallback.src = b.dataset.poster;
        fallback.alt = b.textContent + ' · 静态预览';
      }
      var cap = document.getElementById(tabs.dataset.for + '-cap');
      if (cap) cap.innerHTML = b.dataset.cap + '（可拖动旋转、滚轮缩放）';
    });
  });
});
</script>"""

CAMERA_LOCK_JS = """<script>
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('model-viewer[data-lock-camera]').forEach(function (mv) {
    function apply() {
      var orbit = mv.getAttribute('camera-orbit');
      if (orbit) mv.cameraOrbit = orbit;
      var target = mv.getAttribute('camera-target');
      if (target) mv.cameraTarget = target;
    }
    mv.addEventListener('load', apply);
    if (mv.loaded) apply();
  });
});
</script>"""


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    def link(match):
        target = html.unescape(match[2])
        if "\\" in target or any(ord(c) < 32 or ord(c) == 127 for c in target):
            return match[0]
        try:
            parts = urlsplit(target)
        except ValueError:
            return match[0]
        remote = parts.scheme in ("http", "https") and bool(parts.netloc) and parts.username is None
        relative = (not parts.scheme and not parts.netloc and not target.startswith("/")
                    and ":" not in target.split("/", 1)[0]
                    and parts.path.endswith((".html", ".json")))
        if not (remote or relative):
            return match[0]
        return '<a href="%s">%s</a>' % (html.escape(target, quote=True), match[1])
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+|[^)\s]+\.(?:html|json)[^)\s]*)\)", link, s)
    return s


def paras(items):
    out = []
    for p in items or []:
        if isinstance(p, list):
            out.append("<ul>" + "".join("<li>%s</li>" % inline(x) for x in p) + "</ul>")
        else:
            out.append("<p>%s</p>" % inline(p))
    return "\n".join(out)


def chip(text, tone=None, cls=None):
    c = ["chip"]
    if tone in TONES:
        c.append(tone)
    if cls:
        c.append(cls)
    return '<span class="%s">%s</span>' % (" ".join(c), html.escape(text))


def figure(f):
    src = html.escape(f["src"])
    alt = html.escape(f.get("alt", f.get("caption", "")))
    cap = f.get("caption")
    img = '<img src="%s" alt="%s" loading="lazy">' % (src, alt)
    if f.get("zoomable", True):
        img = '<a href="%s" title="打开原图">%s</a>' % (src, img)
    return ('<figure><div class="frame">%s</div>%s</figure>'
            % (img, "<figcaption>%s</figcaption>" % inline(cap) if cap else ""))


def compare(c, uid):
    return ('<figure><div class="compare" style="--pos:50%%">'
            '<img src="%s" alt="%s">'
            '<div class="after"><img src="%s" alt="%s"></div>'
            '<div class="bar"></div><span class="tag l">%s</span><span class="tag r">%s</span>'
            '<input type="range" min="0" max="100" value="50" aria-label="拖动对比" id="%s"></div>'
            '<figcaption>%s</figcaption></figure>'
            % (html.escape(c["before"]), html.escape(c.get("before_label", "改前")),
               html.escape(c["after"]), html.escape(c.get("after_label", "改后")),
               html.escape(c.get("before_label", "改前")), html.escape(c.get("after_label", "改后")),
               uid, inline(c.get("caption", "左右拖动对比。"))))


def model(m, uid):
    first = m["models"][0]
    tabs = ""
    if len(m["models"]) > 1:
        bs = []
        for i, x in enumerate(m["models"]):
            bs.append('<button type="button" aria-pressed="%s" data-src="%s" data-poster="%s" data-cap="%s">%s</button>'
                      % ("true" if i == 0 else "false", html.escape(x["src"]), html.escape(x.get("poster", "")),
                         html.escape(inline(x.get("caption", ""))), html.escape(x["label"])))
        tabs = '<div class="mvtabs" data-for="%s">%s</div>' % (uid, "".join(bs))
    attrs = ""
    for key, attr in (("orbit", "camera-orbit"), ("target", "camera-target"),
                      ("fov", "field-of-view"), ("min_orbit", "min-camera-orbit")):
        if m.get(key):
            attrs += ' %s="%s"' % (attr, html.escape(m[key]))
    if m.get("lock_camera"):
        attrs += ' data-lock-camera="1"'
    return ('<figure>%s<div class="model-frame"><model-viewer id="%s" class="mv" src="%s" poster="%s" camera-controls touch-action="pan-y" '
            'shadow-intensity="0.6" exposure="1.05" environment-image="neutral" interaction-prompt="none" '
            'alt="%s"%s></model-viewer><img class="model-fallback" src="%s" alt="%s" loading="lazy"></div>'
            '<figcaption id="%s-cap">%s</figcaption><p class="model-help">3D 加载前显示静态图。拖动旋转，双指或滚轮缩放。</p></figure>'
            % (tabs, uid, html.escape(first["src"]), html.escape(first.get("poster", "")),
               html.escape(m.get("alt", "3D 模型")), attrs,
               html.escape(first.get("poster", "")), html.escape(first.get("label", "3D 模型") + " · 静态预览"),
               uid, inline(first.get("caption", "") + "（可拖动旋转、滚轮缩放）")))


def checks_table(rows):
    body = []
    for r in rows:
        st = r.get("status", "pass" if r.get("ok") else "fail")
        tone = {"pass": "good", "fail": "bad", "miss": "warn", "fixed": "info"}.get(st, None)
        label = r.get("status_label") or {"pass": "通过", "fail": "不过", "miss": "漏判", "fixed": "已修"}.get(st, st)
        body.append('<tr><td class="id">%s</td><td>%s</td><td class="st">%s</td><td>%s</td></tr>'
                    % (html.escape(r.get("id", "")), inline(r.get("what", "")), chip(label, tone),
                       inline(r.get("note", ""))))
    return ('<div class="tablebox"><table><thead><tr><th>检查</th><th>查什么</th><th>结果</th><th>说明</th></tr>'
            '</thead><tbody>%s</tbody></table></div>' % "".join(body))


def page(title, body, desc, depth, extra_head=""):
    pre = "../" * depth
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>%s</title>
<meta name="description" content="%s">
<link rel="icon" href="%s">
%s
<link rel="stylesheet" href="%sassets/site.css">
%s
</head>
<body>
%s
</body>
</html>
""" % (html.escape(title), html.escape(desc), ICON, FONTS, pre, extra_head, body)


def load():
    cases = []
    for p in sorted(DATA.glob("*.json")):
        if p.name.startswith("_"):
            continue
        c = json.loads(p.read_text(encoding="utf-8"))
        c.setdefault("order", 999)
        cases.append(c)
    gi = {g[0]: i for i, g in enumerate(GROUPS)}
    cases.sort(key=lambda c: (gi.get(c["group"], 99), c["order"], c["id"]))
    return cases


def thumb(c):
    if (CASES / "img" / c["id"] / "thumb.jpg").exists():
        return "img/%s/thumb.jpg" % c["id"]
    t = c.get("thumb")
    if not t:
        for s in c.get("steps", []):
            for f in s.get("figures", []):
                t = f["src"]
                break
            if not t and s.get("compare"):
                t = s["compare"]["after"]
            if not t and s.get("model"):
                t = s["model"]["models"][0].get("poster")
            if t:
                break
    return t


def build_case(c, prev, nxt):
    uid = 0
    tags = [chip(d, cls="dom") for d in c.get("domain", [])]
    if c.get("level"):
        tags.append(chip(c["level"]))
    for v in c.get("verdict", []):
        tags.append(chip(v["label"], v.get("tone")))
    gname = dict((g[0], g[1]) for g in GROUPS).get(c["group"], "")
    head = """<header class="top">
  <div class="crumb"><a href="../../">QLYYLQ</a><span>/</span><a href="../">omnifex</a><span>/</span><a href="./">案例</a><span>/</span><span>%s</span></div>
  <div class="eyebrow">%s · %s</div>
  <h1>%s</h1>
  <div class="chips">%s</div>
  <div class="text" style="display:grid;gap:10px">%s</div>
</header>""" % (html.escape(c["id"]), html.escape(gname), html.escape(c["project"]), inline(c["title"]),
                "".join(tags), paras(c.get("summary", [])))

    parts = [head]
    if c.get("numbers"):
        parts.append('<div class="figures">%s</div>' % "".join(
            '<div><span class="v">%s%s</span><span class="k">%s</span></div>' % (
            inline(n["v"]), ("<small>/%s</small>" % inline(n["of"])) if n.get("of") else "", inline(n["k"]))
            for n in c["numbers"]))
    t = c.get("task")
    if t:
        rows = []
        for k, v in t.get("rows", []):
            val = paras(v) if isinstance(v, list) else inline(v)
            rows.append('<div class="k">%s</div><div>%s</div>' % (html.escape(k), val))
        parts.append('<section><h2><span class="no">题</span>%s</h2>%s<div class="ticket">%s</div></section>'
                     % (html.escape(t.get("heading", "题目")), paras(t.get("intro", [])), "".join(rows)))
    steps = []
    for i, s in enumerate(c.get("steps", []), 1):
        inner = ['<div class="label">%s</div><h3>%s</h3>' % (html.escape(s.get("label", "")), inline(s["title"]))]
        if s.get("text"):
            inner.append('<div class="text">%s</div>' % paras(s["text"]))
        if s.get("compare"):
            uid += 1
            inner.append(compare(s["compare"], "cmp%d" % uid))
        figs = s.get("figures", [])
        if figs:
            if s.get("figrow") and len(figs) > 1:
                inner.append('<div class="figrow">%s</div>' % "".join(figure(f) for f in figs))
            else:
                inner.extend(figure(f) for f in figs)
        if s.get("model"):
            uid += 1
            inner.append(model(s["model"], "mv%d" % uid))
        if s.get("checks"):
            inner.append(checks_table(s["checks"]))
        if s.get("after_text"):
            inner.append('<div class="text">%s</div>' % paras(s["after_text"]))
        steps.append('<li class="step"><div class="num">%02d</div><div class="main">%s</div></li>' % (i, "".join(inner)))
    if steps:
        parts.append('<section><h2><span class="no">过程</span>一步一步</h2><ol class="steps">%s</ol></section>'
                     % "".join(steps))
    if c.get("lesson"):
        parts.append('<div class="lesson"><div class="eyebrow">看点</div>%s</div>' % paras(c["lesson"]))
    if c.get("sources"):
        items = []
        for s in c["sources"]:
            if s.startswith("http"):
                items.append('<span><a href="%s">%s</a></span>' % (html.escape(s), html.escape(s)))
            else:
                items.append("<span>%s</span>" % html.escape(s))
        parts.append('<section><h3>出处</h3><div class="srcs">%s</div><p class="muted" style="font-size:.84rem">'
                     'C/ 指 Omnifex 工程里的 data/answer_mining_20261107/construct/；其余 data/ 路径相对项目根目录，'
                     '为本地证据索引。原生文件渲染与按证据绘制的示意图在各图注中区分。</p></section>' % "".join(items))
    pg = []
    pg.append('<a href="%s.html"><span class="eyebrow">上一个</span><span>%s</span></a>'
              % (prev["id"], html.escape(prev["short"])) if prev else "<span></span>")
    pg.append('<a href="%s.html"><span class="eyebrow">下一个</span><span>%s</span></a>'
              % (nxt["id"], html.escape(nxt["short"])) if nxt else "<span></span>")
    parts.append('<nav class="pager">%s</nav>' % "".join(pg))
    parts.append('<footer class="site"><a href="./">全部案例</a><a href="../">Omnifex</a><a href="../../">QLYYLQ</a></footer>')
    has_model = any(s.get("model") for s in c.get("steps", []))
    has_lock = any((s.get("model") or {}).get("lock_camera") for s in c.get("steps", []))
    scripts = COMPARE_JS + (("\n" + CAMERA_LOCK_JS) if has_lock else "")
    body = '<div class="wrap">%s</div>\n%s' % ("\n".join(parts), scripts)
    return page("%s · %s" % (c["short"], c["project"]), body, c.get("description", c["short"]), 2,
                MODEL_VIEWER if has_model else "")


def build_index(cases):
    parts = ["""<header class="top">
  <div class="crumb"><a href="../../">QLYYLQ</a><span>/</span><a href="../">omnifex</a><span>/</span><span>案例</span></div>
  <div class="eyebrow">Omnifex · 试做和题源案例</div>
  <h1>Omnifex 案例</h1>
  <p class="lead">基准仿照 SWE-bench：从开源硬件仓库的真实修订里取“改前状态 + 需求 + 上游答案”，让 agent 在原生 KiCad / CAD 文件上完成需求，再用自动检查判分。试做案例按实际顺序展开题目、模型提交、自动检查和复核；新题源案例说明版本变化与待验证的条件。配图包含原生文件渲染和按证据绘制的示意图。</p>
</header>"""]
    by = {}
    for c in cases:
        by.setdefault(c["group"], []).append(c)
    for gid, gname, gdesc in GROUPS:
        cs = by.get(gid, [])
        if not cs:
            continue
        cards = []
        for c in cs:
            t = thumb(c)
            pic = ('<div class="pic"><img src="%s" alt="" loading="lazy"></div>' % html.escape(t)) if t else \
                '<div class="pic none">文字案例</div>'
            vs = "".join(chip(v["label"], v.get("tone")) for v in c.get("verdict", [])[:2])
            doms = "".join(chip(d, cls="dom") for d in c.get("domain", []))
            cards.append('<a class="card" href="%s.html">%s<div class="body"><span class="id">%s</span>'
                         '<span class="ttl">%s</span><span class="proj">%s</span><div class="chips">%s%s</div></div></a>'
                         % (c["id"], pic, html.escape(c["id"]), html.escape(c["short"]), html.escape(c["project"]),
                            doms, vs))
        parts.append('<section class="cgroup"><h2>%s<span class="no">%d 例</span></h2><p>%s</p><div class="cards">%s</div></section>'
                     % (html.escape(gname), len(cs), html.escape(gdesc), "".join(cards)))
    parts.append('<footer class="site"><a href="../">Omnifex</a><a href="../progress.html">进展页</a><a href="../../">QLYYLQ</a></footer>')
    body = '<div class="wrap">%s</div>' % "\n".join(parts)
    return page("Omnifex 案例", body, "Omnifex 基准试做和题源案例，带原生文件渲染图。", 2)


def main():
    cases = load()
    for i, c in enumerate(cases):
        prev = cases[i - 1] if i > 0 else None
        nxt = cases[i + 1] if i + 1 < len(cases) else None
        (CASES / ("%s.html" % c["id"])).write_text(build_case(c, prev, nxt), encoding="utf-8")
    (CASES / "index.html").write_text(build_index(cases), encoding="utf-8")
    project_index = ROOT / "omnifex" / "index.html"
    project_text = project_index.read_text(encoding="utf-8")
    project_text, count = re.subn(
        r'data-case-count="\d+">\d+ 个案例',
        'data-case-count="%d">%d 个案例' % (len(cases), len(cases)), project_text,
    )
    if count != 1:
        raise ValueError("项目页应有且只有一个 data-case-count 案例计数")
    project_index.write_text(project_text, encoding="utf-8")
    print("built %d cases" % len(cases))


if __name__ == "__main__":
    main()
