"""用 pcbnew 把 .kicad_pcb 画成 SVG，可按位号/网络高亮、裁剪、叠加 DRC 未连接线和标注。

用 KiCad 自带的 Python 跑：
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
      scripts/render/pcb_svg.py spec.json

spec.json:
{
  "pcb": "path/to/board.kicad_pcb",
  "drc_json": "optional kicad-cli drc --format json report",
  "views": [
    {
      "out": "out/view.svg",
      "side": "front" | "back" | "both",          # 默认 both
      "crop": "board" | [x0, y0, x1, y1] | {"refs": ["R1"], "nets": [], "margin": 2.0},
      "highlight": {"refs": ["R301"], "nets": ["VBUS_IN"], "pads": [["U1", "3"]]},
      "dim": true,                                # 有高亮时其余元素变暗
      "labels": "highlight" | "all" | "none" | ["R1", "R2"],
      "silk": true, "courtyard": false, "zones": true,
      "unconnected": false,                       # 画 DRC 报告里的未连接线
      "markers": [{"x": 10, "y": 20, "r": 1.0, "text": "重叠"}],
      "width": 1200
    }
  ]
}
坐标单位都是 mm，和 KiCad 编辑器里显示的一致（y 向下）。
"""
import json
import math
import os
import sys

import pcbnew

NM = 1e6

COL = {
    "bg": "#0c1411",
    "board": "#173a2d",
    "edge": "#e8cf6a",
    "fcu": "#c9813f",
    "bcu": "#4f86bd",
    "fpad": "#e6ad6a",
    "bpad": "#7fb0dd",
    "hole": "#0c1411",
    "via": "#c2c7c9",
    "silk": "#eceee6",
    "crtyd": "#c7b8ff",
    "hl": "#ff3d6e",
    "hlnet": "#ffd23f",
    "rats": "#5ff2ff",
    "label": "#ffffff",
    "marker": "#ff3d6e",
}


def mm(v):
    return v / NM


def pts_of_chain(chain):
    return [(mm(chain.CPoint(i).x), mm(chain.CPoint(i).y)) for i in range(chain.PointCount())]


def poly_path(ps):
    """SHAPE_POLY_SET -> SVG path d（含孔），evenodd 填充。"""
    parts = []
    for i in range(ps.OutlineCount()):
        rings = [ps.Outline(i)] + [ps.Hole(i, h) for h in range(ps.HoleCount(i))]
        for ring in rings:
            pts = pts_of_chain(ring)
            if len(pts) < 3:
                continue
            parts.append("M" + " L".join("%.3f %.3f" % p for p in pts) + " Z")
    return " ".join(parts)


def bbox_of_poly(ps):
    b = ps.BBox()
    return (mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom()))


def inter(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Renderer:
    def __init__(self, pcb_path, drc_json=None):
        self.board = pcbnew.LoadBoard(pcb_path)
        self.board.BuildConnectivity()
        self.drc = None
        if drc_json and os.path.exists(drc_json):
            with open(drc_json, encoding="utf-8") as f:
                self.drc = json.load(f)
        self.fps = {fp.GetReference(): fp for fp in self.board.GetFootprints()}

    # ---------- 几何辅助 ----------
    def board_bbox(self):
        ps = pcbnew.SHAPE_POLY_SET()
        if self.board.GetBoardPolygonOutlines(ps, True) and ps.OutlineCount():
            return bbox_of_poly(ps)
        b = self.board.GetBoardEdgesBoundingBox()
        return (mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom()))

    def fp_bbox(self, ref):
        fp = self.fps.get(ref)
        if fp is None:
            raise KeyError("没有位号 %s" % ref)
        b = fp.GetBoundingBox(False)
        return (mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom()))

    def net_bbox(self, net):
        bx = None
        for t in self.board.GetTracks():
            if t.GetNetname() == net:
                b = t.GetBoundingBox()
                r = (mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom()))
                bx = r if bx is None else (min(bx[0], r[0]), min(bx[1], r[1]), max(bx[2], r[2]), max(bx[3], r[3]))
        return bx

    def resolve_crop(self, crop):
        if crop in (None, "board"):
            x0, y0, x1, y1 = self.board_bbox()
            m = max(x1 - x0, y1 - y0) * 0.03
            return (x0 - m, y0 - m, x1 + m, y1 + m)
        if isinstance(crop, list):
            return tuple(crop)
        boxes = [self.fp_bbox(r) for r in crop.get("refs", [])]
        boxes += [b for b in (self.net_bbox(n) for n in crop.get("nets", [])) if b]
        if "points" in crop:
            for p in crop["points"]:
                boxes.append((p[0], p[1], p[0], p[1]))
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[2] for b in boxes)
        y1 = max(b[3] for b in boxes)
        m = crop.get("margin", 2.0)
        return (x0 - m, y0 - m, x1 + m, y1 + m)

    # ---------- 绘制 ----------
    def render(self, v):
        crop = self.resolve_crop(v.get("crop"))
        side = v.get("side", "both")
        hl = v.get("highlight", {}) or {}
        hl_refs = set(hl.get("refs", []))
        hl_nets = set(hl.get("nets", []))
        hl_pads = set(tuple(p) for p in hl.get("pads", []))
        any_hl = bool(hl_refs or hl_nets or hl_pads)
        dim = v.get("dim", True) and any_hl
        w_mm = crop[2] - crop[0]
        h_mm = crop[3] - crop[1]
        width = v.get("width", 1200)
        height = int(round(width * h_mm / w_mm))
        scale = w_mm / width  # mm per px
        out = []
        add = out.append
        add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.3f %.3f %.3f %.3f" width="%d" height="%d" '
            'font-family="JetBrains Mono, Menlo, monospace">' % (crop[0], crop[1], w_mm, h_mm, width, height))
        add('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="%s"/>' % (crop[0], crop[1], w_mm, h_mm, COL["bg"]))

        # 板子底色
        ps = pcbnew.SHAPE_POLY_SET()
        if self.board.GetBoardPolygonOutlines(ps, True):
            add('<path d="%s" fill="%s" fill-rule="evenodd" stroke="%s" stroke-width="%.3f"/>'
                % (poly_path(ps), COL["board"], COL["edge"], max(0.1, 1.2 * scale)))

        layers = []
        if side in ("back", "both"):
            layers.append((pcbnew.B_Cu, COL["bcu"], COL["bpad"], 0.55 if side == "both" else 0.9))
        if side in ("front", "both"):
            layers.append((pcbnew.F_Cu, COL["fcu"], COL["fpad"], 0.9))

        dim_op = 0.35

        for layer, ccol, pcol, op in layers:
            g_op = op
            # 铺铜
            if v.get("zones", True):
                for z in self.board.Zones():
                    if not z.IsOnLayer(layer) or z.GetIsRuleArea():
                        continue
                    fp = z.GetFilledPolysList(layer)
                    if fp is None or fp.OutlineCount() == 0:
                        continue
                    if not inter(bbox_of_poly(fp), crop):
                        continue
                    o = g_op * 0.55
                    if dim and z.GetNetname() not in hl_nets:
                        o *= dim_op
                    col = COL["hlnet"] if z.GetNetname() in hl_nets else ccol
                    add('<path d="%s" fill="%s" fill-opacity="%.2f" fill-rule="evenodd"/>' % (poly_path(fp), col, o))
            # 走线
            segs_n, segs_h = [], []
            for t in self.board.GetTracks():
                if t.Type() == pcbnew.PCB_VIA_T or t.GetLayer() != layer:
                    continue
                b = t.GetBoundingBox()
                if not inter((mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom())), crop):
                    continue
                s, e = t.GetStart(), t.GetEnd()
                if t.Type() == pcbnew.PCB_ARC_T:
                    m = t.GetMid()
                    d = "M%.4f %.4f Q%.4f %.4f %.4f %.4f" % (mm(s.x), mm(s.y), 2 * mm(m.x) - (mm(s.x) + mm(e.x)) / 2,
                                                             2 * mm(m.y) - (mm(s.y) + mm(e.y)) / 2, mm(e.x), mm(e.y))
                else:
                    d = "M%.4f %.4f L%.4f %.4f" % (mm(s.x), mm(s.y), mm(e.x), mm(e.y))
                item = '<path d="%s" stroke-width="%.4f"/>' % (d, mm(t.GetWidth()))
                (segs_h if t.GetNetname() in hl_nets else segs_n).append(item)
            if segs_n:
                add('<g fill="none" stroke="%s" stroke-linecap="round" stroke-opacity="%.2f">%s</g>'
                    % (ccol, g_op * (dim_op if dim else 1), "".join(segs_n)))
            if segs_h:
                add('<g fill="none" stroke="%s" stroke-linecap="round" stroke-opacity="0.95">%s</g>'
                    % (COL["hlnet"], "".join(segs_h)))
            # 焊盘
            for ref, fp in self.fps.items():
                fb = self.fp_bbox(ref)
                if not inter(fb, crop):
                    continue
                for pad in fp.Pads():
                    if not pad.IsOnLayer(layer):
                        continue
                    try:
                        poly = pad.GetEffectivePolygon(layer, pcbnew.ERROR_INSIDE)
                    except TypeError:
                        poly = pad.GetEffectivePolygon(pcbnew.ERROR_INSIDE)
                    d = poly_path(poly)
                    if not d:
                        continue
                    is_hl = ref in hl_refs or (ref, pad.GetNumber()) in hl_pads or pad.GetNetname() in hl_nets
                    if is_hl:
                        col = COL["hl"] if (ref in hl_refs or (ref, pad.GetNumber()) in hl_pads) else COL["hlnet"]
                        add('<path d="%s" fill="%s" fill-opacity="0.92" stroke="#ffffff" stroke-width="%.4f" '
                            'fill-rule="evenodd"/>' % (d, col, max(0.02, 0.8 * scale)))
                    else:
                        add('<path d="%s" fill="%s" fill-opacity="%.2f" fill-rule="evenodd"/>'
                            % (d, pcol, g_op * (dim_op if dim else 1)))

        # 钻孔（焊盘孔、过孔）
        for ref, fp in self.fps.items():
            if not inter(self.fp_bbox(ref), crop):
                continue
            for pad in fp.Pads():
                ds = pad.GetDrillSize()
                if ds.x > 0:
                    p = pad.GetPosition()
                    r = mm(min(ds.x, ds.y)) / 2
                    add('<circle cx="%.4f" cy="%.4f" r="%.4f" fill="%s"/>' % (mm(p.x), mm(p.y), r, COL["hole"]))
        vias = []
        for t in self.board.GetTracks():
            if t.Type() != pcbnew.PCB_VIA_T:
                continue
            p = t.GetPosition()
            x, y = mm(p.x), mm(p.y)
            if not (crop[0] - 2 < x < crop[2] + 2 and crop[1] - 2 < y < crop[3] + 2):
                continue
            try:
                wd = t.GetWidth(pcbnew.F_Cu)
            except TypeError:
                wd = t.GetWidth()
            is_hl = t.GetNetname() in hl_nets
            o = 1 if (not dim or is_hl) else dim_op
            vias.append('<circle cx="%.4f" cy="%.4f" r="%.4f" fill="%s" fill-opacity="%.2f"/>'
                        '<circle cx="%.4f" cy="%.4f" r="%.4f" fill="%s"/>'
                        % (x, y, mm(wd) / 2, COL["hlnet"] if is_hl else COL["via"], o, x, y, mm(t.GetDrillValue()) / 2,
                           COL["hole"]))
        add("".join(vias))

        # 丝印、courtyard
        silk_layer = pcbnew.B_SilkS if side == "back" else pcbnew.F_SilkS
        if v.get("silk", True):
            items = []
            for ref, fp in self.fps.items():
                if not inter(self.fp_bbox(ref), crop):
                    continue
                for g in fp.GraphicalItems():
                    if g.GetLayer() != silk_layer:
                        continue
                    ps = pcbnew.SHAPE_POLY_SET()
                    g.TransformShapeToPolygon(ps, silk_layer, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE)
                    d = poly_path(ps)
                    if d:
                        items.append('<path d="%s"/>' % d)
            for g in self.board.GetDrawings():
                if g.GetLayer() != silk_layer:
                    continue
                ps = pcbnew.SHAPE_POLY_SET()
                g.TransformShapeToPolygon(ps, silk_layer, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE)
                if ps.OutlineCount() and inter(bbox_of_poly(ps), crop):
                    items.append('<path d="%s"/>' % poly_path(ps))
            add('<g fill="%s" fill-opacity="%.2f" fill-rule="evenodd">%s</g>'
                % (COL["silk"], 0.3 if dim else 0.7, "".join(items)))
        if v.get("courtyard", False):
            cl = pcbnew.B_CrtYd if side == "back" else pcbnew.F_CrtYd
            items = []
            for ref, fp in self.fps.items():
                if not inter(self.fp_bbox(ref), crop):
                    continue
                cy = fp.GetCourtyard(cl)
                if cy is None or cy.OutlineCount() == 0:
                    continue
                strong = ref in hl_refs
                items.append('<path d="%s" stroke-opacity="%.2f" stroke-width="%.4f"/>'
                             % (poly_path(cy), 1 if strong or not dim else 0.4, (1.6 if strong else 0.9) * scale))
            add('<g fill="none" stroke="%s" stroke-dasharray="%.3f %.3f">%s</g>'
                % (COL["crtyd"], 5 * scale, 3 * scale, "".join(items)))

        # 未连接线
        if v.get("unconnected") and self.drc:
            lines, dots = [], []
            rr = max(v.get("rats_dot", 3.2) * scale, 0.05)
            for it in self.drc.get("unconnected_items", []):
                its = it.get("items", [])
                if len(its) < 2:
                    continue
                a, b = its[0]["pos"], its[1]["pos"]
                lines.append('<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f"/>' % (a["x"], a["y"], b["x"], b["y"]))
                dots.append('<circle cx="%.3f" cy="%.3f" r="%.3f"/><circle cx="%.3f" cy="%.3f" r="%.3f"/>'
                            % (a["x"], a["y"], rr, b["x"], b["y"], rr))
            add('<g stroke="%s" stroke-width="%.4f" stroke-linecap="round" stroke-opacity="0.95">%s</g>'
                % (COL["rats"], v.get("rats_width", 2.4) * scale, "".join(lines)))
            add('<g fill="%s">%s</g>' % (COL["rats"], "".join(dots)))

        # 标注
        fs = 13 * scale
        labels = v.get("labels", "highlight")
        if labels == "all":
            lab_refs = list(self.fps)
        elif labels == "highlight":
            lab_refs = sorted(hl_refs | set(r for r, _ in hl_pads))
        elif labels == "none":
            lab_refs = []
        else:
            lab_refs = labels
        for ref in lab_refs:
            if ref not in self.fps:
                continue
            b = self.fp_bbox(ref)
            if not inter(b, crop):
                continue
            x = (b[0] + b[2]) / 2
            y = b[1] - fs * 0.35
            if y - fs < crop[1]:
                y = b[3] + fs * 1.05
            add('<text x="%.4f" y="%.4f" font-size="%.4f" text-anchor="middle" fill="%s" stroke="%s" '
                'stroke-width="%.4f" paint-order="stroke">%s</text>'
                % (x, y, fs, COL["label"], COL["bg"], fs * 0.25, esc(ref)))
        for mk in v.get("markers", []):
            r = mk.get("r", 1.0)
            add('<circle cx="%.4f" cy="%.4f" r="%.4f" fill="none" stroke="%s" stroke-width="%.4f"/>'
                % (mk["x"], mk["y"], r, COL["marker"], 2.2 * scale))
            if mk.get("text"):
                add('<text x="%.4f" y="%.4f" font-size="%.4f" fill="%s" stroke="%s" stroke-width="%.4f" '
                    'paint-order="stroke">%s</text>'
                    % (mk["x"] + r + fs * 0.3, mk["y"] - r, fs, COL["marker"], COL["bg"], fs * 0.25, esc(mk["text"])))
        # 比例尺
        target = w_mm / 6
        mag = 10 ** math.floor(math.log10(target))
        step = min((s * mag for s in (1, 2, 5, 10)), key=lambda s: abs(s - target))
        sx, sy = crop[0] + 14 * scale, crop[3] - 14 * scale
        add('<g stroke="#ffffff" stroke-width="%.4f"><line x1="%.4f" y1="%.4f" x2="%.4f" y2="%.4f"/></g>'
            % (2 * scale, sx, sy, sx + step, sy))
        add('<text x="%.4f" y="%.4f" font-size="%.4f" fill="#ffffff">%s mm</text>'
            % (sx, sy - 5 * scale, fs * 0.9, ("%g" % step)))
        add("</svg>")
        return "".join(out), crop


def main():
    spec_path = sys.argv[1]
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    base = os.path.dirname(os.path.abspath(spec_path))

    def rp(p):
        return p if os.path.isabs(p) else os.path.join(base, p)

    r = Renderer(rp(spec["pcb"]), rp(spec["drc_json"]) if spec.get("drc_json") else None)
    results = []
    for v in spec["views"]:
        svg, crop = r.render(v)
        out = rp(v["out"])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(svg)
        results.append({"out": v["out"], "bytes": len(svg.encode("utf-8")), "crop_mm": [round(c, 3) for c in crop]})
        print("%s  %.0f KB  crop=%s" % (v["out"], len(svg.encode("utf-8")) / 1024, [round(c, 2) for c in crop]))
    return results


if __name__ == "__main__":
    main()
