"""Build diagnostic checkpoints around a real start step (numpy only, no GPU).

All variants are written in one pass over the start checkpoint, keeping its
shard layout, dtype and non-weight files (config, tokenizer, chat template),
so the outputs load like any HF checkpoint and can go straight to eval_pass8.py.

Notation: W0 = step 0, W_s = real start, W_T = real target,
delta = W_s - W0 (cumulative update), D = W_T - W_s (real later update).

Variant specs (--variant, repeatable; options after ':' separated by ','):
  scale:c=2          W_s + (c-1)*delta        (= W0 + c*delta; dose curve)
  rev:c=2            W_s - (c-1)*delta        (push in the opposite direction)
  randsign:c=2       W_s + (c-1)*|delta|*eps  (same support and magnitudes, random signs)
  supp               W_s + D on supp(delta), W_s elsewhere      (exact, no rounding)
  comp               W_s + D outside supp(delta), W_s on it     (exact, no rounding)
  par                W_s + alpha_t*delta      (alpha_t = <D,delta>/|delta|^2 per tensor)
  orth               W_T - alpha_t*delta      (the part of D orthogonal to delta)
  oraclemag          W_s + (beta_t-1)*delta   (beta_t = |W_T-W0|/|delta| per tensor)
Common options: round=rne|sr (BF16 rounding: nearest-even like a normal save,
or stochastic rounding, which keeps sub-ULP pushes in expectation), seed=N.

Example (runA, start 40, target 80):
  H=$CHECKPOINT_ROOT/models/olmo3_rlvr_retrain_20261009/runA
  python make_diag_ckpts.py --w0 <official step_1600> \\
    --start 40=$H/global_step_40/actor/huggingface --target 80=$H/global_step_80/actor/huggingface \\
    --out-root <models root>/diag_runA \\
    --variant scale:c=1.5 --variant scale:c=2 --variant scale:c=3 --variant scale:c=4 \\
    --variant scale:c=1.25,round=sr --variant supp --variant comp \\
    --variant par,round=sr --variant orth,round=sr --variant oraclemag,round=sr \\
    --variant randsign:c=2 --variant rev:c=2
Each variant lands in <out-root>/<label>/ with <out-root>/<label>.manifest.json
recording the nominal and the actually saved push.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from st_io import (Ckpt, ShardWriter, chunk_rng, copy_non_weight_files, from_f32,  # noqa: E402
                   row_chunks, to_f32, DEFAULT_CHUNK_ELEMS)

KINDS = {"scale", "rev", "randsign", "supp", "comp", "par", "orth", "oraclemag"}
NEEDS_T = {"supp", "comp", "par", "orth", "oraclemag"}
NEEDS_C = {"scale", "rev", "randsign"}


def parse_variant(spec: str) -> dict:
    kind, _, opts = spec.partition(":")
    if "," in kind and not opts:  # allow "par,round=sr"
        kind, _, opts = kind.partition(",")
    if kind not in KINDS:
        raise ValueError(f"unknown variant kind {kind!r} in {spec!r}")
    v = {"kind": kind, "c": None, "round": "rne", "seed": 0}
    for kv in filter(None, opts.split(",")):
        k, _, val = kv.partition("=")
        if k == "c":
            v["c"] = float(val)
        elif k == "round":
            if val not in ("rne", "sr"):
                raise ValueError(f"round must be rne or sr in {spec!r}")
            v["round"] = val
        elif k == "seed":
            v["seed"] = int(val)
        else:
            raise ValueError(f"unknown option {k!r} in {spec!r}")
    if kind in NEEDS_C and v["c"] is None:
        raise ValueError(f"{kind} needs c=... in {spec!r}")
    return v


def variant_label(prefix: str, s: int, v: dict) -> str:
    lab = f"{prefix}_s{s}_{v['kind']}"
    if v["c"] is not None:
        lab += f"_c{v['c']:g}"
    if v["kind"] not in ("supp", "comp"):
        lab += f"_{v['round']}"
    if v["kind"] == "randsign" or v["round"] == "sr":
        lab += f"_seed{v['seed']}"
    return lab


_G = {}


def _init(cfg):
    _G["cfg"] = cfg
    _G["w0"] = Ckpt(cfg["w0"])
    _G["ws"] = Ckpt(cfg["start_path"])
    _G["wt"] = Ckpt(cfg["target_path"]) if cfg["target_path"] else None


def prepass_tensor(name):
    """Per-tensor <D,delta>, |delta|^2, |W_T-W0|^2 for alpha/beta."""
    cfg, w0c, wsc, wtc = _G["cfg"], _G["w0"], _G["ws"], _G["wt"]
    ip = sq_d = sq_T = 0.0
    for r0, r1 in row_chunks(wsc.shape(name), cfg["chunk_elems"]):
        w0 = w0c.read_rows(name, r0, r1).astype(np.float64)
        ws = wsc.read_rows(name, r0, r1).astype(np.float64)
        wt = wtc.read_rows(name, r0, r1).astype(np.float64)
        d = ws - w0
        ip += float(np.dot((wt - ws).ravel(), d.ravel()))
        sq_d += float(np.dot(d.ravel(), d.ravel()))
        sq_T += float(np.dot((wt - w0).ravel(), (wt - w0).ravel()))
    alpha = ip / sq_d if sq_d > 0 else 0.0
    beta = math.sqrt(sq_T / sq_d) if sq_d > 0 else 1.0
    return name, {"alpha": alpha, "beta": beta, "sq_delta": sq_d, "sq_T": sq_T, "ip_D_delta": ip}


def write_shard(shard):
    cfg, w0c, wsc, wtc = _G["cfg"], _G["w0"], _G["ws"], _G["wt"]
    variants, coef = cfg["variants"], cfg["coef"]
    layout = [(n, wsc.dtype(n), wsc.shape(n)) for n in wsc.shard_tensors(shard)]
    writers = {v["label"]: ShardWriter(os.path.join(v["out_dir"], shard), layout, wsc.shard_metadata(shard))
               for v in variants}
    keys = ("n", "nz", "sq_saved", "sq_nominal", "ip_delta", "ip_D", "sq_delta", "sq_D", "rounded_away")
    st = {v["label"]: dict.fromkeys(keys, 0.0) for v in variants}
    for name, dt, shape in layout:
        same_dt = wtc is not None and wtc.dtype(name) == dt
        for r0, r1 in row_chunks(shape, cfg["chunk_elems"]):
            ws_raw = wsc.read_raw(name, r0, r1)
            ws = to_f32(ws_raw, dt)
            w0 = w0c.read_rows(name, r0, r1)
            delta = ws - w0
            wt_raw = wtc.read_raw(name, r0, r1) if wtc is not None else None
            wt = to_f32(wt_raw, wtc.dtype(name)) if wtc is not None else None
            on = delta != 0
            for v in variants:
                k, lab = v["kind"], v["label"]
                if k in ("supp", "comp"):
                    mask = on if k == "supp" else ~on
                    if same_dt:
                        raw = np.where(mask, wt_raw, ws_raw)
                        nominal = to_f32(raw, dt)
                    else:
                        nominal = np.where(mask, wt, ws)
                        raw = from_f32(nominal, dt)
                else:
                    if k == "scale":
                        nominal = ws + np.float32(v["c"] - 1.0) * delta
                    elif k == "rev":
                        nominal = ws - np.float32(v["c"] - 1.0) * delta
                    elif k == "randsign":
                        eps = chunk_rng(v["seed"], name, r0).integers(0, 2, size=delta.shape).astype(np.float32)
                        nominal = ws + np.float32(v["c"] - 1.0) * np.abs(delta) * (2 * eps - 1)
                    elif k == "par":
                        nominal = ws + np.float32(coef[name]["alpha"]) * delta
                    elif k == "orth":
                        nominal = wt - np.float32(coef[name]["alpha"]) * delta
                    elif k == "oraclemag":
                        nominal = ws + np.float32(coef[name]["beta"] - 1.0) * delta
                    rng = chunk_rng(v["seed"] + 1_000_003, name, r0) if v["round"] == "sr" else None
                    raw = from_f32(nominal, dt, v["round"], rng)
                saved = to_f32(raw, dt)
                a, an = saved - ws, nominal - ws
                s = st[lab]
                s["n"] += a.size
                s["nz"] += int((a != 0).sum())
                s["rounded_away"] += int(((an != 0) & (a == 0)).sum())
                s["sq_saved"] += float(np.dot(a.ravel().astype(np.float64), a.ravel().astype(np.float64)))
                s["sq_nominal"] += float(np.dot(an.ravel().astype(np.float64), an.ravel().astype(np.float64)))
                s["ip_delta"] += float(np.dot(a.ravel().astype(np.float64), delta.ravel().astype(np.float64)))
                s["sq_delta"] += float(np.dot(delta.ravel().astype(np.float64), delta.ravel().astype(np.float64)))
                if wt is not None:
                    dd = (wt - ws).ravel().astype(np.float64)
                    s["ip_D"] += float(np.dot(a.ravel().astype(np.float64), dd))
                    s["sq_D"] += float(np.dot(dd, dd))
                writers[lab].write(name, raw)
    for w in writers.values():
        w.close()
    return shard, st


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--w0", required=True, help="step-0 checkpoint (official start)")
    ap.add_argument("--start", required=True, metavar="STEP=PATH", help="real start checkpoint")
    ap.add_argument("--target", default=None, metavar="STEP=PATH",
                    help="real target checkpoint (needed by supp, comp, par, orth, oraclemag)")
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--variant", action="append", required=True, metavar="SPEC")
    ap.add_argument("--label-prefix", default="diag")
    ap.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--chunk-elems", type=int, default=DEFAULT_CHUNK_ELEMS)
    ap.add_argument("--dry-run", action="store_true", help="print labels and disk estimate only")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    s_step, s_path = args.start.split("=", 1)
    t_step, t_path = (args.target.split("=", 1) if args.target else (None, None))
    variants = [parse_variant(sp) for sp in args.variant]
    if any(v["kind"] in NEEDS_T for v in variants) and not t_path:
        ap.error("supp/comp/par/orth/oraclemag need --target STEP=PATH")
    labels = set()
    for v in variants:
        v["label"] = variant_label(args.label_prefix, int(s_step), v)
        if v["label"] in labels:
            ap.error(f"duplicate variant {v['label']}")
        labels.add(v["label"])
        v["out_dir"] = os.path.join(args.out_root, v["label"])

    wsc = Ckpt(s_path)
    total_bytes = sum(os.path.getsize(os.path.join(s_path, sh)) for sh in wsc.shards())
    print(f"start step {s_step}, target step {t_step}, {len(variants)} variants, "
          f"about {len(variants) * total_bytes / 2**30:.1f} GiB to write", flush=True)
    for v in variants:
        print(f"  {v['label']}  ->  {v['out_dir']}")
    if args.dry_run:
        return
    for v in variants:
        if os.path.exists(v["out_dir"]) and os.listdir(v["out_dir"]) and not args.overwrite:
            ap.error(f"{v['out_dir']} exists and is not empty (use --overwrite)")
        os.makedirs(v["out_dir"], exist_ok=True)

    cfg = {"w0": args.w0, "start_path": s_path, "target_path": t_path,
           "chunk_elems": args.chunk_elems, "variants": variants, "coef": {}}
    t0 = time.time()
    if any(v["kind"] in ("par", "orth", "oraclemag") for v in variants):
        names = sorted(wsc.names(), key=lambda n: -int(np.prod(wsc.shape(n))))
        with Pool(args.workers, initializer=_init, initargs=(cfg,)) as pool:
            cfg["coef"] = dict(pool.imap_unordered(prepass_tensor, names))
        print(f"prepass done ({time.time() - t0:.0f}s)", flush=True)

    shards = wsc.shards()
    totals = {v["label"]: {} for v in variants}
    with Pool(min(args.workers, len(shards)), initializer=_init, initargs=(cfg,)) as pool:
        for shard, st in pool.imap_unordered(write_shard, shards):
            for lab, d in st.items():
                for k, x in d.items():
                    totals[lab][k] = totals[lab].get(k, 0) + x
            print(f"  wrote {shard} for all variants ({time.time() - t0:.0f}s)", flush=True)

    for v in variants:
        copy_non_weight_files(s_path, v["out_dir"])
        t = totals[v["label"]]
        derived = {
            "frac_elements_changed_vs_start": t["nz"] / t["n"],
            "frac_nominal_changes_rounded_away": t["rounded_away"] / t["n"],
            "push_saved_over_delta": math.sqrt(t["sq_saved"] / t["sq_delta"]) if t["sq_delta"] else None,
            "push_nominal_over_delta": math.sqrt(t["sq_nominal"] / t["sq_delta"]) if t["sq_delta"] else None,
            "c_eff_saved_along_delta": 1 + t["ip_delta"] / t["sq_delta"] if t["sq_delta"] else None,
        }
        if t.get("sq_D"):
            derived["cos_saved_push_vs_real_later_update"] = (
                t["ip_D"] / math.sqrt(t["sq_saved"] * t["sq_D"]) if t["sq_saved"] else 0.0)
            derived["saved_push_over_real_later_update"] = math.sqrt(t["sq_saved"] / t["sq_D"])
        manifest = {"label": v["label"], "spec": {k: v[k] for k in ("kind", "c", "round", "seed")},
                    "w0": args.w0, "start": {"step": int(s_step), "path": s_path},
                    "target": {"step": int(t_step), "path": t_path} if t_path else None,
                    "out_dir": v["out_dir"], "totals": t, "derived": derived}
        if v["kind"] in ("par", "orth", "oraclemag"):
            al = [c["alpha"] for c in cfg["coef"].values() if c["sq_delta"] > 0]
            be = [c["beta"] for c in cfg["coef"].values() if c["sq_delta"] > 0]
            manifest["per_tensor_coef_summary"] = {
                "alpha_median": float(np.median(al)) if al else None,
                "beta_median": float(np.median(be)) if be else None,
                "tensors_with_zero_delta": sum(1 for c in cfg["coef"].values() if c["sq_delta"] == 0)}
        with open(os.path.join(args.out_root, v["label"] + ".manifest.json"), "w") as f:
            json.dump(manifest, f, indent=1)
        print(f"{v['label']}: changed {derived['frac_elements_changed_vs_start']:.2%} of elements, "
              f"saved push {derived['push_saved_over_delta']:.3f}x |delta| "
              f"(nominal {derived['push_nominal_over_delta']:.3f}x), "
              f"{derived['frac_nominal_changes_rounded_away']:.2%} of elements rounded back to W_s", flush=True)
    print(f"done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
