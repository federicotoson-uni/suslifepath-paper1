"""
Terrestrial domain — SSCI Section 3.1
======================================
Computes the EF 3.1 weighted single score for the terrestrial phase of a
space mission (raw material extraction → manufacturing → integration →
ground operations → end-of-life recycling/disposal of recoverable elements).

The inventory lives in the SusLifePath_2026_v1 OpenLCA database (built
12/06/2026: complete reference data + openLCA LCIA Methods 2.8.0 with the
official EF 3.1 + the audited/remapped SusLifePath seed v3 process library
+ the redpill_2p_v1 and smallsat_700km_sso_v1 product systems created via
IPC from the team mass budget).

Bridge to OpenLCA: olca-ipc Python client requires OpenLCA running in
server mode (Tools > Developer tools > IPC Server, JSON-RPC, port 8080,
gRPC checkbox OFF).

Behaviour:
  - If the server is reachable AND the mission's product system exists,
    the real EF 3.1 weighted single score (Pt) is returned, with the
    per-impact-category breakdown.
  - Otherwise a mass-scaling placeholder is returned WITH a RuntimeWarning,
    so the pipeline still runs end-to-end. The orchestrator normalises
    mission/reference: both must come from the same source (both EF or
    both placeholder) for the ratio to be meaningful — the `source` field
    lets the caller check this.

Author: Federico Toson
References:
  - Fazio et al. 2018 (JRC, EF 3.1 characterisation method)
  - SusLifePath seed v3 (audited 12/06/2026, see SSL/space_lca/AUDIT_REPORT)
"""
from __future__ import annotations
from dataclasses import dataclass, field
import warnings
from mission_descriptor import Mission


@dataclass
class TerrestrialResult:
    raw_score: float                          # EF 3.1 weighted single score (Pt)
    by_impact_category: dict[str, float]      # EF 3.1 categories breakdown
    by_lifecycle_tier: dict[str, float]       # 7 tiers (raw mat / mfg / ... / EOL)
    source: str = "placeholder"               # "ef31" | "placeholder"


# ----------------------------------------------------------------------- #
def _placeholder(mission: Mission) -> TerrestrialResult:
    warnings.warn(
        "Terrestrial domain uses a development placeholder "
        "(EF 3.1 weighted ~ dry_mass^1.0). Start the OpenLCA IPC server "
        "and ensure the product system exists for the real score.",
        RuntimeWarning, stacklevel=3,
    )
    raw = mission.mass_budget.dry_mass_kg * 1.0
    return TerrestrialResult(
        raw_score=raw,
        by_impact_category={"_placeholder": raw},
        by_lifecycle_tier={"_placeholder": raw},
        source="placeholder",
    )


def compute_terrestrial_score(
    mission: Mission,
    olca_host: str = "localhost",
    olca_port: int = 8080,
) -> TerrestrialResult:
    """EF 3.1 weighted aggregate for the mission's terrestrial phase.

    Looks up the product system named `mission.openlca.product_system_id`
    on the running OpenLCA instance and computes EF 3.1 (adapted) with its
    normalisation and weighting set. Falls back to the documented
    mass-scaling placeholder when the server or the product system is
    unavailable.
    """
    ps_name = getattr(getattr(mission, "openlca", None), "product_system_id", None)
    if not ps_name:
        return _placeholder(mission)

    try:
        import olca_ipc as ipc
        import olca_schema as o

        client = ipc.Client(olca_port)
        systems = {p.name: p for p in client.get_descriptors(o.ProductSystem)}
        if ps_name not in systems:
            warnings.warn(
                f"Product system '{ps_name}' not found in the OpenLCA db "
                f"({len(systems)} systems available) — placeholder used.",
                RuntimeWarning, stacklevel=2,
            )
            return _placeholder(mission)

        ef = next(m for m in client.get_descriptors(o.ImpactMethod)
                  if "EF 3.1" in (m.name or ""))
        nw = (client.get(o.ImpactMethod, ef.id).nw_sets or [None])[0]

        setup = o.CalculationSetup(
            target=o.Ref(ref_type=o.RefType.ProductSystem, id=systems[ps_name].id),
            impact_method=o.Ref(ref_type=o.RefType.ImpactMethod, id=ef.id),
            nw_set=o.Ref(id=nw.id, name=nw.name) if nw else None,
        )
        result = client.calculate(setup)
        result.wait_until_ready()
        try:
            by_cat = {}
            for iv in result.get_total_impacts():
                if iv.impact_category:
                    by_cat[iv.impact_category.name] = iv.amount
            if nw:
                weighted = result.get_weighted_impacts()
                raw = float(sum(w.amount for w in weighted))
            else:  # no weighting available: fall back to GWP as scalar proxy
                raw = float(by_cat.get("Climate change", 0.0))
        finally:
            result.dispose()

        return TerrestrialResult(
            raw_score=raw,
            by_impact_category=by_cat,
            # tier decomposition needs a contribution-tree walk — next iteration
            by_lifecycle_tier={"manufacturing+AIT": raw},
            source="ef31",
        )

    except Exception as exc:   # connection refused, schema mismatch, ...
        warnings.warn(
            f"OpenLCA bridge failed ({type(exc).__name__}: {exc}) — "
            "placeholder used.",
            RuntimeWarning, stacklevel=2,
        )
        return _placeholder(mission)
