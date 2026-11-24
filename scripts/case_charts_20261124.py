#!/usr/bin/env python3
"""生成 2026-11-24 新增案例的示意图（SVG）。

三个图都是按已有证据画的，不是渲染：
- moteus 得分构成 <- hp_moteus_c1_r11/checks/results_20261123/summary.json
- splitflap W3 环境依赖 <- splitflap_r2/run1/output/out/REPORT.md 第 2 节
- probe-stall 步数分配 <- probe_stall/run1/output/out/stats.json

用法：python3 scripts/case_charts_20261124.py
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG = ROOT / "omnifex" / "cases" / "img"

BG = "#0c1411"
FG = "#eceee6"
DIM = "#8d9891"
ORANGE = "#e6ad6a"
BLUE = "#7fb0dd"
GRAY = "#c2c7c9"
RED = "#ff3d6e"
AMBER = "#ffb000"
FONT = "JetBrains Mono, Menlo, monospace"


def head(w, h, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'font-family="{FONT}">\n<rect width="{w}" height="{h}" fill="{BG}"/>\n'
            f'<text x="40" y="52" fill="{FG}" font-size="26" font-weight="500">{title}</text>\n')


def moteus_scores(path):
    # 参考解 P1-P6 得分，满分 6/3/2/3/3/3；总和 10.508，加 80 底 = 90.51
    items = [
        ("P1 高边成对程度", 4.008, 6, ORANGE),
        ("P2 栅源主体线宽", 0.0, 3, RED),
        ("P3 不换层不打过孔", 2.0, 2, BLUE),
        ("P4 U2 电容贴近", 1.5, 3, AMBER),
        ("P5 NC 接地", 0.0, 3, RED),
        ("P6 版本下拉 100k", 3.0, 3, BLUE),
    ]
    w, h = 1200, 590
    x0, x1 = 300, 1080
    top, row = 120, 62
    out = [head(w, h, "moteus-c1 参考解（上游 r1.1 原板）的 20 分品味项：10.508")]
    out.append(f'<text x="40" y="92" fill="{DIM}" font-size="15">满分 6/3/2/3/3/3，80 分底 + 10.508 = 90.51；扣分项都对到上游做法或手册</text>\n')
    for i, (name, got, full, color) in enumerate(items):
        y = top + i * row
        out.append(f'<text x="40" y="{y + 18}" fill="{FG}" font-size="17">{name}</text>\n')
        wfull = (x1 - x0) * 0.55
        bw = wfull * got / full
        out.append(f'<rect x="{x0}" y="{y}" width="{wfull}" height="26" fill="#1b2620"/>\n')
        if bw > 0:
            out.append(f'<rect x="{x0}" y="{y}" width="{bw:.1f}" height="26" fill="{color}" fill-opacity="0.85"/>\n')
        label = f'{got:g} / {full}'
        out.append(f'<text x="{x0 + wfull + 16}" y="{y + 19}" fill="{FG}" font-size="17">{label}</text>\n')
    out.append(f'<text x="40" y="{top + 6 * row + 34}" fill="{DIM}" font-size="14">'
               f'数据：checks/results_20261123/summary.json 的 reference 一项。</text>\n')
    out.append(f'<text x="40" y="{top + 6 * row + 56}" fill="{DIM}" font-size="14">'
               f'P2、P5 上游自己没做（0.3 mm 线宽、NC 未接地）；P4 OUT 侧 0.601 mm 比 r1.0 的 0.415 mm 远。</text>\n')
    out.append("</svg>\n")
    p = IMG / "moteus-c1" / "weighted.svg"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(out), encoding="utf-8")
    print(p, p.stat().st_size)


def splitflap_env(path):
    # 同一块参考解：改前正常 100 / 空配置 95；改后两遍都 100
    w, h = 1200, 480
    out = [head(w, h, "同一块参考解，host KiCad 配置一空就从 100 掉到 95")]
    out.append(f'<text x="40" y="92" fill="{DIM}" font-size="15">W3 检查丝印间距与封装库一致性；改后把 KiCad 10 全局配置冻进题包，每轮复制到临时目录</text>\n')
    rows = [("改前", "宿主正常配置", 100, ORANGE), ("改前", "空 KICAD_CONFIG_HOME", 95, RED),
            ("改后", "宿主正常配置", 100, BLUE), ("改后", "空 KICAD_CONFIG_HOME", 100, BLUE)]
    x0 = 300
    scale = 6.2  # 每分像素
    top, row = 150, 70
    for i, (stage, env, score, color) in enumerate(rows):
        y = top + i * row
        out.append(f'<text x="40" y="{y + 24}" fill="{DIM}" font-size="15">{stage}</text>\n')
        out.append(f'<text x="92" y="{y + 24}" fill="{FG}" font-size="16">{env}</text>\n')
        bw = score * scale
        out.append(f'<rect x="{x0}" y="{y}" width="{bw:.1f}" height="34" fill="{color}" fill-opacity="0.85"/>\n')
        out.append(f'<text x="{x0 + bw + 14}" y="{y + 24}" fill="{FG}" font-size="18">{score}</text>\n')
    out.append(f'<line x1="{x0}" y1="{top - 16}" x2="{x0}" y2="{top + 4 * row - 20}" stroke="{DIM}" stroke-width="1"/>\n')
    out.append(f'<text x="40" y="{top + 4 * row + 30}" fill="{DIM}" font-size="14">'
               f'数据：splitflap_r2/run1/output/out/REPORT.md 第 2 节；改前空配置下 W3 从 pass 变 fail，'
               f'lib_footprint_issues 记 4 类。</text>\n')
    out.append("</svg>\n")
    p = IMG / "splitflap" / "w3_env.svg"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(out), encoding="utf-8")
    print(p, p.stat().st_size)


def probe_steps(path):
    # 150 步预算的分配，来自 stats.json
    cats = [
        ("布线尝试", ORANGE),
        ("只读勘察", BLUE),
        ("探索工具/API", AMBER),
        ("写代码/改板", GRAY),
        ("跑 kicad-cli 验证", "#6f8f7f"),
        ("报错后重试", RED),
        ("读题与材料", "#4b5a52"),
    ]
    data = {
        "cynthion": {"布线尝试": 19, "只读勘察": 66, "探索工具/API": 26, "写代码/改板": 15,
                     "跑 kicad-cli 验证": 11, "报错后重试": 10, "读题与材料": 3},
        "Glasgow": {"布线尝试": 55, "只读勘察": 45, "探索工具/API": 12, "写代码/改板": 11,
                    "跑 kicad-cli 验证": 16, "报错后重试": 9, "读题与材料": 2},
    }
    w, h = 1200, 520
    out = [head(w, h, "两道难题各 150 步用完：Glasgow 一半步数在自研布线循环里")]
    out.append(f'<text x="40" y="92" fill="{DIM}" font-size="15">步数=模型请求次数；两题都是 step_budget_exhausted，不是超时。Glasgow 交付文件改动 0</text>\n')
    x0, x1 = 200, 1120
    top, row = 170, 110
    scale = (x1 - x0) / 150
    for i, (task, mix) in enumerate(data.items()):
        y = top + i * row
        out.append(f'<text x="40" y="{y + 34}" fill="{FG}" font-size="20">{task}</text>\n')
        out.append(f'<text x="40" y="{y + 58}" fill="{DIM}" font-size="14">150 步</text>\n')
        x = x0
        for name, color in cats:
            n = mix.get(name, 0)
            if not n:
                continue
            bw = n * scale
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="46" fill="{color}" fill-opacity="0.8"/>\n')
            if bw > 26:
                out.append(f'<text x="{x + bw / 2:.1f}" y="{y + 30}" fill="{BG}" font-size="15" text-anchor="middle">{n}</text>\n')
            x += bw
        out.append(f'<text x="{x0}" y="{y + 68}" fill="{DIM}" font-size="13">'
                   f'勘察 {mix["只读勘察"]} · 布线 {mix["布线尝试"]} · 探索 {mix["探索工具/API"]} · 写/改 {mix["写代码/改板"]}'
                   f' · 验证 {mix["跑 kicad-cli 验证"]} · 重试 {mix["报错后重试"]}</text>\n')
    ly = top + 2 * row + 20
    lx = 40
    for name, color in cats:
        out.append(f'<rect x="{lx}" y="{ly}" width="16" height="16" fill="{color}" fill-opacity="0.8"/>\n')
        out.append(f'<text x="{lx + 24}" y="{ly + 13}" fill="{FG}" font-size="14">{name}</text>\n')
        lx += 24 + 14 * len(name) + 26
    out.append(f'<text x="40" y="{ly + 46}" fill="{DIM}" font-size="14">'
               f'数据：probe_stall/run1/output/out/stats.json；每步只归一个主类别，映射在 out/scripts/classify_steps.py。</text>\n')
    out.append("</svg>\n")
    p = IMG / "probe-stall" / "steps.svg"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(out), encoding="utf-8")
    print(p, p.stat().st_size)


def process_spread():
    """FDM 配合单边与 MDF 切缝的取值跨度，来自 process_params.json 的逐条 condition。"""
    w, h = 1200, 620
    out = [head(w, h, "同一项参数，不同来源差 10 倍：题面必须点名一家")]
    out.append(f'<text x="40" y="92" fill="{DIM}" font-size="15">'
               f'横轴单位 mm；线是来源给出的区间，点是单值，“≥”是原文没给上限。数据：process_params_20261123/process_params.json</text>\n')
    x0, x1 = 430, 1090
    vmax = 0.9
    def X(v):
        return x0 + (x1 - x0) * v / vmax
    for i in range(0, 10):
        v = i * 0.1
        out.append(f'<line x1="{X(v):.1f}" y1="128" x2="{X(v):.1f}" y2="520" stroke="#1e2a24" stroke-width="1"/>\n')
        out.append(f'<text x="{X(v):.1f}" y="548" fill="{DIM}" font-size="13" text-anchor="middle">{v:.1f}</text>\n')
    rows = [
        ("FDM 压配（Markforged，按直径）", 0.0, 0.025, ORANGE, "range"),
        ("FDM 嵌螺母（Mark3D）", 0.05, 0.08, ORANGE, "range"),
        ("FDM 配合（Loftsmith）", 0.05, 0.25, BLUE, "range"),
        ("FDM 配合（SpeakCAD）", 0.1, 0.8, BLUE, "range"),
        ("FDM 移动件（Prusa，未说明单边）", 0.3, 0.8, AMBER, "open"),
        ("FDM 固定/活动（嘉立创）", 0.5, 0.5, RED, "point"),
        ("MDF 切缝（实测 4 组）", 0.07, 0.20, BLUE, "range"),
        ("MDF 切缝（通用表格值）", 0.16, 0.16, AMBER, "point"),
        ("MDF 木材上限（Ponoko）", 0.20, 0.20, RED, "point"),
    ]
    top, row = 170, 38
    for i, (name, a, b, color, kind) in enumerate(rows):
        y = top + i * row
        out.append(f'<text x="40" y="{y + 5}" fill="{FG}" font-size="15">{name}</text>\n')
        if kind == "range":
            out.append(f'<line x1="{X(a):.1f}" y1="{y}" x2="{X(b):.1f}" y2="{y}" stroke="{color}" stroke-width="7" stroke-opacity="0.55" stroke-linecap="round"/>\n')
            out.append(f'<circle cx="{X(a):.1f}" cy="{y}" r="5" fill="{color}"/>\n<circle cx="{X(b):.1f}" cy="{y}" r="5" fill="{color}"/>\n')
            out.append(f'<text x="{X(b) + 12:.1f}" y="{y + 5}" fill="{DIM}" font-size="13">{a:g}–{b:g}</text>\n')
        elif kind == "open":
            out.append(f'<line x1="{X(a):.1f}" y1="{y}" x2="{X(b):.1f}" y2="{y}" stroke="{color}" stroke-width="5" stroke-dasharray="10 7"/>\n')
            out.append(f'<text x="{X(a) - 10:.1f}" y="{y + 5}" fill="{DIM}" font-size="13" text-anchor="end">≥{a:g}</text>\n')
        else:
            out.append(f'<circle cx="{X(a):.1f}" cy="{y}" r="7" fill="{color}"/>\n')
            out.append(f'<text x="{X(a) + 14:.1f}" y="{y + 5}" fill="{DIM}" font-size="13">{a:g}</text>\n')
    out.append(f'<text x="40" y="{top + len(rows) * row + 30}" fill="{DIM}" font-size="14">'
               f'判分若按“服务商可制造”，FDM 固定装配取嘉立创 0.5 mm；若按“厂商可打印下限”，取 Markforged 0.025 mm。两者差 20 倍。</text>\n')
    out.append("</svg>\n")
    pth = IMG / "process-params" / "clearance.svg"
    pth.parent.mkdir(parents=True, exist_ok=True)
    pth.write_text("".join(out), encoding="utf-8")
    print(pth, pth.stat().st_size)


GOOD = "#6fbb8e"
BAD = "#c2495f"
NONE = "#33413a"

def kicad_matrix():
    """三条无界面路径 × 逐项操作，来自 kicad_capability 报告第 0 节速查表。"""
    rows = [
        ("打开/保存 PCB 文件", "部分", "有", "有"),
        ("从原理图更新 PCB（F8）", "无", "无", "无"),
        ("原理图 ↔ PCB 一致性检查", "有", "无", "无"),
        ("运行 DRC", "有", "无", "实测坏"),
        ("重填铺铜", "部分", "有", "有"),
        ("增删改封装 / 走线 / 过孔", "无", "有", "有"),
        ("交互式推挤布线", "无", "无", "无"),
        ("差分对布线", "无", "无", "无"),
        ("等长 / 时域调谐", "无", "无", "无"),
        ("导出 Gerber / STEP / PDF", "有", "无", "部分"),
        ("导出 3D PNG", "有", "无", "无"),
        ("生成网表", "有", "无", "无"),
        ("运行 ERC", "有", "无", "无"),
    ]
    color = {"有": GOOD, "部分": AMBER, "无": NONE, "实测坏": BAD}
    w, h = 1200, 760
    out = [head(w, h, "KiCad 10 三条无界面路径：设计修改类操作基本都不存在")]
    out.append(f'<text x="40" y="92" fill="{DIM}" font-size="15">'
               f'kicad-cli / IPC API / pcbnew 逐项实测与文档核对；IPC 需要有一个正在运行的 GUI，且只覆盖 PCB 编辑器</text>\n')
    x0 = 430
    colw = 220
    cols = ("kicad-cli 10.0.7", "IPC API", "pcbnew 脚本")
    for j, name in enumerate(cols):
        out.append(f'<text x="{x0 + j * colw + colw / 2:.0f}" y="140" fill="{FG}" font-size="15" text-anchor="middle">{name}</text>\n')
    top, rowh = 165, 40
    for i, (op, a, b, c) in enumerate(rows):
        y = top + i * rowh
        out.append(f'<text x="40" y="{y + 24}" fill="{FG}" font-size="15">{op}</text>\n')
        for j, v in enumerate((a, b, c)):
            cx = x0 + j * colw
            out.append(f'<rect x="{cx + 22}" y="{y + 6}" width="{colw - 44}" height="26" rx="4" fill="{color[v]}" fill-opacity="{0.9 if v != "无" else 0.5}"/>\n')
            out.append(f'<text x="{cx + colw / 2:.0f}" y="{y + 25}" fill="{BG if v != "无" else DIM}" font-size="14" text-anchor="middle">{v}</text>\n')
    ly = top + len(rows) * rowh + 22
    lx = 40
    for name, key in (("有", "有"), ("部分", "部分"), ("无接口", "无"), ("名义有/实测坏", "实测坏")):
        out.append(f'<rect x="{lx}" y="{ly}" width="16" height="16" fill="{color[key]}" fill-opacity="0.9"/>\n')
        out.append(f'<text x="{lx + 24}" y="{ly + 13}" fill="{FG}" font-size="14">{name}</text>\n')
        lx += 24 + 14 * len(name) + 30
    out.append(f'<text x="40" y="{ly + 40}" fill="{DIM}" font-size="14">'
               f'数据：kicad_capability/run2/output/out/REPORT.md 第 0 节速查表；本机 KiCad 10.0.7，macOS。</text>\n')
    out.append("</svg>\n")
    pth = IMG / "kicad-headless" / "matrix.svg"
    pth.parent.mkdir(parents=True, exist_ok=True)
    pth.write_text("".join(out), encoding="utf-8")
    print(pth, pth.stat().st_size)


def glasgow_checks():
    """7 项复核的结论条，来自 glasgow_case_verify REPORT。"""
    w, h = 1200, 340
    out = [head(w, h, "Glasgow revC3 外壳独立复核：7 项里 5 项通过、1 项已更正、1 项只报告")]
    items = [
        ("1 实体", "235/235", GOOD),
        ("2 装得进", "干涉 0", GOOD),
        ("3 USB-C", "扫掠 0", GOOD),
        ("4 复位键", "余 0.980", GOOD),
        ("5 原有配合", "区外 0", GOOD),
        ("6 出处", "改 1 处", AMBER),
        ("7 薄壁", "只报告", GRAY),
    ]
    x0, gap = 40, 12
    cw = (w - 2 * x0 - gap * 6) / 7
    for i, (name, sub, color) in enumerate(items):
        x = x0 + i * (cw + gap)
        out.append(f'<rect x="{x:.0f}" y="140" width="{cw:.0f}" height="110" rx="6" fill="#15211b" stroke="{color}" stroke-width="2"/>\n')
        out.append(f'<text x="{x + cw / 2:.0f}" y="180" fill="{FG}" font-size="17" text-anchor="middle">{name}</text>\n')
        out.append(f'<text x="{x + cw / 2:.0f}" y="214" fill="{color}" font-size="16" text-anchor="middle">{sub}</text>\n')
    out.append(f'<text x="40" y="292" fill="{DIM}" font-size="14">'
               f'第 7 项按要求只报数、不判定；薄壁 0.100 / 0.175 / 0.180 / 0.2025 mm。'
               f'数据：glasgow_case_verify/run1/output/out/REPORT.md</text>\n')
    out.append("</svg>\n")
    pth = IMG / "glasgow-revc3-case" / "checks.svg"
    pth.parent.mkdir(parents=True, exist_ok=True)
    pth.write_text("".join(out), encoding="utf-8")
    print(pth, pth.stat().st_size)


if __name__ == "__main__":
    moteus_scores(IMG / "moteus-c1")
    splitflap_env(IMG / "splitflap")
    probe_steps(IMG / "probe-stall")
    process_spread()
    kicad_matrix()
    glasgow_checks()
