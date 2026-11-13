#!/usr/bin/env python3
"""Paired per-problem analysis of the diagnostic-checkpoint eval against the v1 short-horizon eval.

Cells come from three output roots (v1 full, diag canary, diag full); every cell decodes the
same problems with the same protocol and seed, so each contrast is a per-problem difference
with a bootstrap interval over problems. Cells that are not present yet are skipped.
Weight-space numbers (push, cos vs the real later update) are joined from the build manifests.
"""
import argparse, csv, json, random
from pathlib import Path

DATA = Path("$DATA_ROOT")
ROOTS = [DATA / "output/shorthorizon_eval_20261011_v1",
         DATA / "output/diag_eval_20261012_v1_canary",
         DATA / "output/diag_eval_20261012_v1"]
MATRIX = Path(__file__).resolve().parent / "eval_pkg_diag_v1/sh_matrix.tsv"
MANIFESTS = DATA / "models/experiments/rlvr_diag_20261012/diag_runA"
BENCHES = ("math500", "gsm8k")
N = 8

U40, U64, U80 = "sh_real_runA_u40", "sh_real_runA_u64", "sh_real_runA_u80"
S40 = "dg_runA_s40_"
PAIRS = [
    # cross-job reproducibility first
    ("dg_anchor_real_runA_u64", U64, "anchor: same u64 bytes, new job"),
    # SR vs RNE for the same extrapolation (the BF16 rounding question)
    ("dg_runA_s64_scale_c1p19_sr_seed0", "sh_qh_maglin_runA_P64_T80", "s64 mag c1.19: SR vs saved RNE"),
    ("dg_runA_s64_scale_c1p19_sr_seed0", U64, "s64 mag c1.19 SR vs donor u64"),
    ("dg_runA_s40_scale_c1p88_sr_seed0", "sh_qh_maglin_runA_P40_T80", "s40 mag c1.88: SR vs saved RNE"),
    ("dg_runA_s40_scale_c1p88_sr_seed0", U40, "s40 mag c1.88 SR vs donor u40"),
    ("dg_runA_s40_scale_c1p25_sr_seed0", U40, "s40 c1.25 SR vs donor"),
    # dose curve along delta_40 (RNE)
    ("dg_runA_s40_scale_c1p5_rne", U40, "s40 dose c1.5 vs donor"),
    ("dg_runA_s40_scale_c2_rne", U40, "s40 dose c2 vs donor"),
    ("dg_runA_s40_scale_c3_rne", U40, "s40 dose c3 vs donor"),
    ("dg_runA_s40_scale_c4_rne", U40, "s40 dose c4 vs donor"),
    ("dg_runA_s64_scale_c2_rne", U64, "s64 dose c2 vs donor"),
    # direction controls at c=2
    ("dg_runA_s40_randsign_c2_rne_seed0", "dg_runA_s40_scale_c2_rne", "random sign vs real sign (c2)"),
    ("dg_runA_s40_rev_c2_rne", "dg_runA_s40_scale_c2_rne", "reverse vs forward (c2)"),
    ("dg_runA_s40_randsign_c2_rne_seed0", U40, "random sign c2 vs donor"),
    ("dg_runA_s40_rev_c2_rne", U40, "reverse c2 vs donor"),
    # where the real later update's value lives
    ("dg_runA_s40_supp", U40, "s40 supp(D) vs donor"),
    ("dg_runA_s40_comp", U40, "s40 comp(D) vs donor"),
    ("dg_runA_s40_comp", "dg_runA_s40_supp", "s40 comp vs supp"),
    ("dg_runA_s40_supp", U80, "s40 supp vs target u80"),
    ("dg_runA_s40_comp", U80, "s40 comp vs target u80"),
    ("dg_runA_s64_supp", U64, "s64 supp(D) vs donor"),
    ("dg_runA_s64_comp", U64, "s64 comp(D) vs donor"),
    ("dg_runA_s64_comp", "dg_runA_s64_supp", "s64 comp vs supp"),
    ("dg_runA_s64_supp", U80, "s64 supp vs target u80"),
    ("dg_runA_s64_comp", U80, "s64 comp vs target u80"),
    ("dg_runA_s40_par_sr_seed0", U40, "s40 par(D) vs donor"),
    ("dg_runA_s40_orth_sr_seed0", U40, "s40 orth(D) vs donor"),
    ("dg_runA_s40_orth_sr_seed0", U80, "s40 orth vs target u80"),
    ("dg_runA_s40_oraclemag_sr_seed0", U40, "s40 oracle magnitude vs donor"),
    ("dg_runA_s40_oraclemag_sr_seed0", "dg_runA_s40_scale_c1p88_sr_seed0", "oracle magnitude vs fitted c1.88"),
    # reference from v1
    (U80, U40, "real 40 updates (u40->u80)"),
    (U80, U64, "real 16 updates (u64->u80)"),
]


def find(label, bench):
    for r in ROOTS[::-1]:
        p = r / bench / f"{label}.results.jsonl"
        if p.exists() and (r / bench / f"{label}.json").exists():
            return r
    return None


def rows(root, bench, label):
    out = {}
    for line in (root / bench / f"{label}.results.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            if "_meta" not in r:
                if r["uid"] in out:
                    raise ValueError(f"duplicate uid {r['uid']} in {label}/{bench}")
                out[r["uid"]] = r
    return out


def boot(a, b, uids, reps=10000, seed=0):
    rng = random.Random(seed)
    d = [(a[u] - b[u]) / N for u in uids]
    n = len(d)
    pt = sum(d) / n
    draws = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(reps))
    return pt, draws[int(0.025 * reps)], draws[int(0.975 * reps)]


def manifest(label):
    if not label.startswith("dg_runA_"):
        return {}
    for p in MANIFESTS.glob("*.manifest.json"):
        m = json.loads(p.read_text())
        if m["label"].replace(".", "p").replace("diag_runA_", "dg_runA_") == label:
            return m["derived"]
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(Path(__file__).resolve().parent / "diag_eval_analysis"))
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(exist_ok=True)
    labels = {"sh_real_runA_u0", U40, U64, U80, "sh_qh_maglin_runA_P40_T80", "sh_qh_maglin_runA_P64_T80",
              "sh_lin_elem_runA_P40_T80", "sh_lin_elem_runA_P64_T80", "sh_randctl_runA_P40_T80"}
    for line in MATRIX.read_text().splitlines()[1:]:
        labels.add(line.split("\t")[3])
    cache, cells = {}, []
    for label in sorted(labels):
        for bench in BENCHES:
            root = find(label, bench)
            if root is None:
                continue
            rs = rows(root, bench, label)
            fin = json.loads((root / bench / f"{label}.json").read_text())
            n = sum(r["n_samples"] for r in rs.values())
            cache[(label, bench)] = {u: r["correct"] for u, r in rs.items()}
            m = manifest(label)
            cells.append({"label": label, "bench": bench, "root": root.name,
                          "pass@1": fin["pass@1"], "pass@8": fin.get("pass@8"),
                          "cap_rate": sum(r.get("cap_hits", 0) for r in rs.values()) / n,
                          "mean_len": sum(r["sum_tokens"] for r in rs.values()) / n,
                          "n_problems": fin["n_problems"],
                          "push_over_delta": m.get("push_saved_over_delta"),
                          "c_eff": m.get("c_eff_saved_along_delta"),
                          "cos_vs_real_later": m.get("cos_saved_push_vs_real_later_update"),
                          "push_over_real_later": m.get("saved_push_over_real_later_update"),
                          "frac_changed": m.get("frac_elements_changed_vs_start")})
    print(f"{'label':36s} {'bench':8s} {'p@1':>7s} {'p@8':>7s} {'cap':>6s} {'len':>6s} {'push/|d|':>8s} {'cosD':>6s}")
    for c in cells:
        f = lambda x, s: (s % x) if isinstance(x, (int, float)) else "-"
        print(f"{c['label'][:36]:36s} {c['bench']:8s} {c['pass@1']:7.4f} {f(c['pass@8'],'%7.4f'):>7s} "
              f"{c['cap_rate']:6.3f} {c['mean_len']:6.0f} {f(c['push_over_delta'],'%8.3f'):>8s} {f(c['cos_vs_real_later'],'%+6.3f'):>6s}")
    res = []
    print(f"\n{'contrast':44s} {'bench':8s} {'diff':>8s} {'lo':>8s} {'hi':>8s} excl0")
    for a, b, name in PAIRS:
        for bench in BENCHES:
            if (a, bench) not in cache or (b, bench) not in cache:
                continue
            ca, cb = cache[(a, bench)], cache[(b, bench)]
            if set(ca) != set(cb):
                raise ValueError(f"uid sets differ: {a} vs {b} on {bench}")
            d, lo, hi = boot(ca, cb, sorted(ca))
            ex = lo > 0 or hi < 0
            print(f"{name[:44]:44s} {bench:8s} {d:+8.4f} {lo:+8.4f} {hi:+8.4f} {'yes' if ex else 'no'}")
            res.append({"a": a, "b": b, "name": name, "bench": bench, "diff": d, "lo": lo, "hi": hi,
                        "excludes_zero": ex, "n_problems": len(ca)})
    with open(out / "cells.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cells[0]))
        w.writeheader()
        w.writerows(cells)
    (out / "contrasts.json").write_text(json.dumps({"roots": [str(r) for r in ROOTS], "contrasts": res}, indent=1))
    print(f"\nwrote {out}/cells.csv, contrasts.json")


if __name__ == "__main__":
    main()
