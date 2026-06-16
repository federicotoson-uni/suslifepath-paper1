#!/usr/bin/env python3
r"""eta^orbit sensitivity (review round 2).

The orbit-loss multiplier eta^orbit (Section 3.2.3) uses a 0.3 floor below
600 km, saturation at 1.0 above 2000 km, and a linear ramp between. Reviewers
flagged the floor and anchors as heuristic. This sweeps them on the SAME cached
raw sub-scores (MC scales by eta_alt(h)/eta_base(h); DGP and CC are unaffected
by eta; the reference MC scales the same way), and checks that
  (i)   the 3-case orbital dominance (RedPill CC / Sentinel-6 MC / ENVISAT DGP),
  (ii)  the SSCI magnitude ranking, and
  (iii) the catalogue MC-dominance fraction
survive. No MATLAB / OpenLCA needed.

Usage: .venv/bin/python paper1_eta_sensitivity.py
Author: Federico Toson.
"""
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
OUT = HERE / "outputs"
LAB = ["DGP", "CC", "MC"]
ALT = {"redpill_2p": 550.0, "sentinel6": 1336.0, "envisat": 770.0}
REF_ALT = 700.0
BASE = (0.3, 600.0, 2000.0)          # params used when results.json was generated


def eta(h, floor, lo, hi):
    if h < lo:
        return floor
    if h >= hi:
        return 1.0
    return floor + (1.0 - floor) * (h - lo) / (hi - lo)


models = {
    "baseline (0.3,600,2000)": (0.3, 600, 2000),
    "floor 0.1":               (0.1, 600, 2000),
    "floor 0.5":               (0.5, 600, 2000),
    "anchors 500-1500":        (0.3, 500, 1500),
    "anchors 700-2500":        (0.3, 700, 2500),
}

cases = {mid: json.load(open(OUT / mid / "results.json"))["raw_scores"]["orbital"]
         for mid in ALT}
rsub = json.load(open(OUT / "redpill_2p" / "results.json"))["reference_subscores_orbital"]
cat = json.load(open(OUT / "catalogue_scale.json"))

print(f"{'eta model':24} | {'redpill':>8} {'sentinel':>8} {'envisat':>8} | "
      f"{'rank ok':>7} | {'cat MC-dom%':>11}")
print("-" * 78)
for name, (fl, lo, hi) in models.items():
    mcref = rsub["MC"] * eta(REF_ALT, fl, lo, hi) / eta(REF_ALT, *BASE)
    doms, iO = [], {}
    for mid in ALT:
        h, c = ALT[mid], cases[mid]
        mc = c["MC"] * eta(h, fl, lo, hi) / eta(h, *BASE)
        sub = [c["DGP"] / rsub["DGP"], c["CC"] / rsub["CC"], mc / mcref]
        iO[mid] = sum(sub) / 3.0
        doms.append(LAB[int(np.argmax(sub))])
    rank_ok = (iO["redpill_2p"] < iO["envisat"]) and (iO["sentinel6"] < iO["envisat"])
    n_mc = sum(1 for r in cat
               if np.argmax([r["dgp"] / rsub["DGP"], r["cc"] / rsub["CC"],
                             (r["mc"] * eta(r["h"], fl, lo, hi) / eta(r["h"], *BASE)) / mcref]) == 2)
    print(f"{name:24} | {doms[0]:>8} {doms[1]:>8} {doms[2]:>8} | "
          f"{str(rank_ok):>7} | {100*n_mc/len(cat):10.0f}%")
