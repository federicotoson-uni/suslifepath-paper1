"""
Orbital domain — SSCI Section 3.2
==================================
Computes the orbital impact raw score combining:

  DGP : Debris Generation Potential — adopted from the Paper 0 collective
        proxy (snapshot-ECOB approximation). The full ECOB index of
        Letizia et al. 2016 is out of scope for the Paper 1 pilot; the
        rationale is documented in Section 3.5 of the manuscript.
  CC  : Congestion Contribution — integral of the operational exclusion
        volume against the resident population density over the mission's
        operational lifetime.
  MC  : Material Criticality — sum over the spacecraft material inventory
        of (mass * criticality_factor * orbit_loss_multiplier).

The three sub-scores DGP, CC and MC are returned separately; they carry
incommensurable units, so the normalised orbital score I_tilde_O is built by
`ssci.normalise_orbital()`, which normalises EACH sub-score to the reference
mission before averaging (Eq. orbital, Section 3.2). `raw_score` (their plain
sum) is retained for diagnostics only and is NOT used in the aggregation.

MATLAB integration: DGP and CC require the Paper 0 MATLAB modules
(individual_probability_flux.m, collective_probability.m, ecob_proxy.m,
plus the new congestion_contribution.m). They are called via a thin
subprocess+CSV bridge (matlab_bridge.py).

Author: Federico Toson
References:
  - Paper 0 (Toson 2026, Zenodo v2.0.1, DOI:10.5281/zenodo.20625216)
  - Letizia, Colombo, Lewis, Krag 2016, 2017 (ECOB)
  - Graedel et al. 2015 (terrestrial material criticality)
"""
from __future__ import annotations
from dataclasses import dataclass
from mission_descriptor import Mission


@dataclass
class OrbitalResult:
    raw_score: float                          # I_O (DGP + CC + MC raw)
    DGP: float                                # debris generation potential
    CC: float                                 # congestion contribution
    MC: float                                 # material criticality
    breakdown_pct: dict[str, float]           # raw-sum shares, diagnostic only


# ----------------------------------------------------------------------- #
def compute_orbital_score(mission: Mission) -> OrbitalResult:
    """Compute the orbital raw impact score for a mission.

    Coordinates the three sub-modules:
      1. DGP via the MATLAB ECOB proxy (Paper 0 modules)
      2. CC  via the MATLAB congestion_contribution.m (new for Paper 1)
      3. MC  via the Python material-criticality formula

    Returns the OrbitalResult with the per-category sub-scores and their plain
    sum (raw_score). The meaningful regime decomposition (Figure 4 / Table 3)
    is the NORMALISED one, computed by ssci.normalise_orbital() in the
    orchestrator; raw_score and breakdown_pct here are diagnostic only.
    """
    DGP = _compute_DGP(mission)
    CC  = _compute_CC(mission)
    MC  = _compute_MC(mission)

    raw = DGP + CC + MC
    if raw <= 0:
        breakdown = {"DGP": 0.0, "CC": 0.0, "MC": 0.0}
    else:
        breakdown = {
            "DGP": 100.0 * DGP / raw,
            "CC":  100.0 * CC  / raw,
            "MC":  100.0 * MC  / raw,
        }
    return OrbitalResult(
        raw_score=raw, DGP=DGP, CC=CC, MC=MC, breakdown_pct=breakdown,
    )


# ----------------------------------------------------------------------- #
def _compute_DGP(mission: Mission) -> float:
    """Debris Generation Potential — calls MATLAB ECOB-proxy single wrapper.

    Bridges to paper0_ecob_proxy_single.m via matlab_bridge.call_matlab,
    which itself wraps Paper 0's `collective_probability.m` and `ecob_proxy.m`
    against the Celestrak May 2026 snapshot.

    Returns the normalised collective score R_col (= DGP for the SSCI).
    """
    from pathlib import Path
    from matlab_bridge import call_matlab

    script = Path(__file__).parent / "paper0_ecob_proxy_single.m"
    inputs = {
        "altitude_km":          mission.orbit.altitude_km,
        "inclination_deg":      mission.orbit.inclination_deg,
        "eccentricity":         mission.orbit.eccentricity,
        "op_lifetime_yr":       mission.orbit.operational_lifetime_yr,
        "residual_lifetime_yr": mission.orbit.residual_lifetime_yr,
        "mass_kg":              mission.mass_budget.dry_mass_kg,
        "cross_section_m2":     mission.geometry.cross_section_m2,
        "exposed_surface_m2":   mission.geometry.exposed_surface_m2,
        "total_surface_m2":     mission.geometry.total_surface_m2,
        "cost_usd":             mission.cost.build_cost_usd,
    }
    result = call_matlab(script, inputs)
    return float(result["DGP"])


def _compute_CC(mission: Mission) -> float:
    """Congestion Contribution — calls MATLAB congestion_contribution.m.

    Formula (Section 3.2.2):
        CC_m = ∫ V_m^occ(h,t) * rho_op(h,t) dt   for t in [t0, t0+T_op]

    Implemented via paper0_ecob_proxy_single-style MATLAB bridge:
    operational density rho_op extracted from the Celestrak May 2026
    snapshot (same Paper 0 data); keep-out volume V_occ = (50 km)^3
    per ECSS-U-AS-10C; snapshot assumption => CC = V_occ * rho_op * T_op
    with units of satellite-year exposure.
    """
    from pathlib import Path
    from matlab_bridge import call_matlab

    script = Path(__file__).parent / "congestion_contribution.m"
    inputs = {
        "altitude_km":      mission.orbit.altitude_km,
        "op_lifetime_yr":   mission.orbit.operational_lifetime_yr,
        "cross_section_m2": mission.geometry.cross_section_m2,
    }
    result = call_matlab(script, inputs)
    return float(result["CC"])


def _compute_MC(mission: Mission) -> float:
    """Material Criticality — pure Python.

    Formula (Section 3.2.3):
        MC_m = sum_i (q_i * chi_i * eta_i^orbit)

    where q_i is the mass of material i [kg], chi_i is the Graedel 2015
    terrestrial criticality factor [0..1], and eta_i^orbit is an orbit-loss
    multiplier that captures the irreversibility of orbital deployment.

    Current eta_i^orbit model: linear in altitude above 600 km, saturating
    at h=2000 km (open decision T3 in ARCHITECTURE.md).
    """
    eta = _orbit_loss_multiplier(mission.orbit.altitude_km)
    return sum(m.mass_kg * m.criticality_factor * eta for m in mission.materials)


def _orbit_loss_multiplier(altitude_km: float) -> float:
    """eta^orbit: how irreversibly is material lost at this altitude?

    Heuristic baseline:
       h <  600 km  : eta = 0.3   (near-term decay)
       h in [600, 2000] : linear 0.3 -> 1.0
       h >= 2000 km : eta = 1.0   (effectively permanent loss)
    """
    if altitude_km < 600:
        return 0.3
    if altitude_km >= 2000:
        return 1.0
    return 0.3 + 0.7 * (altitude_km - 600) / (2000 - 600)
