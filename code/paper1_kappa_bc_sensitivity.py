#!/usr/bin/env python3
r"""One-at-a-time sensitivity of the SSCI to the black-carbon effectiveness
coefficient kappa_BC (ISSUES #6).

Motivation
----------
WMO 2022 (Ch. 7, Sec. 7.2.8.1) states that "ozone loss from rocket BC is
comparable to ozone loss from rocket chlorine emissions (per propellant
mass)" (Maloney et al. 2022; Ryan et al. 2022). The baseline atmospheric
module uses kappa_BC = 0.40 (kappa*tau_BC = 1.8 yr). Taken at its strongest,
the WMO statement implies a substantially larger BC effectiveness. This
script sweeps kappa_BC over the range spanned by two literature-anchored
interpretations and reports the effect on (a) the ENVISAT atmospheric
headline ratio and (b) the three-mission SSCI ranking.

Mechanism (why the test is informative)
---------------------------------------
The reference mission and both Falcon-9 missions (RedPill, Sentinel-6) burn
kerosene -> they emit BC. ENVISAT launches on Ariane 5 G+ with APCP solid
boosters -> its launch emits alumina + HCl, almost no BC. Because every
score is normalised to the (kerosene) reference, raising kappa_BC inflates
BOTH the kerosene missions AND the reference, so their normalised scores
move little, while ENVISAT's normalised atmospheric score (numerator nearly
fixed, denominator growing) DECREASES. The test therefore probes whether
the ENVISAT dominance and the ranking survive the strongest defensible
kappa_BC.

Anchors for the sweep (multiplier on kappa_BC = 0.40)
-----------------------------------------------------
  1.0x  : baseline (kappa*tau_BC = 1.8 yr)
  2.7x  : per-EMITTED-mass parity with the chlorine reservoir
          (kappa*tau_BC -> kappa*tau_HCl = 4.8 yr)
  10x   : intermediate
  22.4x : per-PROPELLANT-mass parity (strongest WMO reading):
          EI_BC(kerosene)*kappa*tau_BC = EI_HCl(APCP)*kappa*tau_HCl
          0.025*kappa*tau_BC = 0.21*4.8  ->  kappa*tau_BC = 40.3 yr

Terrestrial and orbital scores are independent of kappa_BC and are read,
unchanged, from outputs/<mission>/results.json. Only the atmospheric domain
is recomputed.

Usage:  python paper1_kappa_bc_sensitivity.py
Author: Federico Toson
"""
import json
from pathlib import Path

import numpy as np

import domain_atmospheric as atm
from mission_descriptor import Mission
from ssci import DomainScores, normalise, ssci_linear, ssci_risk, weights_equal

HERE = Path(__file__).parent
OUT = HERE / "outputs"
MISS = HERE / "missions"

MISSIONS = ["redpill_2p", "sentinel6", "envisat"]
YAML = {"redpill_2p": "redpill_2p.yaml",
        "sentinel6": "sentinel6.yaml",
        "envisat": "envisat.yaml"}
REFERENCE_YAML = "_reference_smallsat.yaml"

BASE_KAPPA_BC = atm.STRATOSPHERIC_KAPPA["BC"]   # 0.40
TAU_BC = atm.STRATOSPHERIC_TAU["BC"]            # 4.5 yr

# multiplier -> short rationale
SWEEP = [
    (1.0,  "baseline (kappa*tau_BC = 1.8 yr)"),
    (2.67, "per-emitted-mass parity with HCl (kappa*tau_BC = 4.8 yr)"),
    (10.0, "intermediate (kappa*tau_BC = 18 yr)"),
    (22.4, "per-propellant-mass parity, strongest WMO reading (kappa*tau_BC = 40 yr)"),
]


def set_kappa_bc(value: float) -> None:
    """Monkeypatch kappa_BC and rebuild the precomputed kappa*tau product."""
    atm.STRATOSPHERIC_KAPPA["BC"] = value
    atm.STRATOSPHERIC_KT["BC"] = value * TAU_BC


def atmospheric_raw(mission: Mission) -> float:
    return atm.compute_atmospheric_score(mission).raw_score


def load_fixed_norm():
    """I_T and I_O normalised scores (kappa_BC-independent) from results.json."""
    fixed = {}
    for m in MISSIONS:
        d = json.load(open(OUT / m / "results.json"))
        fixed[m] = {
            "iT": d["ssci"]["scores_norm"]["terrestrial"],
            "iO": d["ssci"]["scores_norm"]["orbital"],
            "iA_base": d["ssci"]["scores_norm"]["atmospheric"],
            "ssci_base": d["ssci"]["SSCI_linear_equal"],
        }
    return fixed


def main():
    fixed = load_fixed_norm()
    missions = {m: Mission.from_yaml(MISS / YAML[m]) for m in MISSIONS}
    reference = Mission.from_yaml(MISS / REFERENCE_YAML)
    w_eq = weights_equal()

    # sanity: reproduce the baseline atmospheric normalisation from results.json
    set_kappa_bc(BASE_KAPPA_BC)
    ref_atm0 = atmospheric_raw(reference)
    print(f"baseline kappa_BC = {BASE_KAPPA_BC}, tau_BC = {TAU_BC} yr, "
          f"reference atmospheric raw = {ref_atm0:.4g}")
    for m in MISSIONS:
        iA = atmospheric_raw(missions[m]) / ref_atm0
        print(f"  {m:11s} I_A recomputed = {iA:.4g}  "
              f"(results.json {fixed[m]['iA_base']:.4g})")

    print("\n" + "=" * 78)
    print("kappa_BC sweep — effect on normalised atmospheric score and SSCI")
    print("=" * 78)
    header = (f"{'mult':>6} {'k_BC':>6} {'kt_BC':>6} | "
              f"{'IA_red':>8} {'IA_sen':>8} {'IA_env':>9} | "
              f"{'SSCI_red':>9} {'SSCI_sen':>9} {'SSCI_env':>9} | rank")
    print(header)
    print("-" * len(header))

    rows = []
    for mult, _ in SWEEP:
        kbc = BASE_KAPPA_BC * mult
        set_kappa_bc(kbc)
        ref_atm = atmospheric_raw(reference)
        ssci_vals, iA_vals = {}, {}
        for m in MISSIONS:
            iA = atmospheric_raw(missions[m]) / ref_atm
            sn = np.array([fixed[m]["iT"], iA, fixed[m]["iO"]])
            iA_vals[m] = iA
            ssci_vals[m] = ssci_linear(sn, w_eq)
        order = sorted(MISSIONS, key=lambda m: ssci_vals[m])
        rank_ok = order == ["redpill_2p", "sentinel6", "envisat"]
        print(f"{mult:>6.1f} {kbc:>6.2f} {kbc*TAU_BC:>6.1f} | "
              f"{iA_vals['redpill_2p']:>8.2e} {iA_vals['sentinel6']:>8.3f} "
              f"{iA_vals['envisat']:>9.1f} | "
              f"{ssci_vals['redpill_2p']:>9.2e} {ssci_vals['sentinel6']:>9.3f} "
              f"{ssci_vals['envisat']:>9.2f} | {'OK' if rank_ok else 'BROKEN'}")
        rows.append({"mult": mult, "kappa_bc": kbc, "kt_bc": kbc * TAU_BC,
                     "iA": dict(iA_vals), "ssci": dict(ssci_vals),
                     "rank_ok": rank_ok})

    # restore baseline so importing this module leaves state clean
    set_kappa_bc(BASE_KAPPA_BC)

    env0 = rows[0]["iA"]["envisat"]
    envX = rows[-1]["iA"]["envisat"]
    print("\nSummary:")
    print(f"  ENVISAT normalised atmospheric score: {env0:.0f}x (baseline) "
          f"-> {envX:.0f}x (strongest kappa_BC), a {env0/envX:.1f}x reduction.")
    print(f"  Ranking RedPill < Sentinel-6 < ENVISAT preserved in all "
          f"{sum(r['rank_ok'] for r in rows)}/{len(rows)} cases: "
          f"{all(r['rank_ok'] for r in rows)}.")
    print(f"  ENVISAT remains the most impactful by a factor "
          f">{rows[-1]['ssci']['envisat']/rows[-1]['ssci']['sentinel6']:.0f} "
          f"over Sentinel-6 even at the strongest kappa_BC.")

    json.dump(rows, open(OUT / "kappa_bc_sensitivity.json", "w"), indent=1)
    print(f"\nWritten {OUT/'kappa_bc_sensitivity.json'}")


if __name__ == "__main__":
    main()
