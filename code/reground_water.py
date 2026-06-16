#!/usr/bin/env python3
r"""Re-anchor the blue-water consumption of the SusLifePath process library
to literature-grounded, material-class intensities (ISSUES R1).

Problem (hard-review iteration 1, verified 15/06): the seed library's water
input flows were fabricated round numbers (Gold 50,000 m3/kg, Silicon
250 m3/kg, a 10x15 cm PCB 200 m3 for a 0.5 reference, ...), input-only with
no return. Under EF 3.1 (AWARE) this made Water use ~87% of the terrestrial
weighted single score, masking every other category.

Fix: assign each process a consumptive (blue) water intensity by material
class, from published water-footprint / LCA ranges. Values are
order-of-magnitude anchors (the inventory is purpose-built, not ecoinvent);
they are to be validated by the author and are reported with a data-quality
caveat in the manuscript. Units follow each process's own reference unit
(m3 per kg, per m2, per item, or per kWh).

Sources for the class intensities (blue/consumptive water, order of
magnitude): primary metals and semiconductors from water-footprint
literature (e.g. precious metals very high per kg but used at gram scale;
electronic-grade Si a few m3/kg; primary Al ~1.5 m3/kg); polymers, optics
and propellants low; thermoelectric/hydro grid water ~1e-3 m3/kWh.

Usage:  .venv/bin/python reground_water.py [--apply]
Without --apply it prints the planned old->new (dry run). Author: F. Toson.
"""
import sys
import olca_ipc as ipc
import olca_schema as o

APPLY = "--apply" in sys.argv

# (substring, m3 per reference unit) — first match wins; ordered specific->generic
RULES = [
    ("Gold",                     200.0),   # precious metal, very high per kg, gram-scale use
    ("Gallium arsenide",          15.0),   # compound semiconductor
    ("GaAs",                       15.0),
    ("Beryllium",                 20.0),   # specialty metal
    ("Silicon, electronic",        8.0),   # ultrapure-water intensive
    ("Titanium",                   3.0),
    ("Copper",                     0.3),
    ("Aluminium",                  1.5),
    ("Aluminum",                   1.5),
    ("Stainless",                  0.12),
    ("Incoloy",                    0.15),
    ("Nichrome",                   0.15),
    ("Magnesium",                  0.5),
    ("Lithium cobalt",             0.5),
    ("Li-ion battery",            0.5),
    ("PCB",                        0.3),
    ("FR4",                        0.3),
    ("CFRP",                       0.5),
    ("Zerodur",                    0.4),
    ("Borosilicate",               0.4),
    ("Fused silica",               0.4),
    ("coverglass",                 0.4),
    ("Kapton",                     0.3),
    ("PTFE",                       0.3),
    ("Mylar",                      0.3),
    ("Polyimide",                  0.3),
    ("RP-1",                       0.05),
    ("kerosene",                   0.05),
    ("LOX",                        0.01),
    ("liquid oxygen",              0.01),
    ("MMH",                        0.2),
    ("hypergolic",                 0.2),
    ("HTPB",                       0.1),
    ("Iodine",                     0.5),
    ("iodine",                     0.5),
    ("Solar panel",                2.0),    # per m2
    ("Electricity",                0.002),  # per kWh (thermoelectric/hydro consumptive)
    ("Ground Station",            50.0),    # operational facility, 1 yr
    ("Assemblaggio",               2.0),    # assembly finishing water, per item
    ("Radiator",                   0.3),    # per m2
    ("Flexible heater",            0.1),    # per m2
]
DEFAULT = 0.3   # per-item components (sensors, wheels, thrusters, connectors, ...)


def target_for(name: str) -> float:
    for key, val in RULES:
        if key.lower() in name.lower():
            return val
    return DEFAULT


def main():
    c = ipc.Client(8080)
    procs = {p.name: p for p in c.get_descriptors(o.Process)}
    changed, rows = 0, []
    for name, d in sorted(procs.items()):
        full = c.get(o.Process, d.id)
        wex = [e for e in full.exchanges
               if e.is_input and "water" in (e.flow.name or "").lower()]
        if not wex:
            continue
        tgt = target_for(name)
        e = wex[0]
        old = e.amount
        rows.append((old, tgt, name))
        if APPLY and abs(old - tgt) > 1e-12:
            e.amount = tgt
            c.put(full)
            changed += 1
    rows.sort(key=lambda r: -r[0])
    print(f"{'old':>10} {'new':>8}  process")
    for old, tgt, name in rows:
        flag = "  <==" if old / max(tgt, 1e-9) > 5 else ""
        print(f"{old:10.4g} {tgt:8.3g}  {name[:50]:50s}{flag}")
    print(f"\n{'APPLIED' if APPLY else 'DRY RUN'} — {len(rows)} processes with water; "
          f"{changed} updated." if APPLY else
          f"\nDRY RUN — {len(rows)} processes with water input would be updated. "
          f"Re-run with --apply to write.")


if __name__ == "__main__":
    main()
