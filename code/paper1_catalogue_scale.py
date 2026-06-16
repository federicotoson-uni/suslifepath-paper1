#!/usr/bin/env python3
r"""Catalogue-scale application of the SSCI (ISSUES R2).

Addresses the hard-review objection that n=3 does not validate the framework
and that CC/DGP look inert. Draws N missions whose ALTITUDES are sampled from
the real active-LEO Celestrak distribution (the public catalogue carries no
mass, so mass/materials/launcher are assigned by mission-class archetype),
computes the full SSCI for each, and reports the distribution, the prevalence
of each orbital sub-category, and the single-indicator gap statistic.

Domains:
  - CC : density(altitude) * (50 km)^3 * T_op  [pure Python; VALIDATED to
         match congestion_contribution.m on the 3 case studies]
  - DGP: ECOB-proxy R_col from the MATLAB batch paper1_catalogue_scale.m
         (one MATLAB launch for all N; consistent with the case studies)
  - MC : sum_i mass_i * chi_i * eta(altitude)  [archetype material mix]
  - atmospheric: launcher-class propellant chemistry (domain_atmospheric
         emission factors), normalised to the cached reference launch
  - terrestrial: archetype EF 3.1 intensity (Pt/kg) * mass, from the four
         re-grounded product systems, normalised to the cached reference

Reference raw scores (cached, post water-fix) are read from
outputs/redpill_2p/results.json. Usage:
  .venv/bin/python paper1_catalogue_scale.py [--n 300] [--no-matlab]
Author: Federico Toson.
"""
import csv, json, math, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

import domain_atmospheric as atm

HERE = Path(__file__).parent
OUT = HERE / "outputs"
CATALOGUE = HERE.parent.parent / "Paper0_SimplifiedAlgorithm" / "data" / "celestrak_active.csv"
MATLAB_BIN = "/Applications/MATLAB_R2026a.app/bin/matlab"

N = 300
if "--n" in sys.argv:
    N = int(sys.argv[sys.argv.index("--n") + 1])
USE_MATLAB = "--no-matlab" not in sys.argv
RNG = np.random.default_rng(20260615)

MU, RE = 398600.4418, 6378.137
VOCC = 50.0 ** 3                       # (50 km)^3 keep-out, matches MATLAB
CHI_EFF = 0.39                         # effective criticality per kg (typical bus mix)

# reference scores for normalisation (post water-fix + orbital sub-cat renorm)
_rj = json.load(open(OUT / "redpill_2p" / "results.json"))
_ref = _rj["reference_raw_scores"]
REF_TERR, REF_ATM = _ref["terrestrial"], _ref["atmospheric"]
# orbital normalised PER SUB-CATEGORY (R8 fix): DGP_ref=1, CC_ref, MC_ref
_os = _rj["reference_subscores_orbital"]
DGP_REF, CC_REF, MC_REF = _os["DGP"], _os["CC"], _os["MC"]

# mission-class archetypes: (name, prob, mass_kg, T_op, T_res, ex_surf, tot_surf,
#                            Pt_per_kg, launcher, demise_frac)
ARCHETYPES = [
    ("cubesat",  0.50,    6.0, 3,  5,  0.04, 0.12, 0.0051, "kerosene", 1.00),
    ("smallsat", 0.35,  200.0, 5, 25,  1.5,  4.0,  0.0040, "kerosene", 0.80),
    ("medium",   0.12, 1000.0, 6, 25,  6.0,  18.0, 0.0050, "kerosene", 0.75),
    ("large",    0.03, 5000.0, 10, 80, 25.0, 60.0, 0.0049, "mixed",    0.65),
]
# per-kg-payload propellant intensities (kg propellant / kg payload), from the
# case-study launcher shares: kerosene-LOX (Falcon 9) and APCP-stack (Ariane 5)
KEROSENE_STACK = {"kerosene": 8.8, "LOX": 35.0}
SRM_STACK = {"APCP": 26.3, "hydrogen": 1.39, "LOX": 7.2, "MMH": 0.33, "N2O4": 0.22}


def load_real_altitudes():
    alts = []
    with open(CATALOGUE) as f:
        for row in csv.DictReader(f):
            try:
                n = float(row["MEAN_MOTION"]) * 2 * math.pi / 86400.0
                e = float(row["ECCENTRICITY"])
                a = (MU / n ** 2) ** (1 / 3.0)
                hp = a * (1 - e) - RE
                if 0 < hp < 2000:
                    alts.append(hp)
            except (ValueError, KeyError, ZeroDivisionError):
                pass
    return np.array(alts)


def density_at(h0, alts, dh=25.0):
    n_shell = int(np.sum(np.abs(alts - h0) <= dh))
    r = RE + h0
    v_shell = 4 * math.pi * r ** 2 * (2 * dh)
    return n_shell / v_shell


def eta_orbit(h):
    if h < 600:
        return 0.3
    if h >= 2000:
        return 1.0
    return 0.3 + 0.7 * (h - 600) / 1400.0


def atm_raw_for(mass, launcher, demise):
    stack = KEROSENE_STACK if launcher == "kerosene" else SRM_STACK
    launch = 0.0
    for prop, intensity in stack.items():
        pmass = intensity * mass
        ef = atm.EMISSION_FACTORS_LAUNCH.get(prop, {})
        for sp, factor in ef.items():
            launch += atm.STRATOSPHERIC_KT.get(sp, 0.0) * factor * pmass
    # re-entry: demise mass split evenly across the three families (as in the module)
    reentry = 0.0
    dm = demise * mass / 3.0
    for fam, ef in atm.EMISSION_FACTORS_REENTRY.items():
        for sp, factor in ef.items():
            reentry += atm.STRATOSPHERIC_KT.get(sp, 0.0) * factor * dm
    return launch + reentry


def main():
    alts = load_real_altitudes()
    print(f"real active-LEO altitudes: {len(alts)} (median {np.median(alts):.0f} km)")

    # sample N missions
    probs = np.array([a[1] for a in ARCHETYPES])
    probs /= probs.sum()
    idx = RNG.choice(len(ARCHETYPES), size=N, p=probs)
    h = RNG.choice(alts, size=N)            # real altitudes
    missions = []
    for i in range(N):
        _, _, mass, top, tres, ex, tot, ptkg, launcher, demise = ARCHETYPES[idx[i]]
        lr = launcher
        if launcher == "mixed":
            lr = "srm" if RNG.random() < 0.30 else "kerosene"
        missions.append(dict(arch=ARCHETYPES[idx[i]][0], h=float(h[i]), mass=mass,
                             top=top, tres=tres, ex=ex, tot=tot, ptkg=ptkg,
                             launcher=lr, demise=demise))

    # DGP via MATLAB batch (one launch)
    dgp = np.zeros(N)
    if USE_MATLAB:
        with tempfile.TemporaryDirectory() as td:
            ij = Path(td) / "missions.json"
            oc = Path(td) / "dgp.csv"
            json.dump([{"altitude_km": m["h"], "inclination_deg": 90.0,
                        "eccentricity": 0.001, "op_lifetime_yr": m["top"],
                        "residual_lifetime_yr": m["tres"],
                        "exposed_surface_m2": m["ex"], "total_surface_m2": m["tot"]}
                       for m in missions], open(ij, "w"))
            cmd = [MATLAB_BIN, "-batch",
                   f"cd('{HERE}'); paper1_catalogue_scale('{ij}','{oc}')"]
            print("running MATLAB DGP batch (one launch)...")
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if r.returncode != 0 or not oc.exists():
                print("MATLAB batch failed:\n", r.stdout[-500:], r.stderr[-500:])
                sys.exit(1)
            for row in csv.DictReader(open(oc)):
                dgp[int(row["index"]) - 1] = float(row["DGP"])
            print(f"DGP batch done: median {np.median(dgp):.3g}")

    # full SSCI per mission
    rows = []
    for i, m in enumerate(missions):
        rho = density_at(m["h"], alts)
        cc = rho * VOCC * m["top"]
        mc = CHI_EFF * m["mass"] * eta_orbit(m["h"])
        # per-sub-category normalisation (R8): each sub-score / reference, then mean
        iDGP, iCC, iMC = dgp[i] / DGP_REF, cc / CC_REF, mc / MC_REF
        iO = (iDGP + iCC + iMC) / 3.0
        iA = atm_raw_for(m["mass"], m["launcher"], m["demise"]) / REF_ATM
        iT = (m["ptkg"] * m["mass"]) / REF_TERR
        sn = np.array([iT, iA, iO])
        ssci_lin = float(sn.mean())
        ssci_risk = float(np.prod(sn) ** (1 / 3.0))
        gap = (iT - ssci_lin) / ssci_lin * 100
        dom = max([("DGP", iDGP), ("CC", iCC), ("MC", iMC)], key=lambda x: x[1])[0]
        rows.append(dict(arch=m["arch"], h=m["h"], iT=iT, iA=iA, iO=iO,
                         ssci=ssci_lin, ssci_risk=ssci_risk, gap=gap,
                         orb_dom=dom, dgp=dgp[i], cc=cc, mc=mc))

    ssci = np.array([r["ssci"] for r in rows])
    gaps = np.array([r["gap"] for r in rows])
    doms = [r["orb_dom"] for r in rows]
    print(f"\n=== SSCI over N={N} (real-altitude x archetype) ===")
    print(f"  SSCI  median {np.median(ssci):.3g}  IQR [{np.percentile(ssci,25):.3g}, "
          f"{np.percentile(ssci,75):.3g}]  range [{ssci.min():.2g}, {ssci.max():.2g}]"
          f"  ({math.log10(ssci.max()/ssci.min()):.1f} decades)")
    print(f"  orbital sub-category that DOMINATES (per mission):")
    for k in ("DGP", "CC", "MC"):
        print(f"     {k}: {100*doms.count(k)/N:.0f}% of missions")
    print(f"  PEFCR-style (terrestrial-only) gap vs SSCI:")
    print(f"     overestimates (gap>0): {100*np.mean(gaps>0):.0f}% of missions "
          f"(median +{np.median(gaps[gaps>0]):.0f}%)" if np.any(gaps>0) else "     none over")
    print(f"     underestimates (gap<0): {100*np.mean(gaps<0):.0f}% of missions "
          f"(median {np.median(gaps[gaps<0]):.0f}%)" if np.any(gaps<0) else "     none under")
    print(f"     |gap|>50%: {100*np.mean(np.abs(gaps)>50):.0f}% of missions")
    json.dump([{k: (v if not isinstance(v, np.floating) else float(v))
                for k, v in r.items()} for r in rows],
              open(OUT / "catalogue_scale.json", "w"), indent=1)
    print(f"\nwritten {OUT/'catalogue_scale.json'}")


if __name__ == "__main__":
    main()
