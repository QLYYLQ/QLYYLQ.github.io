"""STEP -> GLB（给页面里的 model-viewer 用），可上色、裁剪、标出干涉体。

用 build123d 环境跑：python scripts/render/step_glb.py spec.json

spec.json:
{
  "out": "out/model.glb",
  "inputs": [
    {"step": "a.step", "color": "#b9c1c6", "label": "改前"},          # 一个或多个 STEP，可平移
    {"step": "b.step", "color": "#e0894c", "offset": [0, 0, 0]}
  ],
  "keep_bbox": [x0, y0, z0, x1, y1, z1],      # 可选：只留和这个盒子相交的零件
  "colors": [                                  # 可选：按零件名正则 / 序号 / 体积上色（后写的优先）
    {"name_re": "Bearing", "color": "#ff3d6e"},
    {"index": [3, 7], "color": "#5ff2ff"},
    {"volume": [1940.16, 0.5], "color": "#ffd23f"}
  ],
  "interference": [                            # 可选：两组零件求交，交集体积标红一并导出
    {"a": {"name_re": "Screw"}, "b": {"name_re": "Plate"}, "color": "#ff3d6e"}
  ],
  "list_parts": true,                          # 打印零件表（序号、名字、体积、包围盒），方便写选择器
  "deflection": 0.05
}
"""
import json
import os
import re
import sys

from build123d import Color, Compound, Location, Shape, export_gltf, import_step
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps


def volume(shape):
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, props, 1e-6, False)
    return props.Mass()


def leaves(node, path=""):
    """展开装配树，返回 (名字路径, 世界坐标下的形状)。"""
    kids = list(getattr(node, "children", []) or [])
    name = getattr(node, "label", "") or ""
    p = (path + "/" + name) if name else path
    if not kids:
        # located() deep-copies the build123d parent tree for each leaf. Apply
        # the world transform to the OCC shape handle without copying its tree.
        shp = Shape.cast(node.wrapped.Located(node.global_location.wrapped))
        solids = list(shp.solids())
        for i, s in enumerate(solids):
            yield (p if len(solids) == 1 else "%s#%d" % (p, i)), s
        return
    for k in kids:
        yield from leaves(k, p)


def match(sel, idx, name, vol):
    if "name_re" in sel and not re.search(sel["name_re"], name):
        return False
    if "index" in sel and idx not in sel["index"]:
        return False
    if "volume" in sel:
        v, tol = sel["volume"]
        if abs(vol - v) > tol:
            return False
    return True


def bbox_hit(s, box):
    b = s.bounding_box()
    return not (b.max.X < box[0] or b.min.X > box[3] or b.max.Y < box[1] or b.min.Y > box[4]
                or b.max.Z < box[2] or b.min.Z > box[5])


def main():
    spec_path = sys.argv[1]
    spec = json.load(open(spec_path, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(spec_path))
    rp = lambda p: p if os.path.isabs(p) else os.path.join(base, p)

    parts = []  # (idx, name, solid, vol, color)
    for inp in spec["inputs"]:
        top = import_step(rp(inp["step"]))
        off = inp.get("offset")
        for name, s in leaves(top):
            if off:
                s = s.moved(Location(tuple(off)))
            if spec.get("keep_bbox") and not bbox_hit(s, spec["keep_bbox"]):
                continue
            parts.append([len(parts), (inp.get("label", "") + ":" if inp.get("label") else "") + name, s,
                          volume(s), inp.get("color", "#b9c1c6")])
    for rule in spec.get("colors", []):
        for p in parts:
            if match(rule, p[0], p[1], p[3]):
                p[4] = rule["color"]
    if spec.get("list_parts"):
        for i, name, s, v, c in parts:
            b = s.bounding_box()
            print("%4d  %-60s  vol=%10.2f  bbox=(%.1f,%.1f,%.1f)-(%.1f,%.1f,%.1f)  %s"
                  % (i, name[-60:], v, b.min.X, b.min.Y, b.min.Z, b.max.X, b.max.Y, b.max.Z, c))
    out_shapes = []
    for i, name, s, v, c in parts:
        s.color = Color(c)
        s.label = name
        out_shapes.append(s)
    report = []
    for it in spec.get("interference", []):
        A = [p for p in parts if match(it["a"], p[0], p[1], p[3])]
        B = [p for p in parts if match(it["b"], p[0], p[1], p[3])]
        for pa in A:
            for pb in B:
                if pa[0] == pb[0]:
                    continue
                try:
                    x = pa[2].intersect(pb[2])
                except Exception as e:
                    print("intersect failed", pa[1], pb[1], e)
                    continue
                if x is None:
                    continue
                sols = x.solids() if hasattr(x, "solids") else []
                vol = sum(volume(s) for s in sols)
                if vol <= 1e-6:
                    continue
                for s in sols:
                    s.color = Color(it.get("color", "#ff3d6e"))
                    s.label = "interference"
                    out_shapes.append(s)
                report.append({"a": pa[1], "b": pb[1], "volume_mm3": round(vol, 3)})
                print("interference %s x %s = %.3f mm3" % (pa[1], pb[1], vol))
    comp = Compound(children=out_shapes)
    out = rp(spec["out"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    d = spec.get("deflection", 0.05)
    export_gltf(comp, out, binary=True, linear_deflection=d, angular_deflection=0.3)
    print("wrote %s  %.0f KB  parts=%d" % (out, os.path.getsize(out) / 1024, len(parts)))
    if report:
        with open(os.path.splitext(out)[0] + ".interference.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
