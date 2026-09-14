#!/usr/bin/env python3
r"""IAC 2026 A6 - orbital burden of the population under three disposal rules.

Distinct from paper1_catalogue_scale.py, which samples a population once with a
FIXED per-archetype residual lifetime and reports the SSCI distribution. Here the
same sampled population (same seed, paired design) is re-scored under three
post-mission disposal rules, and the orbital domain alone is reported: no
composite indicator, no atmospheric or terrestrial domain.

Two congestion conventions are compared:
  CC_op   rho(h) * (50 km)^3 * T_op                 (as in Paper 1: operations only)
  CC_ext  rho(h) * (50 km)^3 * (T_op + T_res)       (occupancy continues after death)

Scenarios (residual lifetime after end of operations):
  uncontrolled  natural decay time at the operating altitude, no disposal manoeuvre
  rule25        25 yr cap  (IADC / ISO 24113 legacy rule)
  rule5          5 yr cap  (FCC 2022, ESA Zero Debris direction)

Natural decay is a two-point log-linear model in altitude, calibrated on two
published ESA DRAMA/OSCAR results rather than on assumed values:

  610 km, typical SSO   median ~25 yr (20 yr near solar minimum, 30 yr about
                        1-2 yr after solar maximum; the 25-year rule is met in
                        51% of disposal epochs)
                        Braun, Lemmens, Krag, Flohrer, Merz, Bastida Virgili,
                        Funke, "Probabilistic orbit lifetime assessment with
                        OSCAR", 6th ICATT, ESA/ESTEC, 2016.
  717 km, CryoSat-2     115 yr (Monte Carlo) to >210 yr (best-guess)
                        Braun et al., "Upgrade of the ESA DRAMA OSCAR tool",
                        Proc. 6th European Conference on Space Debris,
                        Darmstadt, 22-25 April 2013 (ESA SP-723).

The nominal curve is fitted through 25 yr at 610 km and 115 yr at 717 km, i.e.
the shorter of the two CryoSat-2 estimates, which is the conservative choice for
the burden claimed here. --decay-scale rescales the whole curve: 0.8 covers the
~25% combined standard deviation ESA reports, 1.8 the best-guess / Monte Carlo
ratio at 717 km. The headline numbers must be reported across that band.

It stands in for the absence of a disposal manoeuvre; it is not an orbit
propagation, and the paper must say so. The stronger version of this, if there
is time, is to run OSCAR directly on an altitude grid and fit to its output.

Usage:
  .venv/bin/python iac_a6_disposal_sweep.py [--n 300] [--no-matlab]
Author: Federico Toson.
"""
import csv, json, math, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

import paper1_catalogue_scale as cs

HERE = Path(__file__).parent
OUT = HERE / "outputs"
MATLAB_BIN = cs.MATLAB_BIN
RE = cs.RE
VOCC = cs.VOCC
CHI_EFF = cs.CHI_EFF

N = 300
if "--n" in sys.argv:
    N = int(sys.argv[sys.argv.index("--n") + 1])
USE_MATLAB = "--no-matlab" not in sys.argv
SEED = 20260615                      # stesso seme del catalogue scale: popolazione confrontabile

SCENARI = [("uncontrolled", None), ("rule25", 25.0), ("rule5", 5.0)]
BANDE = [(0, 500), (500, 800), (800, 1200), (1200, 2000)]

# decadimento naturale calibrato su due risultati OSCAR pubblicati (vedi testa
# del file): 25 anni a 610 km e 115 anni a 717 km. Tetto 1000 anni.
H1, T1 = 610.0, 25.0
H2, T2 = 717.0, 115.0
DECAY_B = (math.log(T2) - math.log(T1)) / (H2 - H1)
DECAY_A = math.log(T1) - DECAY_B * H1
DECAY_CAP = 1000.0

DECAY_SCALE = 1.0
if "--decay-scale" in sys.argv:
    DECAY_SCALE = float(sys.argv[sys.argv.index("--decay-scale") + 1])


def decadimento_naturale(h):
    return float(min(DECAY_CAP, DECAY_SCALE * math.exp(DECAY_A + DECAY_B * h)))


def campiona(alts, rng):
    probs = np.array([a[1] for a in cs.ARCHETYPES], dtype=float)
    probs /= probs.sum()
    idx = rng.choice(len(cs.ARCHETYPES), size=N, p=probs)
    h = rng.choice(alts, size=N)
    miss = []
    for i in range(N):
        nome, _, mass, top, tres, ex, tot, ptkg, launcher, demise = cs.ARCHETYPES[idx[i]]
        miss.append(dict(arch=nome, h=float(h[i]), mass=mass, top=top, tres_nat=tres,
                         ex=ex, tot=tot))
    return miss


def dgp_batch(miss, tres_per_mission):
    """Un solo lancio MATLAB per tutte le missioni di tutti gli scenari."""
    if not USE_MATLAB:
        return np.zeros(len(tres_per_mission))
    with tempfile.TemporaryDirectory() as td:
        ij, oc = Path(td) / "missions.json", Path(td) / "dgp.csv"
        payload = []
        for k, tres in enumerate(tres_per_mission):
            m = miss[k % len(miss)]
            payload.append({"altitude_km": m["h"], "inclination_deg": 90.0,
                            "eccentricity": 0.001, "op_lifetime_yr": m["top"],
                            "residual_lifetime_yr": float(tres),
                            "exposed_surface_m2": m["ex"], "total_surface_m2": m["tot"]})
        json.dump(payload, open(ij, "w"))
        cmd = [MATLAB_BIN, "-batch", f"cd('{HERE}'); paper1_catalogue_scale('{ij}','{oc}')"]
        log = OUT / "iac_a6_matlab.log"
        OUT.mkdir(exist_ok=True)
        print(f"batch MATLAB su {len(payload)} righe (un lancio solo), log in {log}", flush=True)
        # niente capture_output: un servizio MATLAB che eredita la pipe la tiene
        # aperta e subprocess resta fermo su poll anche a calcolo finito.
        with open(log, "w") as lf:
            r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=lf, stderr=lf,
                               timeout=5400)
        if r.returncode != 0 or not oc.exists():
            print("MATLAB fallito, ultime righe del log:")
            print("".join(open(log).readlines()[-15:]))
            sys.exit(1)
        out = np.zeros(len(payload))
        for row in csv.DictReader(open(oc)):
            out[int(row["index"]) - 1] = float(row["DGP"])
        return out


def main():
    rng = np.random.default_rng(SEED)
    alts = cs.load_real_altitudes()
    print(f"altitudini LEO attive reali: {len(alts)} (mediana {np.median(alts):.0f} km)")
    miss = campiona(alts, rng)

    # tempo residuo per scenario, missione per missione
    tres = {}
    for nome, cap in SCENARI:
        if cap is None:
            tres[nome] = np.array([decadimento_naturale(m["h"]) for m in miss], dtype=float)
        else:
            tres[nome] = np.array([min(decadimento_naturale(m["h"]), cap) for m in miss],
                                  dtype=float)
    for nome, _ in SCENARI:
        v = tres[nome]
        print(f"  T_res {nome:<14} mediana {np.median(v):8.1f} anni   "
              f"range [{v.min():.1f}, {v.max():.1f}]")

    # un solo batch: scenari concatenati
    ordine = [n for n, _ in SCENARI]
    concat = np.concatenate([tres[n] for n in ordine])
    dgp_all = dgp_batch(miss, concat)
    dgp = {n: dgp_all[i * N:(i + 1) * N] for i, n in enumerate(ordine)}

    # densita' e termini indipendenti dallo scenario
    rho = np.array([cs.density_at(m["h"], alts) for m in miss])
    top = np.array([m["top"] for m in miss], dtype=float)
    mc = np.array([CHI_EFF * m["mass"] * cs.eta_orbit(m["h"]) for m in miss])
    h = np.array([m["h"] for m in miss])

    righe = []
    for nome, _ in SCENARI:
        cc_op = rho * VOCC * top
        cc_ext = rho * VOCC * (top + tres[nome])
        righe.append(dict(scenario=nome, dgp=dgp[nome], cc_op=cc_op, cc_ext=cc_ext, mc=mc,
                          tres=tres[nome]))

    base = next(r for r in righe if r["scenario"] == "rule25")

    print(f"\n=== N={N}, disegno appaiato (stessa popolazione nei tre scenari) ===")
    for r in righe:
        d = r["dgp"]
        print(f"\n--- {r['scenario']}  (T_res mediano {np.median(r['tres']):.0f} anni) ---")
        print(f"  DGP        mediana {np.median(d):.4g}   media {d.mean():.4g}")
        print(f"  CC_op      mediana {np.median(r['cc_op']):.4g}   (non risente dello scenario)")
        print(f"  CC_ext     mediana {np.median(r['cc_ext']):.4g}")
        if r is not base:
            for k, lab in (("dgp", "DGP"), ("cc_ext", "CC_ext")):
                delta = 100 * (np.median(r[k]) - np.median(base[k])) / np.median(base[k])
                print(f"  delta {lab} vs regola 25 anni: {delta:+.1f}%")

    print("\n=== per banda di quota, DGP mediano ===")
    print(f"  {'banda km':<14}" + "".join(f"{n:>16}" for n, _ in SCENARI) + f"{'n':>6}")
    for lo, hi in BANDE:
        sel = (h >= lo) & (h < hi)
        if sel.sum() == 0:
            continue
        cel = "".join(f"{np.median(r['dgp'][sel]):>16.4g}" for r in righe)
        print(f"  {f'{lo}-{hi}':<14}{cel}{sel.sum():>6}")

    print("\n=== quanto pesa estendere la congestione oltre le operazioni ===")
    for r in righe:
        rap = np.median(r["cc_ext"] / r["cc_op"])
        print(f"  {r['scenario']:<14} CC_ext / CC_op mediano: {rap:.2f}x")

    # L'onere ambientale di una popolazione e' la somma, non la mediana: la
    # mediana e' dominata da Starlink sotto i 500 km, dove la regola non morde.
    print("\n=== aggregato di popolazione (somma DGP) e concentrazione ===")
    base_tot = base["dgp"].sum()
    alta = h >= 800
    for r in righe:
        d = r["dgp"]
        tot = d.sum()
        top10 = np.sort(d)[::-1][:max(1, N // 10)].sum()
        print(f"  {r['scenario']:<14} somma {tot:10.4g}  "
              f"({100 * (tot - base_tot) / base_tot:+6.1f}% vs regola 25)   "
              f"decile alto {100 * top10 / tot:4.1f}% del totale   "
              f"quota >=800 km {100 * d[alta].sum() / tot if alta.any() else 0:4.1f}%")
    print(f"  missioni sopra 800 km: {int(alta.sum())} su {N} "
          f"({100 * alta.mean():.1f}% della popolazione)")

    # dove la regola dei 25 anni e' davvero vincolante
    nat = tres["uncontrolled"]
    morde = nat > 25.0
    print(f"\n  la regola dei 25 anni e' vincolante su {int(morde.sum())}/{N} missioni "
          f"({100 * morde.mean():.1f}%): sotto i ~600 km il decadimento naturale "
          f"e' gia' piu' rapido del limite.")

    OUT.mkdir(exist_ok=True)
    dump = {r["scenario"]: {k: np.asarray(v).tolist() for k, v in r.items() if k != "scenario"}
            for r in righe}
    dump["_meta"] = {"N": N, "seed": SEED, "altitudini": h.tolist(),
                     "archetipi": [m["arch"] for m in miss], "matlab": USE_MATLAB}
    json.dump(dump, open(OUT / "iac_a6_disposal_sweep.json", "w"))
    print(f"\nscritto {OUT / 'iac_a6_disposal_sweep.json'}")


if __name__ == "__main__":
    main()
