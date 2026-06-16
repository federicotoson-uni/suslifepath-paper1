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

## Notes
- In the code and `outputs/`, the geometric-mean aggregation carries the key
  `SSCI_risk`; it is `SSCI^geo` in the manuscript.
- `recompute_orbital_norm.py` / `recompute_terrestrial.py` are one-time migration
  scripts, **superseded** — the per-sub-category orbital normalisation is now native in
  `ssci.normalise_orbital` + `ssci_orchestrator.py`.
- Licence: MIT. Zenodo concept DOI (all versions): https://doi.org/10.5281/zenodo.20715157
