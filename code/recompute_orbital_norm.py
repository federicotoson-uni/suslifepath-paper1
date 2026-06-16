#!/usr/bin/env python3
r"""[SUPERSEDED 15/06/2026] This per-sub-category normalisation is now native
in the pipeline (ssci.normalise_orbital + ssci_orchestrator.run_mission): a
fresh orchestrator run reproduces results.json directly, so this script is no
longer required. Kept for provenance and as a no-MATLAB re-normaliser of the
cached raw scores.

Re-normalise the orbital domain per sub-category (ISSUES R8 / reviewers
A#6, C#3, B#8), then update outputs/<mission>/results.json in place.

Problem: the orbital raw score was DGP + CC + MC summed in INCOMMENSURABLE
units (DGP dimensionless ~O(1-1000), CC in sat-yr ~O(1e-2), MC in
kg*criticality ~O(1e-1..1e3)). The raw sum is dominated by whichever term
has the largest unit magnitude (MC), independent of physics. The N=300
catalogue scale-up made this glaring: MC "dominated" 98% of missions purely
by units, CC 0% — confirming the reviewers' objection.

Fix (standard composite-indicator practice): normalise EACH sub-category to
the reference mission before aggregating, then average:
    I_O = (1/3) [ DGP/DGP_ref + CC/CC_ref + MC/MC_ref ]
with DGP_ref = 1 (R_col self-normalised), CC_ref and MC_ref the reference
mission's congestion and material-criticality (computed here from first
principles and checked against the cached reference orbital raw 65.227).

Atmospheric and terrestrial are unaffected. No MATLAB needed (raw DGP/CC/MC
are cached in results.json). Usage:
  .venv/bin/python recompute_orbital_norm.py [--write]
Author: Federico Toson.
"""
import csv, json, math, sys
from pathlib import Path
import numpy as np
import yaml
from ssci import DomainScores, normalise, ssci_linear, ssci_risk, weights_equal, weights_expert, sensitivity_weights

WRITE = "--write" in sys.argv
HERE = Path(__file__).parent
OUT = HERE / "outputs"
CAT = HERE.parent.parent / "Paper0_SimplifiedAlgorithm" / "data" / "celestrak_active.csv"
MU, RE = 398600.4418, 6378.137


def eta(h):
    return 0.3 if h < 600 else (1.0 if h >= 2000 else 0.3 + 0.7 * (h - 600) / 1400)


def density_at(h0, alts, dh=25.0):
    n = int(np.sum(np.abs(alts - h0) <= dh))
    r = RE + h0
    return n / (4 * math.pi * r ** 2 * 2 * dh)


def real_altitudes():
    a = []
    for row in csv.DictReader(open(CAT)):
        try:
            n = float(row["MEAN_MOTION"]) * 2 * math.pi / 86400.0
            e = float(row["ECCENTRICITY"])
            sma = (MU / n ** 2) ** (1 / 3.0)
            hp = sma * (1 - e) - RE
            if 0 < hp < 2000:
                a.append(hp)
        except (ValueError, KeyError, ZeroDivisionError):
            pass
    return np.array(a)


def main():
    alts = real_altitudes()
    # reference sub-scores
    DGP_ref = 1.0
    CC_ref = density_at(700, alts) * 50 ** 3 * 7          # T_op_ref = 7 yr
    refy = yaml.safe_load(open(HERE / "missions" / "_reference_smallsat.yaml"))
    MC_ref = sum(m["mass_kg"] * m["criticality_factor"] * eta(700)
                 for m in refy["materials"])
    print(f"reference sub-scores: DGP_ref={DGP_ref}, CC_ref={CC_ref:.5g}, "
          f"MC_ref={MC_ref:.5g}  (sum {DGP_ref+CC_ref+MC_ref:.4g} vs cached 65.227)")

    w_eq, w_ex = weights_equal(), weights_expert()
    print(f"\n{'mission':11} {'IO_old':>8} {'IO_new':>8} | dominant | "
          f"{'SSCI_old':>9} {'SSCI_new':>9} | {'gap_old':>8} {'gap_new':>8}")
    print("-" * 86)
    for mid in ["redpill_2p", "sentinel6", "envisat"]:
        f = OUT / mid / "results.json"
        d = json.load(open(f))
        o = d["raw_scores"]["orbital"]
        iDGP, iCC, iMC = o["DGP"] / DGP_ref, o["CC"] / CC_ref, o["MC"] / MC_ref
        iO_new = (iDGP + iCC + iMC) / 3.0
        ssum = iDGP + iCC + iMC
        shares = {"DGP": 100 * iDGP / ssum, "CC": 100 * iCC / ssum, "MC": 100 * iMC / ssum}
        dom = max(shares, key=shares.get)

        iT = d["ssci"]["scores_norm"]["terrestrial"]
        iA = d["ssci"]["scores_norm"]["atmospheric"]
        iO_old = d["ssci"]["scores_norm"]["orbital"]
        ssci_old = d["ssci"]["SSCI_linear_equal"]
        gap_old = (iT - ssci_old) / ssci_old * 100

        sn = np.array([iT, iA, iO_new])
        ssci_new = ssci_linear(sn, w_eq)
        gap_new = (iT - ssci_new) / ssci_new * 100
        print(f"{mid:11} {iO_old:8.3g} {iO_new:8.3g} | {dom:3s} {shares[dom]:4.0f}% | "
              f"{ssci_old:9.3g} {ssci_new:9.3g} | {gap_old:7.1f}% {gap_new:7.1f}%")

        if WRITE:
            d["ssci"]["scores_norm"]["orbital"] = iO_new
            d["raw_scores"]["orbital"]["breakdown_pct"] = shares
            d["raw_scores"]["orbital"]["normalised_subscores"] = {
                "DGP": iDGP, "CC": iCC, "MC": iMC}
            d["ssci"]["SSCI_linear_equal"] = ssci_linear(sn, w_eq)
            d["ssci"]["SSCI_linear_expert"] = ssci_linear(sn, w_ex)
            d["ssci"]["SSCI_risk"] = ssci_risk(sn)
            d["sensitivity_dirichlet_10k"] = sensitivity_weights(sn, 10000, seed=42)
            d["reference_subscores_orbital"] = {"DGP": DGP_ref, "CC": CC_ref, "MC": MC_ref}
            json.dump(d, open(f, "w"), indent=1)

    print(f"\n{'WROTE results.json' if WRITE else 'DRY RUN (--write to update)'}")


if __name__ == "__main__":
    main()
