"""
Mission descriptor for the SSCI toolchain
==========================================
Loads a per-mission YAML file into a typed `Mission` dataclass that the
three domain modules and the orchestrator consume.

The schema is documented in ARCHITECTURE.md Section 3.

Author: Federico Toson
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class Orbit:
    altitude_km: float
    inclination_deg: float
    eccentricity: float
    operational_lifetime_yr: float
    residual_lifetime_yr: float


@dataclass
class MassBudget:
    dry_mass_kg: float
    propellant_mass_kg: float
    total_wet_mass_kg: float


@dataclass
class Geometry:
    exposed_surface_m2: float
    total_surface_m2: float
    cross_section_m2: float


@dataclass
class Cost:
    build_cost_usd: float
    programme_cost_usd: float
    reference_cost_class: str           # smallsat / medium / large


@dataclass
class Material:
    id: str
    mass_kg: float
    criticality_factor: float           # Graedel 2015 scale, 0..1


@dataclass
class Launch:
    vehicle: str
    propellant_share_kg: dict[str, float]   # {"kerosene": ..., "LOX": ...}


@dataclass
class Reentry:
    reentry_class: str                   # small_uncontrolled / controlled
    expected_demise_fraction: float      # 0..1 mass fraction demising


@dataclass
class OpenLCA:
    product_system_id: str               # ID inside the SusLifePath library


@dataclass
class Output:
    reference_mission: str               # YAML id of the reference


@dataclass
class Mission:
    id: str
    description: str
    orbit: Orbit
    mass_budget: MassBudget
    geometry: Geometry
    cost: Cost
    materials: list[Material]
    launch: Launch
    reentry: Reentry
    openlca: OpenLCA
    output: Output

    # ------------------------------------------------------------------ #
    @classmethod
    def from_yaml(cls, path: str | Path) -> "Mission":
        with open(path, "r") as f:
            d = yaml.safe_load(f)
        return cls(
            id=d["id"],
            description=d.get("description", ""),
            orbit=Orbit(**d["orbit"]),
            mass_budget=MassBudget(**d["mass_budget"]),
            geometry=Geometry(**d["geometry"]),
            cost=Cost(**d["cost"]),
            materials=[Material(**m) for m in d["materials"]],
            launch=Launch(**d["launch"]),
            reentry=Reentry(**d["reentry"]),
            openlca=OpenLCA(**d["openlca"]),
            output=Output(**d["output"]),
        )

    # ------------------------------------------------------------------ #
    def validate(self) -> list[str]:
        """Return a list of validation warnings (empty if clean)."""
        warnings: list[str] = []

        # Mass coherence
        m_sum = sum(m.mass_kg for m in self.materials)
        if abs(m_sum - self.mass_budget.dry_mass_kg) > 0.05 * self.mass_budget.dry_mass_kg:
            warnings.append(
                f"Materials sum {m_sum:.2f} kg differs from dry_mass "
                f"{self.mass_budget.dry_mass_kg:.2f} kg by >5%."
            )
        # Wet mass coherence
        wet = self.mass_budget.dry_mass_kg + self.mass_budget.propellant_mass_kg
        if abs(wet - self.mass_budget.total_wet_mass_kg) > 0.01:
            warnings.append(
                f"dry + prop = {wet:.3f} kg differs from total_wet_mass "
                f"{self.mass_budget.total_wet_mass_kg:.3f} kg."
            )
        # Orbit
        if self.orbit.altitude_km < 200 or self.orbit.altitude_km > 36000:
            warnings.append(
                f"altitude {self.orbit.altitude_km} km outside [200, 36000] LEO/GEO."
            )
        # Criticality range
        for m in self.materials:
            if not 0.0 <= m.criticality_factor <= 1.0:
                warnings.append(
                    f"material {m.id}: criticality_factor "
                    f"{m.criticality_factor} outside [0,1]."
                )
        return warnings
