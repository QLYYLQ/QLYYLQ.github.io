#!/usr/bin/env python3
"""给 GLB 出静态图：在本地起 http 服务，用 headless Chrome 打开 model-viewer 截图。

用法：python3 scripts/render/glb_poster.py <glb> <out.png> [--orbit "30deg 65deg auto"] [--target "auto auto auto"]
        [--fov 30deg] [--size 1200x900] [--bg "#0c1411"]
GLB 必须在本仓库目录里（服务根目录是仓库根）。
"""
import argparse
import http.server
import os
import pathlib
import socketserver
import subprocess
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

PAGE = """<!doctype html><meta charset="utf-8">
<script type="module" src="/assets/vendor/model-viewer/model-viewer.min.js"></script>
<style>html,body{margin:0;background:%(bg)s}model-viewer{width:%(w)dpx;height:%(h)dpx;background:%(bg)s}</style>
<model-viewer src="/%(src)s" camera-orbit="%(orbit)s" camera-target="%(target)s" field-of-view="%(fov)s"
  shadow-intensity="0.6" exposure="1.05" environment-image="neutral" interaction-prompt="none"></model-viewer>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("glb")
    ap.add_argument("out")
    ap.add_argument("--orbit", default="35deg 65deg auto")
    ap.add_argument("--target", default="auto auto auto")
    ap.add_argument("--fov", default="30deg")
    ap.add_argument("--size", default="1200x900")
    ap.add_argument("--bg", default="#0c1411")
    a = ap.parse_args()
    w, h = (int(x) for x in a.size.split("x"))
    glb = pathlib.Path(a.glb).resolve()
    src = glb.relative_to(ROOT).as_posix()
    tmp = ROOT / ("_poster_tmp_%d.html" % os.getpid())
    tmp.write_text(PAGE % dict(bg=a.bg, w=w, h=h, src=src, orbit=a.orbit, target=a.target, fov=a.fov),
                   encoding="utf-8")
    os.chdir(ROOT)
    handler = lambda *x, **k: http.server.SimpleHTTPRequestHandler(*x, directory=str(ROOT), **k)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        th.start()
        prof = os.environ.get("CHROME_PROFILE", str(ROOT.parent / ".poster-chrome-profile"))
        subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", "--use-angle=swiftshader",
                        "--enable-unsafe-swiftshader", "--user-data-dir=" + prof,
                        "--window-size=%d,%d" % (w, h), "--virtual-time-budget=15000",
                        "--screenshot=" + str(pathlib.Path(a.out).resolve()),
                        "http://127.0.0.1:%d/%s" % (port, tmp.name)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
        httpd.shutdown()
    tmp.unlink()
    print("wrote", a.out)


if __name__ == "__main__":
    main()
