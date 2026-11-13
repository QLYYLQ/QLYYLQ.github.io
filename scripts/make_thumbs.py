#!/usr/bin/env python3
"""给每个案例生成卡片缩略图 img/<id>/thumb.jpg（默认 640x360，取 JSON 里 thumb 或第一张图）。

用法：python3 scripts/make_thumbs.py [id ...]   不给 id 就全做；已有 thumb.jpg 且比源图新的跳过（--force 重做）
另外生成 omnifex/cases/img/_feature_*.jpg 给首页和项目页用（见 FEATURES）。
"""
import http.server
import json
import os
import pathlib
import socketserver
import subprocess
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES = ROOT / "omnifex" / "cases"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FEATURES = {  # 输出文件 -> (源图, 宽, 高)
    "_feature_home.jpg": ("img/489f2861/agent_mcu_right.svg", 960, 640),
    "_feature_cases.jpg": ("img/489f2861/agent_full.svg", 960, 540),
}

PAGE = """<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#0c1411}
img{width:%dpx;height:%dpx;object-fit:%s;object-position:%s;display:block}</style><img src="/%s">"""


def first_image(c):
    if c.get("thumb"):
        return c["thumb"]
    for s in c.get("steps", []):
        for f in s.get("figures", []):
            if not f["src"].endswith(".glb"):
                return f["src"]
        if s.get("compare"):
            return s["compare"]["after"]
        if s.get("model"):
            p = s["model"]["models"][0].get("poster")
            if p:
                return p
    return None


def shoot(port, src_rel, out, w, h, fit="cover", pos="center", prof=None):
    tmp = ROOT / ("_thumb_tmp_%d.html" % os.getpid())
    tmp.write_text(PAGE % (w, h, fit, pos, src_rel), encoding="utf-8")
    png = out.with_suffix(".png")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--user-data-dir=" + prof,
                    "--window-size=%d,%d" % (w, h), "--virtual-time-budget=6000", "--screenshot=" + str(png),
                    "http://127.0.0.1:%d/%s" % (port, tmp.name)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    tmp.unlink()
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", str(png), "--out", str(out)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    png.unlink()
    print("wrote", out.relative_to(ROOT), "%.0f KB" % (out.stat().st_size / 1024))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    prof = os.environ.get("CHROME_PROFILE", str(ROOT.parent / ".thumb-chrome-profile"))
    handler = lambda *x, **k: http.server.SimpleHTTPRequestHandler(*x, directory=str(ROOT), **k)
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a, **k: None
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        for p in sorted((CASES / "data").glob("*.json")):
            c = json.loads(p.read_text(encoding="utf-8"))
            if args and c["id"] not in args:
                continue
            src = first_image(c)
            if not src:
                continue
            srcp = CASES / src
            out = CASES / "img" / c["id"] / "thumb.jpg"
            if out.exists() and not force and out.stat().st_mtime > srcp.stat().st_mtime:
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            shoot(port, (CASES / src).relative_to(ROOT).as_posix(), out, 640, 360, prof=prof)
        if not args:
            for name, (src, w, h) in FEATURES.items():
                srcp = CASES / src
                if srcp.exists():
                    shoot(port, srcp.relative_to(ROOT).as_posix(), CASES / "img" / name, w, h, prof=prof)
        httpd.shutdown()


if __name__ == "__main__":
    main()
