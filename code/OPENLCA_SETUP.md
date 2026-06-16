# OpenLCA setup guide — SSCI Paper 1 toolchain

**Author**: Federico Toson
**Last update**: 9 giugno 2026

This document explains how to set up the OpenLCA side of the SSCI toolchain.
The Python side (`domain_terrestrial.py`) needs an **OpenLCA server running
in IPC mode** to communicate with. Without this, the terrestrial domain
uses a mass-scaling placeholder and the pipeline still runs end-to-end (a
warning is printed).

---

## 0. Prerequisites

- **OpenLCA app**: free LCA software. You said you already have it installed
  on the Mac. If not, download from <https://www.openlca.org/download/>.
- **Python**: already in place (`python3` system).

---

## 1. Install the Python client (one-off, into the project venv)

macOS-with-Homebrew blocks `pip3` system-wide (PEP 668). The toolchain uses
a **dedicated virtualenv** inside `Paper1_SSCI/code/.venv/`.

The venv is already set up on this machine (created 9 giu 2026):

```
cd /Users/federico/Desktop/AEROSPACE/01_RICERCA/PAPER_SusLifePath_2026/Paper1_SSCI/code
source .venv/bin/activate
python -c "import olca_ipc, olca_schema; print('ok')"
```

If you need to rebuild from scratch (e.g. on a new machine):

```
cd /Users/federico/Desktop/AEROSPACE/01_RICERCA/PAPER_SusLifePath_2026/Paper1_SSCI/code
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

All pipeline commands below assume the venv is active. The `ssci_orchestrator`
can also be invoked without activating, via `.venv/bin/python ssci_orchestrator.py ...`.

---

## 2. Create the SusLifePath LCA archive in OpenLCA

This is a **new** archive built specifically for Paper 1, distinct from
`SpaceSysLab_2025-26_v2.zolca` (which is your SSL didactic archive).

In the OpenLCA GUI:

1. **File → New → Database** → name it `SusLifePathLCA_2026_v1`.
2. Choose **Empty database** (no Ecoinvent / PEFCR import yet).
3. Import the EF 3.1 method:
   - From a recent OpenLCA release the EF 3.1 LCIA method bundle is
     downloadable from the OpenLCA Nexus (<https://nexus.openlca.org/>).
     Look for "EF 3.1 (adapted)" or "PEF — EF 3.1".
   - Import via **File → Import → openLCA data** → select the `.zolca`
     pack of EF 3.1.
4. Add background flows: you need at minimum **Ecoinvent 3.10 cut-off**
   (or 3.11 if available) as the background database for raw-material and
   energy flows. Import into the same database.
5. Build the **RedPill 2P product system**:
   - **New → Product system** → name `redpill_2p_v1`.
   - For each lifecycle tier of the inventory (raw materials, components,
     integration, ground ops, launch terrestrial share, ops support, EOL),
     add the relevant unit processes from the BOM (when Vignato sends the
     numbers).
   - Save & calculate to verify the network solves.

The 7-tier structure is consistent with Section 3.5 of Paper 1.

---

## 3. Start the IPC server

In the OpenLCA GUI:

1. **Window → Preferences → Developer tools** → tick **"Show developer
   menu"** if not already visible.
2. **Tools → Developer Tools → IPC Server** → **Start server** at port
   `8080`.
   - The status bar shows "IPC Server running on port 8080".
   - Leave OpenLCA open in the background; the server runs as long as the
     app is open.

---

## 4. Test the Python ↔ OpenLCA connection

From this Paper 1 `code/` directory:

```
python3 -c "
import olca_ipc as ipc
client = ipc.Client(8080)
print('Connected. Reachable databases:', client.get_all('Database'))
"
```

If you see `Connected. Reachable databases: [...]` with at least
`SusLifePathLCA_2026_v1`, everything is wired. If you see a connection
refused error, check that the IPC server is started and on port 8080.

---

## 5. Implement the `domain_terrestrial.py` bridge

Once steps 1–4 are working, replace the placeholder body of
`compute_terrestrial_score(...)` in `domain_terrestrial.py` with the
production code (pseudocode already in the function docstring):

```python
import olca_ipc as ipc
import olca_schema as o

client = ipc.Client(8080)
ps = client.find(o.ProductSystem, mission.openlca.product_system_id)
setup = o.CalculationSetup(
    target=o.Ref(id=ps.id),
    impact_method=o.Ref(name="EF 3.1"),
    nw_set=o.Ref(name="EF 3.1 weighting"),
)
result = client.calculate(setup)
weighted_total = sum(r.amount for r in client.get_total_impacts(result))
return TerrestrialResult(
    raw_score=weighted_total,
    by_impact_category={r.indicator.name: r.amount
                        for r in client.get_total_impacts(result)},
    by_lifecycle_tier={...},   # optional: contribution tree by process
)
```

Then re-run `ssci_orchestrator.py` and the terrestrial domain will use
the real EF 3.1 weighted score from your archive.

---

## 6. When to do this

Realistically, this is **week 3–4** of the Paper 1 roadmap (after we have
the RedPill BOM from Vignato and the CC orbital module). For now the
toolchain runs end-to-end with placeholders, so we can iterate on the
other dominions in parallel.

Ping me when you want to do the OpenLCA setup pass — I can walk you
through the Nexus EF 3.1 import and the IPC server config in real-time.
