#!/usr/bin/env python3
r"""Normalisation-robustness analysis (review round 2 — reviewers A & B).

Both the LCA methodologist and the orbital/atmospheric reviewer independently
objected that the orbital "regime dominance" (Table 3) and the catalogue-scale
"operational congestion dominates 86%" depend on the single 700 km / 500 kg
reference mission, whose orbital sub-scores are strongly imbalanced
(DGP_ref = 1.0, CC_ref ~ 2e-3, MC_ref ~ 64). Because that reference sits in a
sparse 700 km shell, CC_ref is near zero, so dividing any congested-shell
mission's CC by it inflates the normalised CC — which, the reviewers argue,
manufactures the dominance pattern rather than discovering it.

This script tests that objection directly. It recomputes the orbital
decomposition (which sub-category dominates) and the catalogue dominance
distribution under SEVERAL normalisation schemes, using the SAME cached raw
sub-scores (no MATLAB / OpenLCA needed — the raw DGP/CC/MC are cached). It then
reports the normalisation-INDEPENDENT facts (the distribution of ABSOLUTE
congestion exposure), which do not depend on any reference choice.

Schemes:
  A  single-reference (baseline, as published)
  B  catalogue-median  (each sub-category / its median over the N=300 sample)
  C  catalogue-geomean (robust central value)
  D  congested-shell reference (median sub-scores of the <600 km subset)

Usage: .venv/bin/python paper1_norm_robustness.py
Author: Federico Toson.
"""
import json, math
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
OUT = HERE / "outputs"
LAB = ["DGP", "CC", "MC"]

# --- cached raw sub-scores -------------------------------------------------
cases = {}
for mid in ["redpill_2p", "sentinel6", "envisat"]:
    o = json.load(open(OUT / mid / "results.json"))["raw_scores"]["orbital"]
    cases[mid] = np.array([o["DGP"], o["CC"], o["MC"]], float)

rsub = json.load(open(OUT / "redpill_2p" / "results.json"))["reference_subscores_orbital"]
REF = np.array([rsub["DGP"], rsub["CC"], rsub["MC"]], float)

cat = json.load(open(OUT / "catalogue_scale.json"))
RAW = np.array([[r["dgp"], r["cc"], r["mc"]] for r in cat], float)   # N x 3
alt = np.array([r["h"] for r in cat], float)


def gmean(x):
    x = x[x > 0]
    return math.exp(float(np.mean(np.log(x)))) if len(x) else 1.0


schemes = {
    "A single-reference (baseline)":     REF,
    "B catalogue-median":                np.median(RAW, axis=0),
    "C catalogue-geomean":               np.array([gmean(RAW[:, j]) for j in range(3)]),
    "D congested-shell ref (<600km med)": np.median(RAW[alt < 600], axis=0),
}


def dom_pct(denom):
    dom = np.argmax(RAW / denom, axis=1)
    return {LAB[k]: 100.0 * float(np.mean(dom == k)) for k in range(3)}


def case_decomp(vec, denom):
    I = vec / denom
    s = I.sum()
    return {LAB[k]: 100.0 * I[k] / s for k in range(3)}, LAB[int(np.argmax(I))]


print("=== denominators per scheme (DGP, CC, MC) ===")
for name, d in schemes.items():
    print(f"  {name:36} {d[0]:.4g}  {d[1]:.4g}  {d[2]:.4g}")

print("\n=== catalogue N=300: %% of missions where each sub-category DOMINATES ===")
print(f"{'scheme':38} {'DGP%':>6} {'CC%':>6} {'MC%':>6}")
summary = {}
for name, d in schemes.items():
    dd = dom_pct(d)
    summary[name] = dd
    print(f"{name:38} {dd['DGP']:6.0f} {dd['CC']:6.0f} {dd['MC']:6.0f}")

print("\n=== 3 case studies: dominant orbital sub-category per scheme ===")
for name, d in schemes.items():
    print(f"  [{name}]")
    for mid, vec in cases.items():
        sh, dom = case_decomp(vec, d)
        print(f"     {mid:11} dom={dom:3}  DGP/CC/MC = "
              f"{sh['DGP']:.0f}/{sh['CC']:.0f}/{sh['MC']:.0f}%")

# --- normalisation-INDEPENDENT facts --------------------------------------
cc = RAW[:, 1]
print("\n=== normalisation-independent facts (no reference involved) ===")
print(f"  absolute CC (sat-yr): median {np.median(cc):.3g}, "
      f"IQR [{np.percentile(cc,25):.3g}, {np.percentile(cc,75):.3g}], max {cc.max():.3g}")
print(f"  reference-shell raw CC = {REF[1]:.3g}")
print(f"  missions in shells denser than the 700 km reference (raw CC > CC_ref): "
      f"{100*np.mean(cc > REF[1]):.0f}%")
print(f"  missions below 600 km: {100*np.mean(alt < 600):.0f}%")

json.dump({"denominators": {k: v.tolist() for k, v in schemes.items()},
           "dominance_pct": summary,
           "abs_cc_median": float(np.median(cc)),
           "frac_denser_than_ref": float(np.mean(cc > REF[1])),
           "frac_below_600km": float(np.mean(alt < 600))},
          open(OUT / "norm_robustness.json", "w"), indent=1)
print(f"\nwritten {OUT/'norm_robustness.json'}")
