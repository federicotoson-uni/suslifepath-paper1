# SSCI toolchain — architecture (Paper 1)

**Version**: 0.2 (draft, 9 giugno 2026 — pomeriggio)
**Status**: design phase, scaffold ready; atmospheric module operative

This document describes the computational architecture of the Space Sustainability
Composite Indicator (SSCI) toolchain. The toolchain implements Section 3 of
Paper 1 and produces the numerical Table 2 of Section 4 (pilot application on a
**2P PocketCube — RedPill / J2050** at 550 km SSO, ~0.8 kg, no propulsion,
full atmospheric demise on re-entry).

---

## 1. High-level data flow

```
                ┌─────────────────────────────────────────────────┐
                │             mission_descriptor.py                │
                │     (mission.yaml → Mission dataclass)           │
                └─────────────────────────────────────────────────┘
                                       │
                                       ▼
        ┌──────────────────────────────────────────────────────────────┐
        │                  ssci_orchestrator.py                          │
        │  (top-level: routes the mission to 3 domain modules,           │
        │   collects raw scores, calls ssci.py for aggregation,          │
        │   produces JSON + Markdown report)                             │
        └──────────────────────────────────────────────────────────────┘
              │                       │                        │
              ▼                       ▼                        ▼
   ┌──────────────────┐   ┌──────────────────┐    ┌──────────────────┐
   │  domain_         │   │  domain_         │    │  domain_         │
   │  terrestrial.py  │   │  atmospheric.py  │    │  orbital.py      │
   │                  │   │                  │    │                  │
   │  OpenLCA +       │   │  Ross/Maloney/   │    │  ECOB proxy      │
   │  SpaceSysLab v2  │   │  Ryan emission   │    │  (MATLAB Paper 0)│
   │  via olca-ipc    │   │  model           │    │  + CC + MC       │
   │  → EF 3.1 score  │   │  → κ × τ × m     │    │  → ECOB+CC+MC    │
   └──────────────────┘   └──────────────────┘    └──────────────────┘
              │                       │                        │
              └───────────┬───────────┴────────────┬───────────┘
                          ▼                        ▼
                ┌─────────────────────────────────────────┐
                │             ssci.py                      │
                │  (normalise → weights → linear/risk     │
                │   aggregation → sensitivity)             │
                └─────────────────────────────────────────┘
                                       │
                                       ▼
                              Table 2 of Paper 1
                              + Figures 3, 4, 5
```

---

## 2. Modules (file-by-file)

### 2.1 `ssci.py` ✅ EXISTING
**Status**: complete (232 lines).
**Role**: aggregation layer — given 3 normalised scores, computes
SSCI_linear (equal / expert / AHP weights) and SSCI_risk (geometric mean),
plus sensitivity over the Dirichlet weight simplex.
**Interface**: `compute_ssci(scores, reference, ahp_matrix) → dict`.
**No changes needed**.

### 2.2 `mission_descriptor.py` ◯ NEW
**Role**: container for all per-mission inputs (orbit, mass breakdown,
propellant chemistry, materials inventory).
**Loaded from** a per-mission YAML in `code/missions/`.
**Validation**: required fields, consistency checks (e.g. dry mass = sum of
material masses ± tolerance).

### 2.3 `domain_terrestrial.py` ◯ NEW
**Role**: wrap OpenLCA + SpaceSysLab v2 to compute the EF 3.1 weighted score
for the manufacturing + ground operations + end-of-life phases of the mission.
**Bridge**: `olca-ipc` (Python client to a running OpenLCA server).
**Input**: a SpaceSysLab v2 product-system identifier (e.g. `redpill_12u_v1`).
**Output**: float (terrestrial raw score) + breakdown per impact category.

### 2.4 `domain_atmospheric.py` ◯ NEW
**Role**: compute stratospheric impact from launch + re-entry events,
following Ross & Toohey 2019, Maloney 2022, Ryan 2022.
**Method**: for each propellant species $e$ (NOₓ, Al₂O₃, BC, H₂O, HCl):

$$\tilde{I}_A = \sum_e \kappa_e \cdot \tau_e \cdot m_e$$

where $\kappa_e$ is a radiative/chemical effectiveness coefficient and $\tau_e$
the stratospheric residence time. Reference: WMO 2022 ozone assessment for $\tau_e$.
**Static data**: `data/emission_factors.yaml` (per propellant) and
`data/stratospheric_factors.yaml` ($\kappa, \tau$ per species).
**Pure Python**, no external bridge.

### 2.5 `domain_orbital.py` ◯ NEW
**Role**: compute the orbital impact score combining
- ECOB proxy (debris generation potential, $DGP$) — reusing the MATLAB
  modules `individual_probability_flux.m`, `collective_probability.m`,
  `ecob_proxy.m` from Paper 0 (sole-author Zenodo release v2.0.0).
- Congestion Contribution ($CC$) — NEW MATLAB module
  `congestion_contribution.m` to be added to the Paper 1 repo. Computes
  $\int_{t_0}^{t_0+T_{op}} V^{occ}_m(h,t) \cdot \rho_{op}(h,t)\,dt$.
- Material Criticality ($MC$) — pure Python computation using Graedel 2015
  criticality factors and an orbit-loss multiplier $\eta^{orbit}$.

**MATLAB bridge**: subprocess + CSV. We call MATLAB in batch mode
(`matlab -batch`) passing mission parameters as MATLAB script-arg via a
temporary `.mat` or JSON file, and parse the resulting CSV output. This
avoids the dependency on `matlab.engine.python` (which requires a separate
install) and reuses the Paper 0 pipeline already working from CLI.

**Note**: the ECOB *proxy* from Paper 0 is used here as the orbital debris
component for the SSCI. The Paper 1 manuscript explicitly states this is a
*screening* proxy; the full ECOB (Letizia 2016, 200-yr MC propagation) is
out of scope for the Paper 1 pilot and would require either a Letizia/Colombo
collaboration or a re-implementation outside the scope of this work.

### 2.6 `ssci_orchestrator.py` ◯ NEW
**Role**: CLI entry point. Reads `missions/<id>.yaml`, calls the 3 domain
modules in sequence, collects raw scores into a `DomainScores`, calls
`ssci.compute_ssci(...)`, and writes:
- `outputs/<id>_results.json` — full results
- `outputs/<id>_table2.md` — Table 2 ready to paste in Paper 1 LaTeX
- `outputs/<id>_sensitivity.csv` — Dirichlet samples for Figure 5

**Usage**:
```
python ssci_orchestrator.py missions/redpill_12u.yaml
```

### 2.7 `matlab_bridge.py` ✅ DONE
**Role**: thin utility module to call MATLAB scripts from Python via
`subprocess.run(['matlab','-batch', ...])` and parse CSV output back.
Reused by `domain_orbital.py` for both DGP and CC.

### 2.8 `congestion_contribution.m` ✅ DONE
**Role**: computes the CC orbital category. Per ECSS-U-AS-10C: keep-out
volume $V^{occ} = (50\,\mathrm{km})^3$, density $\rho_{op}(h)$ from the
Celestrak May 2026 active-satellite shell at mission altitude $\pm 25$ km,
$CC = V^{occ} \cdot \rho_{op} \cdot T_{op}$ [sat $\cdot$ yr].

### 2.9 `openlca_bridge.py` ◯ pending (will be inline in `domain_terrestrial.py`)
**Role**: thin wrapper around `olca-ipc` for the OpenLCA Python client.
See `OPENLCA_SETUP.md` for the deployment plan.

---

## 3. Mission descriptor (YAML schema)

`code/missions/redpill_2p.yaml` (example):

```yaml
id: redpill_2p
description: RedPill 2P PocketCube, J2050 mission, 550 km SSO

orbit:
  altitude_km: 550
  inclination_deg: 97.6             # SSO at this altitude
  eccentricity: 0.001
  operational_lifetime_yr: 2        # 1-3 yr typical PocketCube
  residual_lifetime_yr: 8           # rapid passive decay at 550 km, IADC-OK

mass_budget:
  dry_mass_kg: 0.8                  # 2P PocketCube (5x5x10 cm)
  propellant_mass_kg: 0.0           # NO propulsion
  total_wet_mass_kg: 0.8

geometry:
  exposed_surface_m2: 0.012         # ~120 cm^2 deployed Sun-facing
  total_surface_m2: 0.025
  cross_section_m2: 0.0050          # ~50 cm^2 perigee cross-section

cost:
  build_cost_usd: 1.0e5             # ~100 kUSD university-grade build
  programme_cost_usd: 3.0e5
  reference_cost_class: pocketcube

materials:                          # for MC category — placeholder, refine
                                    # with the RedPill BOM from Porcarelli 2025
  - { id: aluminium_6061,     mass_kg: 0.30, criticality_factor: 0.15 }
  - { id: PCB_FR4,            mass_kg: 0.20, criticality_factor: 0.30 }
  - { id: silicon_solar_cells,mass_kg: 0.05, criticality_factor: 0.65 }
  - { id: lithium_battery,    mass_kg: 0.10, criticality_factor: 0.85 }
  - { id: copper_wiring,      mass_kg: 0.05, criticality_factor: 0.20 }
  - { id: misc_electronics,   mass_kg: 0.10, criticality_factor: 0.55 }

launch:
  vehicle: Falcon9_rideshare        # typical for sub-kg secondary payloads
  propellant_share_kg:              # share attributable to a 0.8 kg payload
                                    # on Falcon 9 (~550 t propellant total
                                    # for ~16 t to LEO; share ~= 0.8/16000)
    kerosene: 7.0                   # =~ 0.8 kg / 16000 kg * 140000 kg RP-1
    LOX:      28.0                  # 4:1 LOX:RP1 mass ratio

reentry:
  reentry_class: small_uncontrolled
  expected_demise_fraction: 1.00    # full demise expected for <1 kg dry mass

openlca:
  product_system_id: redpill_2p_v1  # ID in the new SusLifePath LCA archive

output:
  reference_mission: smallsat_700km_sso   # 500 kg / 700 km SSO smallsat
```

---

## 4. Pilot end-to-end run

```
python ssci_orchestrator.py missions/redpill_12u.yaml \
    --reference missions/_reference_smallsat.yaml \
    --output outputs/redpill_12u/
```

Expected wall-clock: ~30 s (orbital MATLAB call + OpenLCA EF 3.1 + Monte
Carlo sensitivity 10⁴ samples). Result: Table 2 numerical values for Paper 1
Section 4.3, replacing the current "indicative" placeholders.

---

## 5. Implementation roadmap

| Week | Module | Status |
|---|---|---|
| 1 (9 giu 2026) | `mission_descriptor.py`, `ssci_orchestrator.py` scaffold | ✅ done |
| 1 | `matlab_bridge.py` + `paper0_ecob_proxy_single.m` (DGP wired) | ✅ done |
| 1 | `congestion_contribution.m` (CC wired) | ✅ done |
| 1 | `domain_atmospheric.py` + emission factors (Ross/Maloney/Ferreira/WMO) | ✅ done |
| 1 | Mission YAMLs (`redpill_2p.yaml`, `_reference_smallsat.yaml`) | ✅ done |
| 1 | venv + requirements.txt + .gitignore | ✅ done |
| 1 | End-to-end pipeline run with placeholders | ✅ done |
| **2-3** | `domain_terrestrial.py` olca-ipc bridge + `SusLifePathLCA_2026_v1` archive | ⏳ blocked on Federico OpenLCA setup |
| **2** | Mission YAML refinement with Vignato IAC 2025 RedPill BOM | ⏳ blocked on Vignato |
| 3-4 | Pilot run with REAL Table 2 numbers | ◯ pending T2 unblocks |
| 4-5 | Figures 3, 4, 5 from `outputs/redpill_2p/sensitivity.csv` | ◯ |
| 5-6 | Repo `suslifepath-paper1` GitHub + Zenodo DOI minting | ◯ |

---

## 6. Open decisions

| ID | Topic | Default | Action |
|---|---|---|---|
| T1 | MATLAB bridge: subprocess+CSV vs matlab.engine.python | subprocess+CSV | confirmed (Paper 0 already runs this way) |
| T2 | OpenLCA bridge: olca-ipc vs file-based JSON-LD | olca-ipc | needs OpenLCA running in server mode |
| T3 | $\eta^{orbit}$ multiplier in MC category — model | linear in altitude | needs justification in Section 3.2 |
| T4 | Atmospheric κ values — source | Ross 2019 + WMO 2022 | needs Federico cross-check |
| T5 | Reference mission for normalisation | median SpaceSysLab v2 | as per Section 4.1 |
| T6 | RedPill 2P PocketCube: mass/material breakdown publicly cite-able? | check Porcarelli + Vignato IAC 2025 | needs confirmation |
| T7 | SusLifePath LCA archive: new openLCA archive built for Paper 1 (NOT SpaceSysLab v2, that's for SSL didactica) | confirmed 9 giu 2026 | name TBD, suggested `SusLifePathLCA_2026_v1` |
