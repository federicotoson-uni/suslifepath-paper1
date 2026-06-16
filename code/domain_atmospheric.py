"""
Atmospheric domain — SSCI Section 3.3
======================================
Computes the stratospheric impact score of a mission's launch + re-entry
events following the Ross/Maloney/Ryan emission framework and the WMO 2022
ozone assessment characterisation factors.

Method (Section 3.3 of Paper 1):

    I_atm = sum over species e of (kappa_e * tau_e * mass_e)

with kappa_e = radiative/chemical effectiveness (units depend on species),
     tau_e   = stratospheric residence time [yr]
     mass_e  = total mass of species e emitted by the mission [kg]

The raw I_atm is then divided by the reference-mission I_atm in `ssci.py`
normalise() to obtain the dimensionless I_tilde_A.

Author: Federico Toson
References:
  - Ross & Toohey 2019, Eos 100
  - Maloney et al. 2022, PNAS
  - Ryan et al. 2022, Earth's Future
  - WMO 2022, Scientific Assessment of Ozone Depletion
"""
from __future__ import annotations
from dataclasses import dataclass
from mission_descriptor import Mission


# ----------------------------------------------------------------------- #
#  STATIC DATA: emission factors and stratospheric characterisation factors.
#  ---------------------------------------------------------------
#  Each numeric value carries an inline reference. The two-tier
#  structure (separate tau and kappa, with their product kappa*tau
#  used in the final score) makes it easy to do one-at-a-time sensitivity
#  in Section 4.4 of the paper.
# ----------------------------------------------------------------------- #

# (1) Emission factors per kg of propellant burned in the stratosphere.
#     Units: kg of species emitted / kg of propellant.
#     Refs:
#       [Ross & Toohey, 2019, Eos] - BC emission index of high-BC kerosene
#         engines ~100x larger than aviation (=> ~20-30 g/kg fuel);
#         SRM alumina up to 300 g/kg, HCl up to 210 g/kg.
#       [Dallas et al., 2020, J. Cleaner Prod.] - launch emissions LCA review.
#       [Maloney et al., 2022, JGR Atm.] - 10 Gg/yr global rocket BC scenario
#         used as anchor for the kerosene BC factor.
EMISSION_FACTORS_LAUNCH = {
    "kerosene": {  # RP-1 (Falcon 9 first stage, Soyuz, Atlas V-class)
        "NOx":   0.001,  # negligible (no N2 in fuel; trace from air entrainment)
        "BC":    0.025,  # 25 g/kg, mid-range Ross 2019 BC emission index
        "H2O":   1.30,   # main combustion product
        "Al2O3": 0.0,
        "HCl":   0.0,
    },
    "LOX": {       # oxidiser (no standalone combustion contribution)
        "NOx": 0.0, "BC": 0.0, "H2O": 0.0, "Al2O3": 0.0, "HCl": 0.0,
    },
    "APCP": {      # Ammonium Perchlorate Composite Propellant (SRM boosters)
        "NOx":   0.0,
        "BC":    0.0,
        "H2O":   0.32,
        "Al2O3": 0.30,   # 300 g/kg (Ross & Toohey 2019)
        "HCl":   0.21,   # 210 g/kg (Ross & Toohey 2019)
    },
    "MMH": {       # Monomethyl hydrazine (storable hypergolic, upper stages)
        "NOx":   0.18,   # from N in fuel + thermal NOx
        "BC":    0.010,
        "H2O":   0.60,
        "Al2O3": 0.0,
        "HCl":   0.0,
    },
    "N2O4": {      # Dinitrogen tetroxide (storable hypergolic oxidiser)
        "NOx":   0.40,   # major NOx source (N already in molecule)
        "BC":    0.0,
        "H2O":   0.0,
        "Al2O3": 0.0,
        "HCl":   0.0,
    },
    "methane": {   # CH4 (Starship, Vulcan, Neutron)
        "NOx":   0.0005,
        "BC":    0.008,  # lower BC than kerosene
        "H2O":   2.25,   # major H2O producer
        "Al2O3": 0.0,
        "HCl":   0.0,
    },
    "hydrogen": {  # LH2 (Ariane core, SLS, Centaur)
        "NOx":   0.0,
        "BC":    0.0,
        "H2O":   9.0,    # only product
        "Al2O3": 0.0,
        "HCl":   0.0,
    },
}

# (2) Re-entry emission factors per kg of DEMISED material.
#     Refs:
#       [Ferreira et al., 2024, GRL e2024GL109280] - first atomic-scale MD
#         simulation of Al oxidation during reentry. Numbers extracted from
#         Sections 2.2 and 3.3 of the open-access full text:
#           * Spacecraft burn-up: 51-95% of mass (Anselmo & Pardini 2005;
#             Pardini & Anselmo 2019), default 95% in this work.
#           * Aluminium fraction of satellite mass: ~30% (Bonvoisin 2023).
#           * For a 250 kg satellite with 30% Al: 75 kg Al initial mass,
#             24 kg oxidised to 29.8 kg AlO clusters (oxygen-deficient,
#             not stoichiometric Al2O3), 51 kg residual unoxidised Al.
#           * Effective ratio: 29.8 / 24 = 1.24 kg AlO per kg of oxidised Al.
#           * Anthropogenic excess at TOA: 29.5% over natural meteoroid
#             flux in 2022 (308.9 t LEO reentry mass -> 41.7 t Al at TOA).
#           * Catalytic boost: 2% reaction probability for Cl activation on
#             Al2O3 surface (Hanning-Lee 1996; Molina 1997).
EMISSION_FACTORS_REENTRY = {
    # 1.24 kg AlO per kg of Al actually oxidised (Ferreira 2024 Sec 3.3).
    # The full demise releases ~32% of the Al content as AlO clusters.
    "aluminium":  {"Al2O3": 1.24 * 0.32, "NOx": 0.030},
    "stainless":  {"NOx": 0.020},
    "composites": {"NOx": 0.015, "BC": 0.010},
}

# (3) Stratospheric residence time tau (years).
#     Refs:
#       [WMO, 2022, Scientific Assessment of Ozone Depletion] - general
#         stratospheric lifetimes; CFC-12 >100 yr, methyl bromide shortest,
#         halogen content -18% from peak. Specific tau values for NOx, BC,
#         alumina and water from chapter-level numerics (consensus values).
#       [Maloney et al., 2022, JGR Atm.] - 10 Gg/yr stratospheric BC ->
#         maximum 4% ozone reduction at North Pole in June, multi-year BC
#         burden in the stratosphere consistent with tau ~ 4-5 yr.
#       [Ferreira et al., 2024, GRL Sec 3.2] - alumina nanoparticles 0.4-4.2 nm
#         aerodynamic diameter, settling time UP TO 30 YEARS from the top of
#         the mesosphere (86 km) to the ozone layer (40 km). Average expected
#         diameter 4.1 nm. We adopt 15 yr as the effective stratospheric
#         tau, capturing both settling and the catalytic persistence on
#         particle surfaces (each particle acts as a perpetual reaction
#         site for Cl activation, 2% reaction probability).
STRATOSPHERIC_TAU = {  # years
    "NOx":   1.5,   # 1-2 yr in lower stratosphere
    "Al2O3": 15.0,  # Ferreira 2024: up to 30 yr settling + catalytic persistence
    "BC":    4.5,   # 4-5 yr (Maloney 2022)
    "H2O":   2.5,   # 2-3 yr stratospheric water
    "HCl":   4.0,   # Cl reservoir residence
}

# (4) Effectiveness coefficient kappa (dimensionless, relative ozone-
#     destruction potential anchored to NOx = 1.0).
#     Refs:
#       [WMO, 2022, GAW Report 278, Chapter 7, Sec. 7.2.8.1 "Influence of
#         a Growing Spaceflight Industry", pp. 409-410] - VERIFIED on the
#         full report PDF (12/06/2026): the Assessment contains NO
#         quantitative table of per-species rocket effectiveness factors;
#         the section is a qualitative synthesis of the primary papers.
#         Section-level support for the adopted ordering:
#           * alumina: ozone loss via heterogeneous Cly activation, "less
#             well bounded" (surface area density, sulfate coating, reaction
#             coefficients, Danilin 2003); in-situ plume data suggest loss
#             "could be larger than the loss from chlorine" (Danilin 2001),
#             question "remains unresolved" -> kappa 0.50, HCl-order, with
#             large declared uncertainty.
#           * H2O: +9% stratospheric water only under the extreme 100,000
#             hydrogen-launches/yr scenario (Larson 2017) -> weak per-kg
#             effect, kappa 0.10.
#           * NOx: reentry NO reduces mesospheric ozone (Ryan 2022);
#             hydrogen-economy NOx pathway dominates its ozone effect ->
#             baseline kappa 1.00.
#       RESOLVED TENSION (15/06/2026, ISSUES #6): Sec. 7.2.8.1 states that
#         "ozone loss from rocket BC is comparable to ozone loss from rocket
#         chlorine emissions (per propellant mass)" (Maloney 2022, Ryan
#         2022). With EI_BC(kerosene)=25 g/kg vs EI_HCl(APCP)=210 g/kg,
#         literal per-propellant-mass parity would imply kappa*tau(BC) ~ 40
#         yr, i.e. ~22x the adopted 1.8 yr. The baseline kappa_BC=0.40 is
#         RETAINED, because the one-at-a-time sweep in
#         paper1_kappa_bc_sensitivity.py shows the headline finding is robust:
#         over kappa_BC in [0.40, 8.96] the ranking RedPill<Sentinel-6<ENVISAT
#         is preserved, the two kerosene missions' normalised scores are
#         nearly invariant (they and the reference scale together), and only
#         ENVISAT's normalised atmospheric score moves (380x -> 121x),
#         remaining dominant. The result is reported in Sec. 4.5 of the paper.
#         Do not change the value silently; re-run the sweep if you do.
STRATOSPHERIC_KAPPA = {
    "NOx":   1.00,  # catalytic O3 destruction, baseline
    "Al2O3": 0.50,  # heterogeneous chemistry on particle surface
    "BC":    0.40,  # indirect via radiative warming + dynamics (Maloney 2022)
    "H2O":   0.10,  # weak direct effect, background-dominated
    "HCl":   1.20,  # primary chlorine reservoir, high O3 destruction
}

# (5) Combined characterisation factor: kappa * tau (units: years).
STRATOSPHERIC_KT = {
    s: STRATOSPHERIC_KAPPA[s] * STRATOSPHERIC_TAU[s]
    for s in STRATOSPHERIC_KAPPA
}


# ----------------------------------------------------------------------- #
@dataclass
class AtmosphericResult:
    raw_score: float                          # I_atm (un-normalised)
    by_species: dict[str, float]              # contribution per species
    by_phase: dict[str, float]                # {"launch": ..., "reentry": ...}


# ----------------------------------------------------------------------- #
def compute_atmospheric_score(mission: Mission) -> AtmosphericResult:
    """Compute the atmospheric raw impact score for a mission.

    Returns the AtmosphericResult containing the scalar raw score and the
    decomposition by species and by phase. The orchestrator then passes the
    raw score to ssci.normalise() for dimensionless conversion.
    """
    by_species: dict[str, float] = {s: 0.0 for s in STRATOSPHERIC_KT}
    by_phase: dict[str, float] = {"launch": 0.0, "reentry": 0.0}

    # ------ LAUNCH ------
    for prop_name, prop_mass in mission.launch.propellant_share_kg.items():
        ef = EMISSION_FACTORS_LAUNCH.get(prop_name, {})
        for species, factor in ef.items():
            kg_e = factor * prop_mass
            contrib = STRATOSPHERIC_KT.get(species, 0.0) * kg_e
            by_species[species] += contrib
            by_phase["launch"] += contrib

    # ------ REENTRY ------
    demising_mass = (
        mission.mass_budget.dry_mass_kg * mission.reentry.expected_demise_fraction
    )
    # Heuristic: split demising mass evenly across material families present.
    # For a refined treatment, infer family from `mission.materials`.
    n_families = max(1, len(EMISSION_FACTORS_REENTRY))
    per_family_mass = demising_mass / n_families
    for fam, ef in EMISSION_FACTORS_REENTRY.items():
        for species, factor in ef.items():
            kg_e = factor * per_family_mass
            contrib = STRATOSPHERIC_KT.get(species, 0.0) * kg_e
            by_species[species] += contrib
            by_phase["reentry"] += contrib

    raw = sum(by_species.values())
    return AtmosphericResult(
        raw_score=raw,
        by_species=by_species,
        by_phase=by_phase,
    )
