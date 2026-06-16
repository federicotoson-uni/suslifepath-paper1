"""
SSCI orchestrator — top-level CLI for the Paper 1 toolchain
============================================================
Reads a mission YAML, routes it through the 3 domain modules, collects raw
scores, calls ssci.py for aggregation and sensitivity, writes results.

Usage:

    python ssci_orchestrator.py missions/redpill_12u.yaml \
        --reference missions/_reference_smallsat.yaml \
        --output outputs/redpill_12u/

Outputs (in --output dir):
  - results.json       full numerical results
  - table2.md          Table 2 ready for Paper 1 LaTeX
  - sensitivity.csv    Dirichlet samples for Figure 5

Author: Federico Toson
"""
from __future__ import annotations
import argparse
import json
from dataclasses import asdict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from mission_descriptor import Mission
from domain_terrestrial import compute_terrestrial_score
from domain_atmospheric import compute_atmospheric_score
from domain_orbital     import compute_orbital_score
from ssci import (DomainScores, normalise_orbital, ssci_linear, ssci_risk,
                  weights_equal, weights_expert, sensitivity_weights)


# ----------------------------------------------------------------------- #
def _compute_one(mission: Mission, label: str = "") -> tuple:
    """Compute the 3 raw domain scores + scaled scores for one mission."""
    print(f"\n[{mission.id}] {label}")
    print("  Computing terrestrial score (OpenLCA + EF 3.1)...")
    ter = compute_terrestrial_score(mission)
    print(f"    raw = {ter.raw_score:.4g}")
    print("  Computing atmospheric score (Ross/Maloney/Ferreira)...")
    atm = compute_atmospheric_score(mission)
    print(f"    raw = {atm.raw_score:.4g}  "
          f"(launch={atm.by_phase['launch']:.4g} | "
          f"reentry={atm.by_phase['reentry']:.4g})")
    print("  Computing orbital score (ECOB proxy + CC + MC)...")
    orb = compute_orbital_score(mission)
    print(f"    DGP={orb.DGP:.4g}  CC={orb.CC:.4g}  MC={orb.MC:.4g}  "
          f"(normalised per sub-category downstream)")
    return ter, atm, orb


def run_mission(mission_yaml: Path, reference_yaml: Path,
                output_dir: Path, seed: int = 42,
                reference_scores_cache: DomainScores = None,
                reference_orbital_cache: dict = None) -> dict:
    """Run the full SSCI pipeline on one mission and write outputs.

    If `reference_scores_cache` (and `reference_orbital_cache`, the reference
    DGP/CC/MC sub-scores) is provided, the reference mission is not recomputed
    (batch mode).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    mission = Mission.from_yaml(mission_yaml)
    warnings = mission.validate()
    if warnings:
        print(f"\n[{mission.id}] Validation warnings:")
        for w in warnings:
            print(f"  - {w}")

    # -- Mission raw scores ----------------------------------------------- #
    ter, atm, orb = _compute_one(mission, label="MISSION")

    # -- Reference raw scores (cache or compute) -------------------------- #
    reference = Mission.from_yaml(reference_yaml)
    reference_id = reference.id
    if reference_scores_cache is None:
        ref_ter, ref_atm, ref_orb = _compute_one(reference, label="REFERENCE")
        reference_scores = DomainScores(
            terrestrial=ref_ter.raw_score,
            atmospheric=ref_atm.raw_score,
            orbital=ref_orb.raw_score,
        )
        reference_sub = {"DGP": ref_orb.DGP, "CC": ref_orb.CC, "MC": ref_orb.MC}
    else:
        reference_scores = reference_scores_cache
        reference_sub = reference_orbital_cache
        print(f"\n[{reference_id}] reference scores reused from cache")
    ref_raw = {
        "terrestrial": reference_scores.terrestrial,
        "atmospheric": reference_scores.atmospheric,
        "orbital":     reference_scores.orbital,
    }

    # -- Normalisation (Section 3.4; orbital per sub-category, Eq. orbital) - #
    iT = ter.raw_score / reference_scores.terrestrial
    iA = atm.raw_score / reference_scores.atmospheric
    iO, iO_sub, orb_shares = normalise_orbital(
        {"DGP": orb.DGP, "CC": orb.CC, "MC": orb.MC}, reference_sub)
    sn = np.array([iT, iA, iO])

    # -- Aggregation + sensitivity ---------------------------------------- #
    w_eq, w_ex = weights_equal(), weights_expert()
    ssci_results = {
        "scores_norm": {"terrestrial": iT, "atmospheric": iA, "orbital": iO},
        "SSCI_linear_equal":  ssci_linear(sn, w_eq),
        "SSCI_linear_expert": ssci_linear(sn, w_ex),
        "SSCI_risk":          ssci_risk(sn),
    }
    sens = sensitivity_weights(sn, n_samples=10000, seed=seed)

    orb_out = asdict(orb)
    orb_out["breakdown_pct"] = orb_shares          # normalised shares (Fig 4 / Table 3)
    orb_out["normalised_subscores"] = iO_sub
    out = {
        "mission_id": mission.id,
        "reference_id": reference_id,
        "raw_scores": {
            "terrestrial": asdict(ter),
            "atmospheric": asdict(atm),
            "orbital":     orb_out,
        },
        "reference_raw_scores": ref_raw,
        "reference_subscores_orbital": reference_sub,
        "ssci": ssci_results,
        "sensitivity_dirichlet_10k": sens,
    }
    with open(output_dir / "results.json", "w") as f:
        json.dump(out, f, indent=2)
    _write_table2_md(out, output_dir / "table2.md")
    print(f"  -> {output_dir}")
    return out


def run_batch(mission_yamls: list, reference_yaml: Path,
              output_dir: Path, seed: int = 42) -> list:
    """Run the SSCI pipeline on multiple missions sharing one reference.

    Reference scores computed ONCE and reused. Per-mission outputs in
    `output_dir/<mission_id>/`. Aggregate `_summary.md` in `output_dir/`.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Compute reference once
    reference = Mission.from_yaml(reference_yaml)
    print(f"\n========== REFERENCE: {reference.id} ==========")
    ref_ter, ref_atm, ref_orb = _compute_one(reference, label="REFERENCE")
    reference_scores = DomainScores(
        terrestrial=ref_ter.raw_score,
        atmospheric=ref_atm.raw_score,
        orbital=ref_orb.raw_score,
    )
    reference_sub = {"DGP": ref_orb.DGP, "CC": ref_orb.CC, "MC": ref_orb.MC}

    # Loop over missions
    results = []
    for my in mission_yamls:
        print(f"\n========== MISSION: {Path(my).stem} ==========")
        sub_dir = output_dir / Path(my).stem
        r = run_mission(my, reference_yaml, sub_dir, seed=seed,
                        reference_scores_cache=reference_scores,
                        reference_orbital_cache=reference_sub)
        results.append(r)

    # Aggregate summary
    _write_summary_md(results, output_dir / "_summary.md")
    print(f"\nSummary written to {output_dir / '_summary.md'}")
    return results


def _write_summary_md(results: list, path: Path) -> None:
    """Write a comparative summary across N missions."""

    def fmt(x: float) -> str:
        if x == 0: return "0"
        if abs(x) >= 1e-2: return f"{x:.3f}"
        return f"{x:.3e}"

    lines = [
        "**Table 2.** Comparative SSCI scores across mission case studies. "
        "All scores normalised against the reference mission.",
        "",
        "| Quantity | " + " | ".join(r["mission_id"] for r in results) + " |",
        "|---" + "|---" * len(results) + "|",
    ]
    for key, label in [
        ("terrestrial", r"$\tilde{I}_T$ (terrestrial)"),
        ("atmospheric", r"$\tilde{I}_A$ (atmospheric)"),
        ("orbital",     r"$\tilde{I}_O$ (orbital)"),
    ]:
        row = [fmt(r["ssci"]["scores_norm"][key]) for r in results]
        lines.append(f"| {label} | " + " | ".join(row) + " |")
    for key, label in [
        ("SSCI_linear_equal",  r"$SSCI^{lin}$ equal $w$"),
        ("SSCI_linear_expert", r"$SSCI^{lin}$ expert $w$"),
        ("SSCI_risk",          r"$SSCI^{risk}$ geometric"),
    ]:
        row = [fmt(r["ssci"][key]) for r in results]
        lines.append(f"| {label} | " + " | ".join(row) + " |")

    # Orbital breakdown row
    lines += [
        "",
        "**Orbital breakdown (% of $\\tilde{I}_O$)**:",
        "",
        "| Component | " + " | ".join(r["mission_id"] for r in results) + " |",
        "|---" + "|---" * len(results) + "|",
    ]
    for comp in ["DGP", "CC", "MC"]:
        row = [f"{r['raw_scores']['orbital']['breakdown_pct'][comp]:.1f}%"
               for r in results]
        lines.append(f"| {comp} | " + " | ".join(row) + " |")

    # Atmospheric breakdown row
    lines += [
        "",
        "**Atmospheric phase split (% of $\\tilde{I}_A$ raw)**:",
        "",
        "| Phase | " + " | ".join(r["mission_id"] for r in results) + " |",
        "|---" + "|---" * len(results) + "|",
    ]
    for ph in ["launch", "reentry"]:
        row = []
        for r in results:
            tot = r["raw_scores"]["atmospheric"]["raw_score"]
            v = r["raw_scores"]["atmospheric"]["by_phase"][ph]
            pct = 100.0 * v / tot if tot > 0 else 0.0
            row.append(f"{pct:.1f}%")
        lines.append(f"| {ph} | " + " | ".join(row) + " |")

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


# ----------------------------------------------------------------------- #
def _write_table2_md(out: dict, path: Path) -> None:
    """Format a markdown Table 2 ready to paste in Paper 1 LaTeX."""
    s = out["ssci"]["scores_norm"]
    r = out["ssci"]
    def fmt(x: float) -> str:
        if x == 0:
            return "0"
        if abs(x) >= 1e-2:
            return f"{x:.3f}"
        return f"{x:.3e}"

    lines = [
        "**Table 2.** Domain-specific impact scores and composite SSCI for "
        f"the `{out['mission_id']}` mission. All scores normalised against "
        f"the `{out['reference_id']}` reference mission.",
        "",
        "| Quantity | Value | Notes |",
        "|---|---|---|",
        f"| $\\tilde{{I}}_T$ (terrestrial) | {fmt(s['terrestrial'])} | EF 3.1 weighted aggregate (placeholder mass-scaling for v0) |",
        f"| $\\tilde{{I}}_A$ (atmospheric) | {fmt(s['atmospheric'])} | Ross/Maloney/Ryan emission model |",
        f"| $\\tilde{{I}}_O$ (orbital)     | {fmt(s['orbital'])} | ECOB proxy + CC + MC |",
        f"| $SSCI^{{lin}}$ — equal weights   | {fmt(r['SSCI_linear_equal'])} | $w_T = w_A = w_O = 1/3$ |",
        f"| $SSCI^{{lin}}$ — expert weights  | {fmt(r['SSCI_linear_expert'])} | Indicative Delphi |",
        f"| $SSCI^{{risk}}$ (geometric)      | {fmt(r['SSCI_risk'])} | Eq. 9 of Section 3.4 |",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


# ----------------------------------------------------------------------- #
def _parse_args():
    p = argparse.ArgumentParser(description="SSCI toolchain orchestrator")
    p.add_argument("mission", type=Path, nargs="+",
                   help="one or more mission YAML paths (batch mode)")
    p.add_argument("--reference", type=Path, required=True,
                   help="reference-mission YAML path")
    p.add_argument("--output", type=Path, default=Path("outputs/"),
                   help="output directory")
    p.add_argument("--seed", type=int, default=42,
                   help="Dirichlet sampling seed")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if len(args.mission) == 1:
        run_mission(args.mission[0], args.reference,
                    args.output / args.mission[0].stem, seed=args.seed)
    else:
        run_batch(args.mission, args.reference, args.output, seed=args.seed)
