"""Glasgow 案例的 2D 对照图：改前 revC0 与改后 revC2 用同一裁剪窗口，改动的件高亮并标位号。

用 KiCad 自带的 Python 跑：
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
      scripts/render/glasgow_views.py BEFORE.kicad_pcb AFTER.kicad_pcb OUT_DIR

BEFORE 是 a73607c7 的 glasgow.kicad_pcb，AFTER 是 678b8972 的（题包里的参考解，revC2 原板）。
窗口是 PCB 坐标（mm）。红框是改后新增的件，橙框是同位号但换了封装或型号的件；改前图里红色虚线框是被删掉的件。revC2 把这一带整体重新布置过，所以窗口内的其他件位置也变了。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcb_svg  # noqa: E402
from pcb_svg import Renderer  # noqa: E402

WINDOWS = {
    "port": {"crop": [95.0, 101.0, 112.0, 117.0], "width": 1200, "tag": "端口 B 保护"},
    "sync": {"crop": [80.0, 96.0, 98.0, 114.0], "width": 1200, "tag": "SYNC 电平转换",
             "new": ["U32", "R38", "R45", "C85"], "extra_chg": ["R10"]},
    "ina": {"crop": [114.0, 98.0, 130.0, 114.0], "width": 1200, "tag": "端口 B 电流监测",
            "new": ["D18", "R48", "R7", "R59"], "chg": ["U12"]},
}
NEW_C = "#ff3d6e"   # 改后新增的件
CHG_C = "#ffb000"   # 同位号但换了封装或型号的件（改前和改后都标）


def fp_name(r, ref):
    return str(r.fps[ref].GetFPID().GetLibItemName())


def classify(rb, ra, crop):
    """返回 (新增, 换型, 删除)，只看中心落在窗口内的件。"""
    def inside(r, ref):
        p = r.fps[ref].GetPosition()
        return crop[0] <= p.x / 1e6 <= crop[2] and crop[1] <= p.y / 1e6 <= crop[3]
    new = sorted(x for x in ra.fps if x not in rb.fps and inside(ra, x))
    gone = sorted(x for x in rb.fps if x not in ra.fps and inside(rb, x))
    chg = sorted(x for x in ra.fps if x in rb.fps and (inside(ra, x) or inside(rb, x))
                 and (x.startswith(("U", "RN")) or x == "J4")
                 and (fp_name(ra, x) != fp_name(rb, x)
                      or ("INA233" in str(ra.fps[x].GetValue())) != ("INA233" in str(rb.fps[x].GetValue()))))
    return new, chg, gone


def boxes(r, refs, color, scale, fill=False, dash=False):
    out = []
    fs = 12 * scale
    pad = 3 * scale
    for ref in refs:
        b = r.fp_bbox(ref)
        da = ' stroke-dasharray="%.3f %.3f"' % (6 * scale, 4 * scale) if dash else ""
        out.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="none" stroke="%s" stroke-width="%.3f"%s/>'
                   % (b[0] - pad, b[1] - pad, b[2] - b[0] + 2 * pad, b[3] - b[1] + 2 * pad, color, 2 * scale, da))
        out.append('<text x="%.3f" y="%.3f" font-size="%.3f" text-anchor="middle" fill="%s" stroke="#0c1411" '
                   'stroke-width="%.3f" paint-order="stroke" font-family="Menlo, monospace">%s</text>'
                   % ((b[0] + b[2]) / 2, b[1] - pad - 3 * scale, fs, color, fs * 0.28, ref))
        if fill:
            out.insert(len(out) - 2, '<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="%s" fill-opacity="0.22"/>'
                       % (b[0] - pad, b[1] - pad, b[2] - b[0] + 2 * pad, b[3] - b[1] + 2 * pad, color))
    return "".join(out)


def tag(text, crop, scale):
    fs = 15 * scale
    return ('<text x="%.3f" y="%.3f" font-size="%.3f" fill="#ffffff" stroke="#0c1411" stroke-width="%.3f" '
            'paint-order="stroke" font-family="PingFang SC, Noto Sans CJK SC, sans-serif">%s</text>'
            % (crop[0] + 10 * scale, crop[1] + 22 * scale, fs, fs * 0.25, text))


def make(rb, ra, name, spec, outdir):
    crop = spec["crop"]
    width = spec["width"]
    scale = (crop[2] - crop[0]) / width
    new, chg, gone = classify(rb, ra, crop)
    if "new" in spec:
        new = [x for x in new if x in spec["new"]] + [x for x in spec["new"] if x not in new]
    if "chg" in spec:
        chg = spec["chg"]
    chg = chg + [x for x in spec.get("extra_chg", []) if x not in chg]
    if "only" in spec:  # 整板图只标题目相关的件
        new, chg, gone = spec["only"]
    for side_name, r in (("before", rb), ("after", ra)):
        hl = gone if side_name == "before" else new
        v = {"crop": crop, "width": width, "side": "both", "highlight": {"refs": hl or ["-"]}, "dim": True,
             "labels": "none", "silk": True, "zones": False}
        svg, c = r.render(v)
        if side_name == "before":
            extra = boxes(rb, chg, CHG_C, scale, fill=True) + boxes(rb, gone, NEW_C, scale, dash=True)
            label = "改前 revC0 · %s" % spec["tag"]
        else:
            extra = boxes(ra, chg, CHG_C, scale, fill=True) + boxes(ra, new, NEW_C, scale)
            label = "改后 revC2 · %s" % spec["tag"]
        if name == "board":
            for wn, ws in WINDOWS.items():
                x0, y0, x1, y1 = ws["crop"]
                extra += ('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="none" stroke="#ffffff" '
                          'stroke-width="%.3f" stroke-dasharray="%.3f %.3f"/>'
                          '<text x="%.3f" y="%.3f" font-size="%.3f" fill="#ffffff" stroke="#0c1411" stroke-width="%.3f" '
                          'paint-order="stroke" font-family="PingFang SC, Noto Sans CJK SC, sans-serif">%s</text>'
                          % (x0, y0, x1 - x0, y1 - y0, 1.5 * scale, 8 * scale, 5 * scale,
                             x0, y1 + 16 * scale, 13 * scale, 3 * scale, ws["tag"]))
        extra += tag(label, crop, scale)
        svg = svg.replace("</svg>", extra + "</svg>")
        path = os.path.join(outdir, "%s_%s.svg" % (name, side_name))
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(path, "%.0f KB" % (len(svg) / 1024), "crop", [round(x, 2) for x in c],
              "new", new, "chg", chg, "gone", gone)


def main():
    before, after, outdir = sys.argv[1:4]
    os.makedirs(outdir, exist_ok=True)
    rb, ra = Renderer(before), Renderer(after)
    for name, spec in WINDOWS.items():
        make(rb, ra, name, spec, outdir)
    bb = rb.board_bbox()
    make(rb, ra, "board", {"crop": [bb[0] - 2, bb[1] - 2, bb[2] + 2, bb[3] + 2], "width": 1800,
                           "tag": "整板 80.10 x 49.10 mm",
                           "only": (["D20", "D21", "D22", "D23", "U32"], ["U12", "U21"], [])}, outdir)


if __name__ == "__main__":
    main()
