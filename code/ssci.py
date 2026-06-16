"""
Space Sustainability Composite Indicator (SSCI) - aggregation orchestrator
==========================================================================
Paper 1 (SusLifePath) - toolchain core.

This module implements the AGGREGATION layer of the SSCI framework
(Section 3.4 of Paper 1): it takes the three domain-specific impact scores,
normalises them against a reference mission, and combines them through two
alternative strategies (linear and geometric-mean), under three weighting
scenarios (equal, expert/Delphi, AHP). It also provides a sensitivity
analysis over the weight simplex.

What this module DOES NOT do (by design, decoupled from the domain models):
  - It does not compute the terrestrial score  -> OpenLCA EF 3.1 (domain_terrestrial)
  - It does not compute the atmospheric score   -> dedicated module (domain_atmospheric)
  - It does not compute the orbital score        -> comes from the ECOB index
    [Letizia, Colombo, Lewis & Krag, 2016; 2017] + the complementary
    Congestion (CC) and Material-Criticality (MC) categories (Section 3.2).
  The three raw scores enter here as inputs through DomainScores. Hooks to the
  real domain modules are marked `TODO(domain)`.

Design note (the ECOB decision, 29/05/2026): the orbital raw score MUST be
fed from the full ECOB index, not from the Paper-0 real-time proxy. The proxy
is for early-design screening only. See Paper 1 Section 3.2.

Dependencies: numpy only.
Author: Federico Toson
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


# ======================================================================= #
#  DOMAIN INPUTS
# ======================================================================= #
@dataclass
class DomainScores:
    """Raw (un-normalised) impact scores for a single mission.

    terrestrial : EF 3.1 weighted aggregate (OpenLCA + SusLifePath library)
    atmospheric : stratospheric perturbation score (dedicated Python module)
    orbital     : ECOB index combined with CC and MC (Section 3.2)
    """
    terrestrial: float
    atmospheric: float
    orbital: float

    def as_array(self) -> np.ndarray:
        return np.array([self.terrestrial, self.atmospheric, self.orbital],
                        dtype=float)


# TODO(domain): replace these stubs with calls to the real domain modules.
def terrestrial_score_stub(mission_id: str) -> float:
    raise NotImplementedError("Hook to OpenLCA EF 3.1 (SusLifePath library) result.")

def atmospheric_score_stub(mission_id: str) -> float:
    raise NotImplementedError("Hook to the atmospheric module (domain_atmospheric).")

def orbital_score_stub(mission_id: str) -> float:
    raise NotImplementedError("Hook to ECOB index + CC + MC (NOT the Paper-0 proxy).")


# ======================================================================= #
#  NORMALISATION  (Section 3.4: scores normalised against a reference mission)
# ======================================================================= #
def normalise(scores: DomainScores, reference: DomainScores) -> np.ndarray:
    """Return the per-domain normalised scores I_tilde = I_m / I_ref.

    The reference mission is the 500 kg / 700 km smallsat (Section 4.1),
    evaluated separately per domain. Normalisation makes the
    three domains dimensionless and comparable, so SSCI is interpretable as a
    multiplier of the reference-mission footprint.
    """
    s = scores.as_array()
    r = reference.as_array()
    if np.any(r <= 0):
        raise ValueError("Reference scores must be strictly positive.")
    return s / r


def normalise_orbital(mission_sub: dict, reference_sub: dict
                      ) -> tuple[float, dict, dict]:
    """Per-sub-category orbital normalisation (Eq. orbital, Section 3.2).

    DGP, CC and MC carry incommensurable units (a normalised collision-risk
    ratio, a satellite-year exposure and a mass-weighted criticality). Summing
    them in native units would let whichever has the largest numerical
    magnitude dominate the orbital score irrespective of physics, so each is
    normalised to the reference mission BEFORE averaging:

        I_O = (1/3) ( DGP/DGP_ref + CC/CC_ref + MC/MC_ref ).

    Returns (I_O, normalised_subscores, shares_pct), where shares_pct are the
    contributions of the three normalised sub-scores to I_O (the regime-
    specific decomposition of Figure 4 / Table 3).
    """
    isub = {k: mission_sub[k] / reference_sub[k] for k in ("DGP", "CC", "MC")}
    total = sum(isub.values())
    i_O = total / 3.0
    shares = {k: (100.0 * v / total if total > 0 else 0.0)
              for k, v in isub.items()}
    return i_O, isub, shares


# ======================================================================= #
#  WEIGHTING STRATEGIES  (Section 3.4)
# ======================================================================= #
def weights_equal() -> np.ndarray:
    """Equal weights: w_T = w_A = w_O = 1/3 (baseline)."""
    return np.array([1/3, 1/3, 1/3])


def weights_expert(w_T: float = 0.25, w_A: float = 0.40,
                   w_O: float = 0.35) -> np.ndarray:
    """Expert/Delphi weights (defaults = the indicative values of Section 4).

    TODO: replace defaults with the outcome of the structured Delphi exercise
    (Section 5.4 future work: stakeholder elicitation).
    """
    w = np.array([w_T, w_A, w_O], dtype=float)
    return w / w.sum()


def weights_ahp(pairwise: np.ndarray) -> tuple[np.ndarray, float]:
    """Analytic Hierarchy Process weights from a 3x3 pairwise-comparison matrix.

    [Saaty, 1980]. Returns (weights, consistency_ratio). A consistency ratio
    CR < 0.10 is conventionally considered acceptable.

    pairwise[i,j] = importance of domain i relative to domain j (Saaty scale).
    Domains order: [terrestrial, atmospheric, orbital].
    """
    A = np.asarray(pairwise, dtype=float)
    n = A.shape[0]
    if A.shape != (n, n):
        raise ValueError("Pairwise matrix must be square.")
    # Principal eigenvector -> weights
    eigvals, eigvecs = np.linalg.eig(A)
    k = int(np.argmax(eigvals.real))
    w = np.abs(eigvecs[:, k].real)
    w = w / w.sum()
    # Consistency ratio
    lambda_max = eigvals.real[k]
    CI = (lambda_max - n) / (n - 1) if n > 1 else 0.0
    RI = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12}.get(n, 0.58)  # Saaty's RI
    CR = CI / RI if RI > 0 else 0.0
    return w, CR


# ======================================================================= #
#  AGGREGATION  (Section 3.4)
# ======================================================================= #
def ssci_linear(scores_norm: np.ndarray, weights: np.ndarray) -> float:
    """Linear aggregation: SSCI = sum_d w_d * I_tilde_d   (Eq. linear)."""
    w = np.asarray(weights, dtype=float)
    if not np.isclose(w.sum(), 1.0):
        w = w / w.sum()
    return float(np.dot(w, scores_norm))


def ssci_risk(scores_norm: np.ndarray) -> float:
    """Geometric-mean aggregation (Eq. geo, Section 3.4).

    SSCI_geo = (prod_d I_tilde_d)^(1/3). Non-compensatory: bounded above by the
    linear score and pulled toward the SMALLEST domain score, collapsing toward
    zero if any single domain is near zero. Reported alongside the linear rule
    (not as a precautionary measure); their ratio diagnoses how unevenly a
    mission's impact is distributed across domains. (JSON key kept as
    "SSCI_risk" for continuity; the manuscript calls it SSCI^geo.)
    """
    s = np.asarray(scores_norm, dtype=float)
    if np.any(s < 0):
        raise ValueError("Normalised scores must be non-negative.")
    return float(np.prod(s) ** (1.0 / len(s)))


# ======================================================================= #
#  SENSITIVITY  (Section 4.4: SSCI over the weight simplex)
# ======================================================================= #
def sensitivity_weights(scores_norm: np.ndarray, n_samples: int = 10000,
                        seed: int | None = None) -> dict:
    """Sample weights uniformly on the simplex (Dirichlet(1,1,1)) and report
    the resulting SSCI_linear distribution.

    Note: seed is exposed for reproducibility of the paper figures; pass a
    fixed integer when generating the published sensitivity surface.
    """
    rng = np.random.default_rng(seed)
    W = rng.dirichlet(np.ones(3), size=n_samples)        # rows sum to 1
    vals = W @ scores_norm                               # SSCI_linear per sample
    return {
        "mean":   float(vals.mean()),
        "median": float(np.median(vals)),
        "p05":    float(np.percentile(vals, 5)),
        "p25":    float(np.percentile(vals, 25)),
        "p75":    float(np.percentile(vals, 75)),
        "p95":    float(np.percentile(vals, 95)),
        "min":    float(vals.min()),
        "max":    float(vals.max()),
    }


# ======================================================================= #
#  TOP-LEVEL CONVENIENCE
# ======================================================================= #
def compute_ssci(scores: DomainScores, reference: DomainScores,
                 ahp_matrix: np.ndarray | None = None) -> dict:
    """Run the full SSCI aggregation for one mission and return all variants."""
    sn = normalise(scores, reference)

    w_eq = weights_equal()
    w_ex = weights_expert()
    out = {
        "scores_norm": {"terrestrial": sn[0], "atmospheric": sn[1], "orbital": sn[2]},
        "SSCI_linear_equal":  ssci_linear(sn, w_eq),
        "SSCI_linear_expert": ssci_linear(sn, w_ex),
        "SSCI_risk":          ssci_risk(sn),
    }
    if ahp_matrix is not None:
        w_ahp, cr = weights_ahp(ahp_matrix)
        out["SSCI_linear_AHP"] = ssci_linear(sn, w_ahp)
        out["AHP_weights"] = w_ahp.tolist()
        out["AHP_consistency_ratio"] = cr
    return out


# ======================================================================= #
#  EXAMPLE / SELF-TEST
#  Uses the INDICATIVE pilot values from Paper 1 Section 4 (Table 2) to show
#  the interface. These are NOT validated numbers; they will be replaced by
#  real domain-module outputs (ECOB / OpenLCA / atmospheric module).
# ======================================================================= #
if __name__ == "__main__":
    # Indicative normalised pilot (2P PocketCube): I_T=0.92, I_A=1.37, I_O=1.18.
    # We back out raw scores == normalised by using reference = 1 per domain,
    # purely to exercise the interface.
    pilot = DomainScores(terrestrial=0.92, atmospheric=1.37, orbital=1.18)
    reference = DomainScores(terrestrial=1.0, atmospheric=1.0, orbital=1.0)

    # AHP example: atmospheric slightly > orbital > terrestrial
    ahp = np.array([
        [1,   1/3, 1/2],   # terrestrial vs (T, A, O)
        [3,   1,   2  ],   # atmospheric
        [2,   1/2, 1  ],   # orbital
    ])

    res = compute_ssci(pilot, reference, ahp_matrix=ahp)
    print("=== SSCI pilot (indicative interface test) ===")
    for k, v in res.items():
        print(f"  {k}: {v}")

    sn = normalise(pilot, reference)
    print("\n=== Sensitivity over weight simplex (seed=42) ===")
    sens = sensitivity_weights(sn, n_samples=10000, seed=42)
    for k, v in sens.items():
        print(f"  {k}: {v:.3f}")
