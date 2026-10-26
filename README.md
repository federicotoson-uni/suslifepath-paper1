# SusLifePath Paper 1: Space Sustainability Composite Indicator (SSCI)

Reproducibility package for *"Bridging Life Cycle Assessment and orbital sustainability
assessment: a multi-domain composite indicator for the environmental assessment of space
missions"* (sole author: F. Toson), under revision at the *Journal of Cleaner Production*.
Version 2.1.1 goes with the revised manuscript; versions 1.0.x went with the submitted one.

The SSCI couples three impact domains of a space mission into one composite indicator:

| Domain | What | Engine |
|---|---|---|
| Terrestrial | manufacturing, assembly, integration and test (EF 3.1 weighted single score) | OpenLCA |
| Atmospheric | stratospheric perturbation of launch and re-entry (κ·τ) | Python |
| Orbital | ECOB-aligned debris proxy, congestion (CC), material criticality (MC) | MATLAB and Python |

## Layout

```
code/
  ssci.py                          aggregation: normalisation, linear and geometric mean, Dirichlet sensitivity
  domain_terrestrial.py            EF 3.1 weighted score through the OpenLCA IPC server
  domain_atmospheric.py            stratospheric emission factors and κ·τ
  domain_orbital.py                DGP (ECOB proxy), CC and MC, normalised per sub-category
  ssci_orchestrator.py             runs the mission YAML files through the three domains, writes outputs/
  mission_descriptor.py            mission YAML schema
  matlab_bridge.py                 subprocess and CSV bridge to MATLAB
  *.m                              MATLAB modules for DGP and CC (they use the Paper 0 toolchain)
  missions/*.yaml                  the three case studies and the reference mission
  SusLifePath_seed_v4.zip          the OpenLCA library, JSON-LD (see below)
  openlca_build_mission_ps.py      builds the product system of a mission from its YAML
  reground_water.py                blue-water consumption per material class, with sources
  paper1_norm_robustness.py        normalisation sensitivity of the orbital decomposition
  paper1_eta_sensitivity.py        orbit-loss multiplier sensitivity
  paper1_kappa_bc_sensitivity.py / paper1_atm_cf_sensitivity.py   atmospheric κ·τ sensitivities
  paper1_catalogue_scale.{py,m}    300-mission catalogue-scale sample
  paper1_revision_sensitivities.py the checks added in the revision (A to N)
  build_supplementary.py           tables of the supplementary material, from the inputs above
  export_terrestrial_weighted.py   EF 3.1 weighted breakdown per impact category, to CSV
  paper1_figures.py                figures from outputs/
  iac_a6_disposal_sweep.py         IAC 2026 A6 sweep (see the last section)
  figures/                         figures of the paper; figures/iac_a6/ for the IAC 2026 paper
  outputs/                         computed results (see below)
```

## The OpenLCA library

`code/SusLifePath_seed_v4.zip` is a JSON-LD export (openLCA 2) of the database the
results were computed with: the 57 unit processes of the SusLifePath library, the
manufacturing process of each case (assembly, integration and test included) and the
product systems `redpill_2p_v1`, `sentinel6_v1`, `envisat_v1` and
`smallsat_700km_sso_v1` (the reference mission). It holds no characterisation method and
no licensed data. To use it:

1. create a database in OpenLCA 2 (2.6.2 used) with the complete reference data and the
   openLCA LCIA methods package (2.8.0 used), which contains EF 3.1;
2. import the zip (File, Import, JSON-LD);
3. start the IPC server on port 8080 (Tools, Developer tools, IPC Server, JSON-RPC).

`domain_terrestrial.py` then computes the EF 3.1 weighted single score of each product
system: 0.00229 Pt for the PocketQube, 7.54 for Sentinel-6, 39.2 for ENVISAT and 1.82 for
the reference mission.

## Requirements

- Python 3.10 or later: `numpy`, `pyyaml`; `matplotlib` for the figures; `olca-ipc` and
  `olca-schema` 2.x for the terrestrial domain.
- MATLAB (R2026a used) for DGP and CC, through `matlab_bridge.py`.
- OpenLCA with the library above, for the terrestrial domain.
- The Paper 0 toolchain checked out next to this repository as `suslifepath-paper0`
  (https://github.com/federicotoson-uni/suslifepath-paper0, Zenodo
  https://doi.org/10.5281/zenodo.20554998): its `data/celestrak_active.csv` is the
  catalogue snapshot read by the orbital module, the catalogue-scale sample and the
  revision checks.

## Reproduce the paper's numbers

### A. Without MATLAB or OpenLCA
`code/outputs/` holds the computed results, so the aggregation and the checks reproduce
offline:

```bash
cd code
python paper1_norm_robustness.py         # normalisation sensitivity of the orbital decomposition
python paper1_eta_sensitivity.py         # orbit-loss multiplier
python paper1_revision_sensitivities.py  # checks A to N (reads the Paper 0 snapshot)
python build_supplementary.py            # writes ../supplementary.tex
python paper1_figures.py                 # figures (needs matplotlib)
```
- SSCI scores of the three cases: `outputs/{redpill_2p,sentinel6,envisat}/results.json`
- Summary: `outputs/_summary.md`
- Weighted terrestrial breakdown per EF 3.1 category: `outputs/terrestrial_weighted.csv`
- Catalogue-scale sample: `outputs/catalogue_scale.json`
- Revision checks: `outputs/revision_sensitivities.json`

### B. Full run, with MATLAB and the OpenLCA IPC server
```bash
cd code
python ssci_orchestrator.py \
    missions/redpill_2p.yaml missions/sentinel6.yaml missions/envisat.yaml \
    --reference missions/_reference_smallsat.yaml --output outputs/
```
regenerates `outputs/*/results.json` and `outputs/_summary.md`, with the terrestrial
scores read live from OpenLCA (`source: ef31`).

## Changes in 2.1.1

- New check N in `paper1_revision_sensitivities.py`: the composite of the three cases
  under every test of Table 4 of the paper, one metric for all, with a changed
  convention applied to the reference mission too. `build_supplementary.py` prints it.

## Changes in 2.1.0 (revised manuscript, final checks)

- Sentinel-6, the only case in the catalogue snapshot, is excluded from the density of its
  own shell (`catalogued: true` in its descriptor, `self_exclusion_factor` in
  `domain_orbital.py`): at 1336 km the snapshot holds Sentinel-6 and Sentinel-6B alone, so
  its DGP and CC were counted twice. Its composite moves from 2.76 to 2.75.
- Liquid-oxygen loads of the Falcon 9 launches corrected to 2.49 kg per kg of RP-1 on a
  488 t load, and the hypergolic loads of ENVISAT's upper stage swapped back. Liquid
  oxygen has no stratospheric factor, so only the propellant-production check changes.
- New checks in `paper1_revision_sensitivities.py`: K, the catalogued fragmentation clouds
  added to the congestion term; L, a disposal credited in the orbit-loss multiplier; M,
  the stratospheric burden of the launch per tonne of spacecraft, Ariane 5G over Falcon 9.
- MATLAB is called with its output written to a file, not a pipe (`matlab_bridge.py`,
  `paper1_catalogue_scale.py`): recent MathWorks service hosts keep the pipe open after
  MATLAB exits, and the call never returned.
- The Paper 0 snapshot is looked up in `domain_orbital.py` in the same order as in the
  other scripts.
- Outputs, summary tables, figures and the supplementary material regenerated.

## Changes in 2.0.0 (revised manuscript)

- The library is now exported from the database of the results
  (`SusLifePath_seed_v4.zip`). Versions 1.0.x shipped `SusLifePath_seed_v3`, the seed
  file the database was built from: it predates the corrections made in the database
  afterwards (resource flows entered as inputs, water re-anchored) and lacks the three
  processes added for the PocketCube payload (brass, ITO-coated glass, PEEK).
- Blue water is consumption, as AWARE in EF 3.1 requires, not water use; values and
  sources in `reground_water.py`.
- The reference mission descriptor carries the same 500 kg inventory as its product
  system.
- Assembly, integration and test: 10 kWh per kilogram of dry mass, with a 50 kWh floor
  (`openlca_build_mission_ps.py`).
- New: `paper1_revision_sensitivities.py` and `build_supplementary.py`. All outputs and
  figures regenerated.
- The Paper 0 snapshot is found as `suslifepath-paper0` or `Paper0_SimplifiedAlgorithm`
  next to this repository, in Python as in MATLAB.
- The manuscript PDF is no longer in the repository; the article will be linked here by
  DOI on publication.

## IAC 2026 A6: population response to disposal rules

Added in v1.1.0. `code/iac_a6_disposal_sweep.py` re-scores the 600-mission
catalogue-scale sample (same seed as `paper1_catalogue_scale.py`, paired design)
under three post-mission disposal rules (no disposal, 25-year cap, 5-year cap)
and two congestion conventions (operations only, whole time in orbit), for the
IAC 2026 paper IAC-26,A6,IPB,14,x110076 (Toson and Porcarelli, "A hybrid life
cycle assessment framework for satellite end-of-life sustainability:
incorporating orbital collision risk and congestion metrics", 77th IAC,
Antalya, October 2026).

Outputs behind every table and figure of that paper:
`code/outputs/iac_a6_sweep_scale{0.8,1.0,1.8}.json`, one file per scale of the
residual-lifetime model (0.8, nominal, 1.8). Each file holds `_meta`
(`altitudini`, operating altitude in km; `archetipi`, cubesat / smallsat /
medium / large; `seed`) and, for each scenario `uncontrolled`, `rule25`,
`rule5`, six hundred values of `tres` (residual lifetime after end of
operations, years, capped at 1000), `dgp` (collision burden index, reference
mission = 1), `cc_op` and `cc_ext` (congestion over operations only and over
the whole time in orbit) and `mc` (material criticality, independent of the
rule). Figure scripts and the archetype-mix reweighting are in
`code/figures/iac_a6/`. These outputs are unchanged in 2.0.0 and 2.1.x.

Run: `python code/iac_a6_disposal_sweep.py --n 600 [--decay-scale 0.8]`. It
needs MATLAB and the Paper 0 toolchain (`suslifepath-paper0`) checked out
next to this repository; `--no-matlab` runs without the DGP term. The
two-point decay model and its calibration sources are documented in the
script docstring.

## Notes
- In the code and `outputs/`, the geometric-mean aggregation carries the key
  `SSCI_risk`; it is `SSCI^geo` in the manuscript.
- `recompute_orbital_norm.py` and `recompute_terrestrial.py` are one-time migration
  scripts, superseded: the per-sub-category orbital normalisation is native in
  `ssci.normalise_orbital` and `ssci_orchestrator.py`.
- Licence: MIT. Zenodo concept DOI (all versions): https://doi.org/10.5281/zenodo.20715157
