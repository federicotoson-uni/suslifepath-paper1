#!/usr/bin/env python3
r"""Export the EF 3.1 WEIGHTED single-score breakdown per impact category for
the case-study and reference product systems (review round 2, R3-F2).

The pipeline stores only the weighted total (raw_score) and the *characterised*
per-category amounts; this script pulls the *weighted* per-category breakdown
via get_weighted_impacts(), so the terrestrial single score and the
"climate-led" statement of Section 4.2 are verifiable from a committed CSV
without rebuilding the OpenLCA database. Requires the OpenLCA IPC server
(port 8080). Writes outputs/terrestrial_weighted.csv.
Usage: .venv/bin/python export_terrestrial_weighted.py
Author: Federico Toson.
"""
import csv
from pathlib import Path
import olca_ipc as ipc
import olca_schema as o
from mission_descriptor import Mission

HERE = Path(__file__).parent
MISS = HERE / "missions"
FILES = {"reference": "_reference_smallsat.yaml", "redpill_2p": "redpill_2p.yaml",
         "sentinel6": "sentinel6.yaml", "envisat": "envisat.yaml"}

client = ipc.Client(8080)
systems = {p.name: p for p in client.get_descriptors(o.ProductSystem)}
ef = next(m for m in client.get_descriptors(o.ImpactMethod) if "EF 3.1" in (m.name or ""))
nw = (client.get(o.ImpactMethod, ef.id).nw_sets or [None])[0]

data = {}
for label, f in FILES.items():
    m = Mission.from_yaml(MISS / f)
    ps = getattr(getattr(m, "openlca", None), "product_system_id", None)
    if not ps or ps not in systems:
        print(f"{label:11} product system '{ps}' not found — skipped")
        continue
    setup = o.CalculationSetup(
        target=o.Ref(ref_type=o.RefType.ProductSystem, id=systems[ps].id),
        impact_method=o.Ref(ref_type=o.RefType.ImpactMethod, id=ef.id),
        nw_set=o.Ref(id=nw.id, name=nw.name) if nw else None)
    r = client.calculate(setup); r.wait_until_ready()
    w = {wi.impact_category.name: wi.amount for wi in r.get_weighted_impacts()
         if wi.impact_category}
    r.dispose()
    data[label] = w
    tot = sum(w.values())
    top = sorted(w.items(), key=lambda x: -x[1])[:4]
    print(f"{label:11} total={tot:.4g} Pt | "
          + ", ".join(f"{k} {100*v/tot:.0f}%" for k, v in top))

cats = sorted({c for w in data.values() for c in w})
out = HERE / "outputs" / "terrestrial_weighted.csv"
with open(out, "w", newline="") as fp:
    wr = csv.writer(fp)
    wr.writerow(["impact_category_Pt"] + list(data))
    for c in cats:
        wr.writerow([c] + [f"{data[m].get(c, 0):.6g}" for m in data])
    wr.writerow(["TOTAL_Pt"] + [f"{sum(data[m].values()):.6g}" for m in data])
print(f"\nwritten {out}")
