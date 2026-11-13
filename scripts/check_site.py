#!/usr/bin/env python3
"""只读检查案例数据、生成结果、站内链接与报告 manifest。

用法：python3 scripts/check_site.py [--artifacts <Omnifex 工程>/artifacts]
只用 Python 标准库；不启动浏览器、不访问网络、不修改生成文件。
"""
import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "omnifex" / "cases"
ERRORS = []


def fail(where, message):
    ERRORS.append(f"{where}: {message}")


def relative(path):
    return str(path.relative_to(ROOT))


def local_target(base, value):
    url = urlsplit(value)
    if url.scheme or url.netloc:
        return None, url.fragment
    path = unquote(url.path)
    target = (ROOT / path.lstrip("/")) if path.startswith("/") else base.parent / path
    if not path:
        target = base
    target = target.resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError("路径超出站点根目录")
    if target.is_dir():
        target = target / "index.html"
    return target, unquote(url.fragment)


def resource(value, where):
    if not isinstance(value, str) or not value:
        fail(where, "资源路径必须为非空字符串")
        return
    try:
        target, _ = local_target(CASES / "index.html", value)
        if target is None or not target.is_file():
            fail(where, f"本地资源不存在：{value}")
    except ValueError as exc:
        fail(where, f"{value}：{exc}")


def case_data(builder):
    records = []
    groups = {group[0] for group in builder.GROUPS}
    seen = set()
    for path in sorted((CASES / "data").glob("*.json")):
        if path.name.startswith("_"):
            continue
        where = relative(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            fail(where, f"无法读取 JSON：{exc}")
            continue
        if not isinstance(data, dict):
            fail(where, "案例必须是 JSON 对象")
            continue
        for key in ("id", "group", "project", "short", "title", "description"):
            if not isinstance(data.get(key), str) or not data[key].strip():
                fail(where, f"{key} 必须为非空字符串")
        case_id = data.get("id")
        if isinstance(case_id, str):
            if case_id != path.stem or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case_id):
                fail(where, "id 必须与文件名一致，且只用小写字母、数字和连字符")
            if case_id in seen:
                fail(where, f"重复 id：{case_id}")
            seen.add(case_id)
        if not isinstance(data.get("group"), str) or data["group"] not in groups:
            fail(where, f"group 必须属于 {', '.join(sorted(groups))}")
        if type(data.get("order")) is not int:
            fail(where, "order 必须为整数")
        for key in ("domain", "summary", "steps", "sources"):
            if not isinstance(data.get(key), list) or not data[key]:
                fail(where, f"{key} 必须为非空列表")
        for key in ("domain", "sources"):
            if isinstance(data.get(key), list) and any(not isinstance(x, str) or not x for x in data[key]):
                fail(where, f"{key} 必须只包含非空字符串")
        if data.get("thumb") is not None:
            resource(data["thumb"], where + ".thumb")
        if not isinstance(data.get("steps"), list):
            continue
        for i, step in enumerate(data["steps"]):
            sw = f"{where}.steps[{i}]"
            if not isinstance(step, dict) or not isinstance(step.get("title"), str) or not step["title"]:
                fail(sw, "步骤必须是包含非空 title 的对象")
                continue
            figures = step.get("figures", [])
            if not isinstance(figures, list):
                fail(sw, "figures 必须为列表")
                figures = []
            for j, figure in enumerate(figures):
                if not isinstance(figure, dict):
                    fail(sw, "figures 的每项必须为对象")
                    continue
                resource(figure.get("src"), f"{sw}.figures[{j}].src")
            if "compare" in step:
                comparison = step["compare"]
                if not isinstance(comparison, dict):
                    fail(sw, "compare 必须为对象")
                else:
                    for key in ("before", "after"):
                        resource(comparison.get(key), f"{sw}.compare.{key}")
            if "model" in step:
                model = step["model"]
                models = model.get("models") if isinstance(model, dict) else None
                if not isinstance(models, list) or not models:
                    fail(sw, "model.models 必须为非空列表")
                    continue
                for j, item in enumerate(models):
                    if not isinstance(item, dict):
                        fail(sw, "models 的每项必须为对象")
                        continue
                    for key in ("src", "poster"):
                        resource(item.get(key), f"{sw}.model.models[{j}].{key}")
        records.append(data)
    if not records:
        fail("cases/data", "没有案例数据")
    return records


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.links = []
        self.routes = set()
        self.counts = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        line = self.getpos()[0]
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if attrs.get("data-view"):
            self.routes.add(attrs["data-view"])
        if "data-case-count" in attrs:
            self.counts.append((attrs["data-case-count"], line))
        for key in ("src", "href", "poster", "data-src", "data-poster"):
            if attrs.get(key):
                self.links.append((attrs[key], line))


def pages_and_links(count):
    pages = {}
    for path in ROOT.rglob("*.html"):
        if any(part in {".git", "_t", "__pycache__"} for part in path.relative_to(ROOT).parts):
            continue
        if path.name.startswith(("_thumb_tmp_", "_poster_tmp_")):
            continue
        parser = Page()
        parser.feed(path.read_text(encoding="utf-8"))
        pages[path] = parser
        duplicate_ids = [key for key, n in Counter(parser.ids).items() if n > 1]
        if duplicate_ids:
            fail(relative(path), f"重复 HTML id：{', '.join(duplicate_ids)}")
        for value, line in parser.counts:
            if value != str(count):
                fail(f"{relative(path)}:{line}", f"data-case-count={value!r}，实际有 {count} 个案例")
    index = ROOT / "omnifex" / "index.html"
    if index not in pages or not pages[index].counts:
        fail("omnifex/index.html", "缺少 data-case-count，无法核对项目页案例数量")
    for path, parser in pages.items():
        for value, line in parser.links:
            where = f"{relative(path)}:{line}"
            try:
                target, fragment = local_target(path, value)
            except ValueError as exc:
                fail(where, f"{value}：{exc}")
                continue
            if target is None:
                continue
            if not target.is_file():
                fail(where, f"站内链接不存在：{value}")
            elif fragment and target in pages:
                dest = pages[target]
                # 题源报告以 data-view 注册 hash 路由，其余链接必须有真实锚点。
                if fragment not in dest.ids and fragment not in dest.routes and not fragment.startswith(":~:text="):
                    fail(where, f"站内锚点不存在：{value}")
    return len(pages)


def generated_pages(builder):
    try:
        cases = builder.load()
        expected = {"index.html": builder.build_index(cases)}
        for i, case in enumerate(cases):
            expected[case["id"] + ".html"] = builder.build_case(
                case, cases[i - 1] if i else None, cases[i + 1] if i + 1 < len(cases) else None)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, OSError) as exc:
        fail("build_cases.py", f"案例数据无法生成页面：{exc}")
        return
    for name, content in expected.items():
        path = CASES / name
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            fail(relative(path), "生成结果过时，请运行 python3 scripts/build_cases.py")
    for path in CASES.glob("*.html"):
        if path.name not in expected:
            fail(relative(path), "详情页没有对应 JSON；请核对是否留下已删除案例的旧页")


def manifest(artifacts):
    path = ROOT / "omnifex" / "manifest.json"
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(entries, list) or not entries:
            raise ValueError("manifest 必须为非空列表")
        seen = set()
        for entry in entries:
            name = entry["page"]
            if name in seen:
                fail(relative(path), f"重复页面：{name}")
            seen.add(name)
            output, _ = local_target(path, name)
            if output is None or not output.is_file():
                fail(relative(path), f"页面不存在：{name}")
                continue
            raw = output.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry["page_sha256"] or len(raw) != entry["bytes"]:
                fail(relative(output), "与 manifest 的页面哈希或字节数不符，请重新同步报告")
            if artifacts is not None:
                source = (artifacts / entry["source"]).resolve()
                if not source.is_relative_to(artifacts.resolve()) or not source.is_file():
                    fail(relative(path), f"源文件不存在或超出 artifacts 目录：{entry['source']}")
                elif hashlib.sha256(source.read_bytes()).hexdigest() != entry["source_sha256"]:
                    fail(entry["source"], "源文件已变化，请重新同步报告")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        fail(relative(path), f"manifest 无法验证：{exc}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifacts", type=Path, help="额外核对报告源文件的 SHA-256")
    args = ap.parse_args()
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("build_cases", ROOT / "scripts" / "build_cases.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    records = case_data(builder)
    generated_pages(builder)
    page_count = pages_and_links(len(records))
    manifest(args.artifacts)
    if ERRORS:
        for error in ERRORS:
            print("ERROR", error, file=sys.stderr)
        print(f"检查失败：{len(ERRORS)} 项。", file=sys.stderr)
        return 1
    print(f"检查通过：{len(records)} 个案例，{page_count} 个 HTML；数据、资源、站内链接、生成结果、案例数量和报告 manifest 一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
