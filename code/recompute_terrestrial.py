#!/usr/bin/env python3
r"""Recompute the terrestrial domain after the water re-grounding (ISSUES R1)
and update outputs/<mission>/results.json in place, WITHOUT touching the
atmospheric/orbital domains (which the water fix does not affect, so no
MATLAB bridge is needed).

For each of the four product systems it pulls the new EF 3.1 weighted single
score (Pt) from the running OpenLCA IPC server, renormalises I_T against the
reference, recombines with the cached atmospheric/orbital normalised scores,
and recomputes the SSCI variants + the Dirichlet weight sensitivity (seed 42,
matching the orchestrator). Prints old->new for every headline number.

Usage:  .venv/bin/python recompute_terrestrial.py [--write]
Author: Federico Toson.
"""
import json, sys
from pathlib import Path
import numpy as np
import olca_ipc as ipc
import olca_schema as o
from ssci import DomainScores, compute_ssci, normalise, sensitivity_weights

WRITE = "--write" in sys.argv
HERE = Path(__file__).parent
OUT = HERE / "outputs"
PS = {"redpill_2p": "redpill_2p_v1", "sentinel6": "sentinel6_v1",
      "envisat": "envisat_v1"}
REF_PS = "smallsat_700km_sso_v1"


def terrestrial_pt(client, ef, nw, systems, ps_name):
    t = systems[ps_name]
    setup = o.CalculationSetup(
        target=o.Ref(ref_type=o.RefType.ProductSystem, id=t.id),
        impact_method=o.Ref(ref_type=o.RefType.ImpactMethod, id=ef.id),
        nw_set=o.Ref(id=nw.id, name=nw.name))
    r = client.calculate(setup); r.wait_until_ready()
    by_cat = {iv.impact_category.name: iv.amount for iv in r.get_total_impacts()
              if iv.impact_category}
    pt = float(sum(w.amount for w in r.get_weighted_impacts()))
    r.dispose()
    return pt, by_cat


def main():
    c = ipc.Client(8080)
    systems = {p.name: p for p in c.get_descriptors(o.ProductSystem)}
    ef = next(m for m in c.get_descriptors(o.ImpactMethod) if "EF 3.1" in (m.name or ""))
    nw = (c.get(o.ImpactMethod, ef.id).nw_sets or [None])[0]

    ref_pt, _ = terrestrial_pt(c, ef, nw, systems, REF_PS)
    print(f"reference terrestrial: {ref_pt:.4g} Pt\n")
    print(f"{'mission':11} {'IT_old':>9} {'IT_new':>9} | "
          f"{'SSCI_old':>9} {'SSCI_new':>9} | {'gap_old':>8} {'gap_new':>8}")
    print("-" * 74)

    for mid, ps_name in PS.items():
        f = OUT / mid / "results.json"
        d = json.load(open(f))
        mis_pt, by_cat = terrestrial_pt(c, ef, nw, systems, ps_name)

        iA = d["ssci"]["scores_norm"]["atmospheric"]
        iO = d["ssci"]["scores_norm"]["orbital"]
        iT_old = d["ssci"]["scores_norm"]["terrestrial"]
        ssci_old = d["ssci"]["SSCI_linear_equal"]
        gap_old = (iT_old - ssci_old) / ssci_old * 100

        # recompute with new terrestrial, cached atmospheric/orbital
        atm_raw = d["raw_scores"]["atmospheric"]["raw_score"]
        orb_raw = d["raw_scores"]["orbital"]["raw_score"]
        ref_atm = d["reference_raw_scores"]["atmospheric"]
        ref_orb = d["reference_raw_scores"]["orbital"]
        scores = DomainScores(mis_pt, atm_raw, orb_raw)
        reference = DomainScores(ref_pt, ref_atm, ref_orb)
        res = compute_ssci(scores, reference)
        sn = normalise(scores, reference)
        sens = sensitivity_weights(sn, n_samples=10000, seed=42)

        iT_new = res["scores_norm"]["terrestrial"]
        ssci_new = res["SSCI_linear_equal"]
        gap_new = (iT_new - ssci_new) / ssci_new * 100
        print(f"{mid:11} {iT_old:9.3g} {iT_new:9.3g} | "
              f"{ssci_old:9.3g} {ssci_new:9.3g} | {gap_old:7.1f}% {gap_new:7.1f}%")

        if WRITE:
            d["raw_scores"]["terrestrial"]["raw_score"] = mis_pt
            d["raw_scores"]["terrestrial"]["by_impact_category"] = by_cat
            d["raw_scores"]["terrestrial"]["source"] = "ef31"
            d["reference_raw_scores"]["terrestrial"] = ref_pt
            d["ssci"]["scores_norm"] = res["scores_norm"]
            d["ssci"]["SSCI_linear_equal"] = res["SSCI_linear_equal"]
            d["ssci"]["SSCI_linear_expert"] = res["SSCI_linear_expert"]
            d["ssci"]["SSCI_risk"] = res["SSCI_risk"]
            d["sensitivity_dirichlet_10k"] = sens
            json.dump(d, open(f, "w"), indent=1)

    print(f"\n{'WROTE results.json' if WRITE else 'DRY RUN (use --write to update results.json)'}")


if __name__ == "__main__":
    main()
