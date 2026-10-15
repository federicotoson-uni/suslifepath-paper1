"""Sensitivities added in the JCLEPRO revision (October 2026), pure Python.

Reads the outputs of the pilot (outputs/<case>/results.json, outputs/catalogue_scale.json)
and the Celestrak snapshot used by the orbital module, and computes:

  A. CC boundary: congestion counted to re-entry (T_op + T_res) against the
     operations-only convention (T_op), for the three cases and the N=300 sample
     (archetype residual lifetimes, and the natural-lifetime curve of the IAC 2026
     companion study as an uncontrolled upper variant).
  B. Same-constellation pairs: share of the catalogued objects in a 25-km half-width
     shell that belong to the dominant constellation at that altitude, i.e. the
     reduction of rho_op (and of CC) if a constellation satellite screened only
     against other operators.
  C. Terrestrial uncertainty: the normalised terrestrial score scaled by 0.1 and 10,
     propagated to SSCI (linear, equal weights; geometric mean) for the three cases
     and to the catalogue-scale statistics (share of missions whose terrestrial
     score lies below the composite, median difference).
  D. Without the atmospheric domain: composite from terrestrial and orbital only,
     ranking of the three cases and Spearman correlation over the sample.
  E. Accounting horizon of the debris term: DGP_H = DGP * (T_op + min(T_res, H)) /
     (T_op + min(T_res, T_cap)) for H = 100, 200, 1000 yr (T_cap = 200 yr in the
     pilot proxy), three cases.
  F. Launch allocation: share of the launch capacity (the pilot rule) against full
     attribution of a dedicated launch to its payload.
  G. Propellant production, climate only: cradle-to-gate factors per propellant,
     low / mid / high, converted to EF 3.1 points and normalised to the reference.
  H. A trade-off across domains: Sentinel-6 with and without disposal.

Writes outputs/revision_sensitivities.json and prints a summary.
"""
import csv, json, math
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
from paper1_catalogue_scale import CATALOGUE  # Paper 0 snapshot, same lookup

CASES = {  # T_op, T_res [yr] from missions/*.yaml; altitude [km]
    "redpill_2p": dict(top=2.0, tres=8.0, h=550.0),
    "sentinel6":  dict(top=5.5, tres=25.0, h=1336.0),
    "envisat":    dict(top=10.0, tres=200.0, h=770.0),
}
ARCH = {  # T_op, T_res as in paper1_catalogue_scale.py
    "cubesat": (3.0, 5.0), "smallsat": (5.0, 25.0), "medium": (6.0, 25.0), "large": (10.0, 80.0),
}
# natural-lifetime screening curve of the IAC 2026 study: 25 yr at 610 km, 115 yr at 717 km, cap 1000 yr
_B = (math.log(115.0) - math.log(25.0)) / (717.0 - 610.0)
_A = math.log(25.0) - _B * 610.0
T_CAP_PROXY = 200.0


def t_nat(h):
    return min(1000.0, math.exp(_A + _B * h))


def spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def main():
    res = {}
    cat = json.load(open(OUT / "catalogue_scale.json"))
    # ---------------- A. CC boundary ----------------
    a = {}
    for c, p in CASES.items():
        a[c] = dict(ratio_ext_op=(p["top"] + p["tres"]) / p["top"],
                    share_after_ops=p["tres"] / (p["top"] + p["tres"]))
    cc_op = np.array([m["cc"] for m in cat])
    top = np.array([ARCH[m["arch"]][0] for m in cat]); tres_arch = np.array([ARCH[m["arch"]][1] for m in cat])
    tres_nat = np.array([t_nat(m["h"]) for m in cat])
    for lab, tres in (("archetype", tres_arch), ("natural_uncontrolled", tres_nat)):
        cc_ext = cc_op * (top + tres) / top
        a[f"sample_{lab}"] = dict(
            median_ratio=float(np.median(cc_ext / cc_op)),
            share_after_ops_total=float(1 - cc_op.sum() / cc_ext.sum()),
            median_share_after_ops=float(np.median(tres / (top + tres))),
            spearman_rank_ext_vs_op=spearman(cc_ext, cc_op))
    res["A_cc_boundary"] = a
    # ---------------- B. same-constellation share ----------------
    mu, RE = 398600.4418, 6378.137
    alts, names = [], []
    for row in csv.DictReader(open(CATALOGUE)):
        n = float(row["MEAN_MOTION"]) * 2 * math.pi / 86400.0
        alts.append((mu / n ** 2) ** (1 / 3) - RE); names.append(row["OBJECT_NAME"].upper())
    alts = np.array(alts)
    b = {}
    for h0, pref in ((475.0, "STARLINK"), (525.0, "STARLINK"), (550.0, "STARLINK"), (1200.0, "ONEWEB")):
        sel = np.abs(alts - h0) <= 25.0
        own = sum(1 for nm, s in zip(names, sel) if s and nm.startswith(pref))
        b[f"{int(h0)}km_{pref}"] = dict(objects_in_shell=int(sel.sum()), own=own, own_share=own / max(1, int(sel.sum())))
    res["B_same_constellation"] = b
    # ---------------- C. terrestrial uncertainty ----------------
    cc = {}
    scores = {}
    for c in CASES:
        r = json.load(open(OUT / c / "results.json"))["ssci"]["scores_norm"]
        scores[c] = (r["terrestrial"], r["atmospheric"], r["orbital"])
    for f in (0.1, 1.0, 10.0):
        row = {}
        for c, (t, at, o) in scores.items():
            tt = t * f
            row[c] = dict(lin=(tt + at + o) / 3, geo=(tt * at * o) ** (1 / 3))
        order_lin = sorted(row, key=lambda k: row[k]["lin"]); order_geo = sorted(row, key=lambda k: row[k]["geo"])
        iT = np.array([m["iT"] for m in cat]) * f; iA = np.array([m["iA"] for m in cat]); iO = np.array([m["iO"] for m in cat])
        ssci = (iT + iA + iO) / 3; diff = (iT - ssci) / ssci
        row["catalogue"] = dict(share_terrestrial_below=float(np.mean(diff < 0)), median_difference=float(np.median(diff)),
                                median_ssci=float(np.median(ssci)))
        row["ranking_lin"] = order_lin; row["ranking_geo"] = order_geo
        cc[f"terrestrial_x{f:g}"] = row
    res["C_terrestrial_uncertainty"] = cc
    # ---------------- D. without the atmospheric domain ----------------
    d = {}
    for c, (t, at, o) in scores.items():
        d[c] = dict(full_lin=(t + at + o) / 3, TO_lin=(t + o) / 2)
    d["ranking_full"] = sorted(CASES, key=lambda k: d[k]["full_lin"]); d["ranking_TO"] = sorted(CASES, key=lambda k: d[k]["TO_lin"])
    iT = np.array([m["iT"] for m in cat]); iA = np.array([m["iA"] for m in cat]); iO = np.array([m["iO"] for m in cat])
    d["sample_spearman_full_vs_TO"] = spearman((iT + iA + iO) / 3, (iT + iO) / 2)
    d["sample_spearman_full_vs_O"] = spearman((iT + iA + iO) / 3, iO)
    d["sample_median_share_atmospheric"] = float(np.median(iA / (iT + iA + iO)))
    res["D_without_atmospheric"] = d
    # ---------------- E. accounting horizon of DGP ----------------
    # The pilot DGP is R_col (paper0_ecob_proxy_single.m, line 'DGP = R_col'): the
    # snapshot collision rate integrated over the mission's own presence T_op + T_res,
    # without cap, with a severity (A_tot / A_ref)^0.5. An accounting horizon H caps
    # the residual lifetime. The mass-weighted proxy with a fixed 200-yr horizon
    # (ecob_proxy.m, severity (M / M_ref)^0.75) is the cross-check, not the DGP.
    MASS = {"redpill_2p": 0.435, "sentinel6": 1192.0, "envisat": 8211.0}
    ATOT = {"redpill_2p": 0.025, "sentinel6": 25.0, "envisat": 250.0}
    REF = dict(top=7.0, tres=25.0, mass=500.0, atot=15.0)
    e = {}
    for c, p in CASES.items():
        e[c] = {f"horizon_H{int(H)}": (p["top"] + min(p["tres"], H)) / (p["top"] + p["tres"]) for H in (100.0, 200.0, 1000.0)}
        rcol_rel = ((p["top"] + p["tres"]) / (REF["top"] + REF["tres"])) * (ATOT[c] / REF["atot"]) ** 0.5
        reco_rel = (MASS[c] / REF["mass"]) ** 0.75
        e[c]["mass_fixed200_over_presence_area"] = reco_rel / rcol_rel
    res["E_dgp_horizon_factor"] = e
    # ---------------- F. launch allocation rule ----------------
    # The pilot charges each payload with its share of the launch capacity
    # (payload mass over payload capacity to LEO), also for dedicated launches.
    # Alternative: full attribution of a dedicated launch to its payload.
    import yaml, domain_atmospheric as atm
    def atm_raw(d, launch_factor):
        raw = 0.0
        for prop, kg in d["launch"]["propellant_share_kg"].items():
            for s, fac in atm.EMISSION_FACTORS_LAUNCH.get(prop, {}).items():
                raw += atm.STRATOSPHERIC_KT.get(s, 0.0) * fac * kg * launch_factor
        dem = d["mass_budget"]["dry_mass_kg"] * d["reentry"]["expected_demise_fraction"]
        per_fam = dem / max(1, len(atm.EMISSION_FACTORS_REENTRY))
        for fam, ef in atm.EMISSION_FACTORS_REENTRY.items():
            for s, fac in ef.items():
                raw += atm.STRATOSPHERIC_KT.get(s, 0.0) * fac * per_fam
        return raw
    FULL = {"redpill_2p": 1.0, "sentinel6": 1 / 0.075, "envisat": 1 / 0.456, "_reference_smallsat": 1 / 0.031}
    descr = {f: yaml.safe_load(open(HERE / "missions" / f"{f}.yaml")) for f in FULL}
    base = {f: atm_raw(d, 1.0) for f, d in descr.items()}
    full = {f: atm_raw(d, FULL[f]) for f, d in descr.items()}
    f_out = {}
    for c in CASES:
        iA_base = base[c] / base["_reference_smallsat"]; iA_full = full[c] / full["_reference_smallsat"]
        t, a, o = scores[c]
        f_out[c] = dict(iA_capacity_share=iA_base, iA_full_attribution=iA_full,
                        ssci_lin_capacity_share=(t + a + o) / 3, ssci_lin_full_attribution=(t + iA_full + o) / 3,
                        launch_factor=FULL[c])
    f_out["reference_launch_factor"] = FULL["_reference_smallsat"]
    res["F_launch_allocation"] = f_out
    # ---------------- G. propellant production, climate-only estimate ----------------
    # Cradle-to-gate climate factors (kg CO2 eq per kg propellant), low / mid / high,
    # from revisione_JoCP/fattori_propellente.md: kerosene from Jing et al. 2022
    # (well-to-tank jet fuel), LOX from Dominguez Calabuig et al. 2024 (published 1.2)
    # with an energy-based lower bound, LH2 from Dominguez Calabuig 2024 and Elgowainy
    # et al. 2024, APCP, MMH and N2O4 as order-of-magnitude estimates from relative
    # ratios (Blondel-Canepari et al. 2025). The added climate burden is converted to
    # EF 3.1 single-score points with the pipeline's own kg CO2 eq per weighted climate
    # point (outputs/terrestrial_weighted.csv), then normalised to the reference.
    CF = {"kerosene": (0.31, 0.64, 0.90), "LOX": (0.2, 1.2, 1.2), "hydrogen": (10.0, 12.0, 14.0),
          "APCP": (1.5, 2.2, 3.0), "MMH": (20.0, 30.0, 40.0), "N2O4": (11.0, 14.0, 17.0)}
    import csv as _csv
    rows = list(_csv.reader(open(OUT / "terrestrial_weighted.csv")))
    header = rows[0]
    clim_pt = {}
    for row in rows[1:]:
        if row[0].strip().lower() == "climate change":
            clim_pt = {header[i]: float(row[i]) for i in range(1, len(header))}
    def key_for(c):
        for k in clim_pt:
            if c.replace("_", "") in k.replace("_", "") or k.replace("_", "") in c.replace("_", ""):
                return k
        return None
    g = {}
    kg_per_pt = {}
    singles = {}
    for c in list(CASES) + ["_reference_smallsat"]:
        rj = json.load(open(OUT / (c if c in CASES else "sentinel6") / "results.json"))
        if c in CASES:
            terr = rj["raw_scores"]["terrestrial"]
            singles[c] = terr["raw_score"]
            ck = key_for(c)
            kg_per_pt[c] = terr["by_impact_category"]["Climate change"] / clim_pt[ck] if ck and clim_pt.get(ck) else None
        else:
            singles[c] = rj["reference_raw_scores"]["terrestrial"]
    kpp = float(np.median([v for v in kg_per_pt.values() if v]))
    for c in list(CASES) + ["_reference_smallsat"]:
        d = descr[c]
        add = {lvl: sum(kg * CF[p][i] for p, kg in d["launch"]["propellant_share_kg"].items() if p in CF)
               for i, lvl in enumerate(("low", "mid", "high"))}
        g[c] = dict(added_climate_kg=add, added_points={k: v / kpp for k, v in add.items()},
                    single_score=singles[c], relative_increase={k: v / kpp / singles[c] for k, v in add.items()})
    g["kg_co2e_per_climate_point"] = kpp
    for c in CASES:
        t, a, o = scores[c]
        g[c]["normalised_terrestrial_ratio"] = {}
        g[c]["ssci_lin_new"] = {}
        for lvl in ("low", "mid", "high"):
            new_t = (singles[c] + g[c]["added_points"][lvl]) / (singles["_reference_smallsat"] + g["_reference_smallsat"]["added_points"][lvl])
            g[c]["normalised_terrestrial_ratio"][lvl] = new_t / t
            g[c]["ssci_lin_new"][lvl] = (new_t + a + o) / 3
    res["G_propellant_production"] = g
    # ---------------- H. a trade-off across domains: Sentinel-6 with and without disposal ----------------
    rj = json.load(open(OUT / "sentinel6" / "results.json"))
    sub = rj["raw_scores"]["orbital"]["normalised_subscores"]
    p = CASES["sentinel6"]
    tres_nat = t_nat(p["h"])
    f_dgp = (p["top"] + tres_nat) / (p["top"] + p["tres"])
    iO_with = (sub["DGP"] + sub["CC"] + sub["MC"]) / 3
    iO_without = (sub["DGP"] * f_dgp + sub["CC"] + sub["MC"]) / 3
    t, a, o = scores["sentinel6"]
    prop_kg = descr["sentinel6"]["mass_budget"]["propellant_mass_kg"]
    add_pt = {lvl: prop_kg * CF["MMH"][i] / kpp for i, lvl in enumerate(("low", "mid", "high"))}
    res["H_tradeoff_sentinel6_disposal"] = dict(
        natural_residual_lifetime_yr=tres_nat, dgp_factor_without_disposal=f_dgp,
        orbital_with=iO_with, orbital_without=iO_without,
        ssci_lin_with=(t + a + iO_with) / 3, ssci_lin_without=(t + a + iO_without) / 3,
        onboard_propellant_kg=prop_kg,
        terrestrial_relative_increase_if_all_propellant_charged={k: v / singles["sentinel6"] for k, v in add_pt.items()})
    json.dump(res, open(OUT / "revision_sensitivities.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
