# SusLifePath — Paper 1: Space Sustainability Composite Indicator (SSCI)

Reproducibility package for *"Bridging Life Cycle Assessment and orbital sustainability
science: a multi-domain composite indicator for the environmental assessment of space
missions"* (sole author: F. Toson), submitted to the *Journal of Cleaner Production*.

The SSCI couples three impact domains of a space mission into one composite indicator:

| Domain | What | Engine |
|---|---|---|
| Terrestrial | manufacturing, ground, end-of-life (EF 3.1 weighted single score) | OpenLCA |
| Atmospheric | launch + re-entry stratospheric perturbation (κ·τ) | Python |
| Orbital | ECOB-aligned debris proxy + congestion (CC) + material criticality (MC) | MATLAB + Python |

## Layout

```
main.tex / main.pdf          manuscript
07_References.bib             bibliography
graphical_abstract.svg        graphical abstract (convert to PDF/PNG for upload)
code/
  ssci.py                     aggregation: normalisation, linear + geometric-mean, Dirichlet sensitivity
  domain_terrestrial.py       EF 3.1 weighted score via OpenLCA IPC
  domain_atmospheric.py       stratospheric emission factors + κ·τ
  domain_orbital.py           DGP (ECOB proxy) + CC + MC; normalised per sub-category
  ssci_orchestrator.py        mission YAML -> 3 domains -> SSCI -> outputs/
  mission_descriptor.py       mission YAML schema
  matlab_bridge.py            subprocess+CSV bridge to MATLAB
  missions/*.yaml             3 case studies + reference mission
  paper1_norm_robustness.py   normalisation-sensitivity of the orbital decomposition (Table normsens)
  paper1_eta_sensitivity.py   orbit-loss-multiplier sensitivity
  paper1_kappa_bc_sensitivity.py / paper1_atm_cf_sensitivity.py   atmospheric κ·τ sensitivities
  paper1_catalogue_scale.{py,m}   300-mission catalogue scale-up
  export_terrestrial_weighted.py  EF 3.1 weighted per-category breakdown -> CSV
  paper1_figures.py           regenerate figures from outputs/
  outputs/                    committed static result artefacts (see below)
```

## Requirements

- **Python 3.10+** (a venv lives in `code/.venv`): `numpy`, `pyyaml`; `matplotlib` (figures); `olca-ipc`, `olca-schema` (terrestrial).
- **MATLAB R2026a** — orbital DGP + CC (invoked via `matlab_bridge.py`).
- **OpenLCA 2.6.2** with the EF 3.1 method and the `SusLifePath_2026_v1` database, IPC server on port 8080 (Tools → Developer tools → IPC Server, JSON-RPC, gRPC off) — terrestrial.

## Reproduce the paper's numbers

### A. Without MATLAB or OpenLCA — from the committed static artefacts
`code/outputs/` ships the computed results, so the orbital, atmospheric and aggregation
results reproduce offline:

```bash
cd code
.venv/bin/python paper1_norm_robustness.py     # Table (normsens) + 85%<600km / 94%-denser facts
.venv/bin/python paper1_eta_sensitivity.py     # η^orbit invariance
```
- SSCI scores (Table 2): `outputs/{redpill_2p,sentinel6,envisat}/results.json`
- Comparative summary: `outputs/_summary.md`
- Terrestrial climate-led breakdown (41–44 %): `outputs/terrestrial_weighted.csv`
- Catalogue distribution: `outputs/catalogue_scale.json`
- Figures: `python3 paper1_figures.py` (needs `matplotlib`)

### B. Full end-to-end — with MATLAB + the OpenLCA IPC server running
```bash
cd code
.venv/bin/python ssci_orchestrator.py \
    missions/redpill_2p.yaml missions/sentinel6.yaml missions/envisat.yaml \
    --reference missions/_reference_smallsat.yaml --output outputs/
```
regenerates `outputs/*/results.json` and `outputs/_summary.md`, reproducing the
manuscript's Table values (terrestrial pulled live from OpenLCA, `source: ef31`).

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
`code/figures/iac_a6/`.

Run: `python code/iac_a6_disposal_sweep.py --n 600 [--decay-scale 0.8]`. It
needs MATLAB and the Paper 0 toolchain (`suslifepath-paper0`) checked out
next to this repository; `--no-matlab` runs without the DGP term. The
two-point decay model and its calibration sources are documented in the
script docstring.

## Notes
- In the code and `outputs/`, the geometric-mean aggregation carries the key
  `SSCI_risk`; it is `SSCI^geo` in the manuscript.
- `recompute_orbital_norm.py` / `recompute_terrestrial.py` are one-time migration
  scripts, **superseded** — the per-sub-category orbital normalisation is now native in
  `ssci.normalise_orbital` + `ssci_orchestrator.py`.
- Licence: MIT. Zenodo concept DOI (all versions): https://doi.org/10.5281/zenodo.20715157
