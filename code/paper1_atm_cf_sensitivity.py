#!/usr/bin/env python3
r"""Sensitivity of the ENVISAT atmospheric headline to the TWO species that
actually carry it: alumina (Al2O3) and chlorine (HCl).

Review finding (iteration 1): the 380x ENVISAT atmospheric ratio is 94%
alumina (65%) + HCl (29%); black carbon is 0.01%. The kappa_BC sweep in
paper1_kappa_bc_sensitivity.py therefore stress-tests a species irrelevant
to ENVISAT. This script sweeps the kappa*tau of the two dominant species
over defensible ranges and reports the ENVISAT normalised atmospheric score
and composite SSCI, so the headline is reported as a band, not a point.

Baselines (domain_atmospheric.py):
  alumina  kappa*tau = 0.50 * 15.0 = 7.5 yr   (tau is "up to 30 yr settling"
           in Ferreira 2024; kappa "less well bounded", Danilin)
  HCl      kappa*tau = 1.20 *  4.0 = 4.8 yr   (Cl reservoir residence)

Defensible low ends: alumina kappa*tau 2.5 yr (shorter effective settling,
no catalytic-persistence add-on); HCl kappa*tau 2.4 yr (faster reservoir
turnover). Reference mission is kerosene (no Al2O3/HCl), so these knobs move
ENVISAT's numerator only -> a clean one-/two-at-a-time test.

Terrestrial and orbital scores are kappa-independent and read from
results.json. Author: Federico Toson.
"""
import json
from pathlib import Path
import numpy as np

import domain_atmospheric as atm
from mission_descriptor import Mission
from ssci import normalise, ssci_linear, ssci_risk, weights_equal

HERE = Path(__file__).parent
OUT = HERE / "outputs"
MISS = HERE / "missions"
MISSIONS = ["redpill_2p", "sentinel6", "envisat"]
YAML = {"redpill_2p": "redpill_2p.yaml", "sentinel6": "sentinel6.yaml",
        "envisat": "envisat.yaml"}

BASE = {"Al2O3": atm.STRATOSPHERIC_KT["Al2O3"], "HCl": atm.STRATOSPHERIC_KT["HCl"]}


def set_kt(al, hcl):
    atm.STRATOSPHERIC_KT["Al2O3"] = al
    atm.STRATOSPHERIC_KT["HCl"] = hcl


def atm_raw(mission):
    return atm.compute_atmospheric_score(mission).raw_score


def main():
    fixed = {m: json.load(open(OUT / m / "results.json")) for m in MISSIONS}
    miss = {m: Mission.from_yaml(MISS / YAML[m]) for m in MISSIONS}
    ref = Mission.from_yaml(MISS / "_reference_smallsat.yaml")
    w = weights_equal()

    # baseline validation
    set_kt(BASE["Al2O3"], BASE["HCl"])
    ref_atm0 = atm_raw(ref)
    iA_env0 = atm_raw(miss["envisat"]) / ref_atm0
    print(f"baseline: alumina kt={BASE['Al2O3']:.1f} yr, HCl kt={BASE['HCl']:.1f} yr")
    print(f"  ENVISAT I_A = {iA_env0:.1f}  (results.json "
          f"{fixed['envisat']['ssci']['scores_norm']['atmospheric']:.1f})\n")

    # species decomposition of ENVISAT atmospheric (why these two matter)
    by = atm.compute_atmospheric_score(miss["envisat"]).by_species
    tot = sum(by.values())
    print("ENVISAT atmospheric by species (share of raw):")
    for s, v in sorted(by.items(), key=lambda kv: -kv[1]):
        print(f"  {s:6s} {100*v/tot:5.2f}%")
    print()

    grid_al = [2.5, 5.0, 7.5]     # alumina kappa*tau (yr)
    grid_hcl = [2.4, 3.6, 4.8]    # HCl kappa*tau (yr)
    print(f"{'al_kt':>6} {'hcl_kt':>6} | {'IA_env':>8} {'SSCI_env':>9} | rank")
    print("-" * 46)
    rows = []
    iA_vals = []
    for al in grid_al:
        for hcl in grid_hcl:
            set_kt(al, hcl)
            ref_atm = atm_raw(ref)
            ssci_v, iA_v = {}, {}
            for m in MISSIONS:
                iA = atm_raw(miss[m]) / ref_atm
                sn = np.array([fixed[m]["ssci"]["scores_norm"]["terrestrial"],
                               iA, fixed[m]["ssci"]["scores_norm"]["orbital"]])
                iA_v[m] = iA
                ssci_v[m] = ssci_linear(sn, w)
            order = sorted(MISSIONS, key=lambda k: ssci_v[k])
            ok = order == ["redpill_2p", "sentinel6", "envisat"]
            iA_vals.append(iA_v["envisat"])
            print(f"{al:>6.1f} {hcl:>6.1f} | {iA_v['envisat']:>8.1f} "
                  f"{ssci_v['envisat']:>9.1f} | {'OK' if ok else 'BROKEN'}")
            rows.append({"al_kt": al, "hcl_kt": hcl,
                         "iA_env": iA_v["envisat"], "ssci_env": ssci_v["envisat"],
                         "rank_ok": ok})
    set_kt(BASE["Al2O3"], BASE["HCl"])  # restore

    lo, hi = min(iA_vals), max(iA_vals)
    print(f"\nENVISAT normalised atmospheric band: {lo:.0f}x - {hi:.0f}x "
          f"(baseline {iA_env0:.0f}x)")
    print(f"ranking preserved in all {sum(r['rank_ok'] for r in rows)}/"
          f"{len(rows)} cells: {all(r['rank_ok'] for r in rows)}")
    print(f"ENVISAT remains atmospherically dominant (> terrestrial 22x and "
          f"orbital 31x) in every cell: {all(r['iA_env']>31 for r in rows)}")
    json.dump(rows, open(OUT / "atm_cf_sensitivity.json", "w"), indent=1)


if __name__ == "__main__":
    main()
