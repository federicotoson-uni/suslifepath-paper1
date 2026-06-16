#!/usr/bin/env python3
"""Build an OpenLCA product system for a mission YAML (SSCI Paper 1).

Reads the `materials:` section of the mission descriptor, maps each material
class onto a provider process of the SusLifePath seed v3 library, adds an
AIT electricity overhead (10 kWh/kg dry), creates the manufacturing process
and the auto-linked product system named `openlca.product_system_id`.

Usage:  .venv/bin/python openlca_build_mission_ps.py missions/sentinel6.yaml [...]
Requires the OpenLCA IPC server on :8080 (JSON-RPC, gRPC OFF).
"""
import sys, uuid
import yaml
import olca_ipc as ipc
import olca_schema as o

AIT_KWH_PER_KG = 10.0

# material class (yaml) -> provider process name (seed v3 / IPC-built)
PROVIDER_FOR_CLASS = {
    "aluminium_6061":      "Produzione Aluminium 6061-T6 structure, machined",
    "titanium_alloys":     "Produzione Titanium alloy Ti-6Al-4V",
    "CFRP_composites":     "Produzione CFRP composite structure",
    "PCB_FR4":             "Produzione FR4 substrate, rad-hard",
    "ASIC_electronics":    "Produzione PCB OBC space-grade 10x15cm",
    "misc_electronics":    "Produzione PCB OBC space-grade 10x15cm",
    "lithium_battery":     "Produzione Li-ion battery 100Wh, rad-hard",
    "NiCd_battery":        "Produzione Li-ion battery 100Wh, rad-hard",  # proxy: NiCd not in library
    "copper_wiring":       "Produzione Copper cathode, primary",
    "silicon_solar_cells": "Produzione Silicon, electronic grade monocrystalline",
    "GaAs_payload":        "Produzione Gallium arsenide wafer",
    "steel_fasteners":     "Produzione Stainless steel 17-4PH",
    "misc_thermal":        "Produzione Mylar MLI blanket",
    "brass_spacers":       "Produzione Brass CuZn37, machined",
    "glass_ITO":           "Produzione ITO-coated glass (double pane)",
    "polymer_PEEK":        "Produzione PEEK polymer, machined part",
}

def main(paths):
    client = ipc.Client(8080)
    fprops = {fp.name: fp for fp in client.get_descriptors(o.FlowProperty)}
    unit_map = {}
    for ug in client.get_descriptors(o.UnitGroup):
        g = client.get(o.UnitGroup, ug.id)
        for u in (g.units or []):
            unit_map.setdefault(u.name, o.Ref(id=u.id, name=u.name, ref_type=o.RefType.Unit))
    def fpref(n):
        fp = fprops[n]
        return o.Ref(id=fp.id, name=fp.name, ref_type=o.RefType.FlowProperty)
    procs = {p.name: p for p in client.get_descriptors(o.Process)}
    systems = {p.name for p in client.get_descriptors(o.ProductSystem)}
    def ref_flow(pname):
        full = client.get(o.Process, procs[pname].id)
        for e in full.exchanges:
            if e.is_quantitative_reference:
                return e.flow

    for path in paths:
        m = yaml.safe_load(open(path))
        ps_name = m["openlca"]["product_system_id"]
        if ps_name in systems:
            print(f"[{m['id']}] product system '{ps_name}' already exists — skip")
            continue
        dry = float(m["mass_budget"]["dry_mass_kg"])
        out = o.Flow(id=str(uuid.uuid4()), name=f"{m['id']} spacecraft, assembled",
                     flow_type=o.FlowType.PRODUCT_FLOW,
                     flow_properties=[o.FlowPropertyFactor(
                         flow_property=fpref("Number"), conversion_factor=1.0,
                         is_ref_flow_property=True)])
        client.put(out)
        exch = [o.Exchange(amount=1.0, is_input=False, internal_id=1,
                flow=o.Ref(id=out.id, name=out.name, ref_type=o.RefType.Flow),
                unit=unit_map["Item(s)"], flow_property=fpref("Number"),
                is_quantitative_reference=True)]
        iid = 1
        for mat in m.get("materials", []):
            cls, kg = mat["id"], float(mat["mass_kg"])
            pname = PROVIDER_FOR_CLASS.get(cls)
            if not pname or pname not in procs:
                print(f"  ! no provider for class '{cls}' ({kg} kg) — SKIPPED, add to library")
                continue
            iid += 1
            fl = ref_flow(pname)
            exch.append(o.Exchange(amount=kg, is_input=True, internal_id=iid,
                flow=o.Ref(id=fl.id, name=fl.name, ref_type=o.RefType.Flow),
                unit=unit_map["kg"], flow_property=fpref("Mass"),
                default_provider=o.Ref(id=procs[pname].id, name=pname,
                                       ref_type=o.RefType.Process),
                description=f"class {cls}"))
        iid += 1
        elname = "Produzione Electricity, EU grid mix 2023"
        elfl = ref_flow(elname)
        exch.append(o.Exchange(amount=AIT_KWH_PER_KG * dry, is_input=True, internal_id=iid,
            flow=o.Ref(id=elfl.id, name=elfl.name, ref_type=o.RefType.Flow),
            unit=unit_map["kWh"], flow_property=fpref("Energy"),
            default_provider=o.Ref(id=procs[elname].id, name=elname,
                                   ref_type=o.RefType.Process),
            description=f"AIT {AIT_KWH_PER_KG} kWh/kg, first-order"))
        proc = o.Process(id=str(uuid.uuid4()),
            name=f"{m['id']} manufacturing (AIT included)",
            description=(f"Built via openlca_build_mission_ps.py from {path} materials "
                         f"section ({dry} kg dry). AIT {AIT_KWH_PER_KG} kWh/kg first-order. "
                         "Launch/flight emissions out of scope (SSCI atmospheric domain)."),
            process_type=o.ProcessType.UNIT_PROCESS, exchanges=exch, last_internal_id=iid)
        client.put(proc)
        cfg = o.LinkingConfig(prefer_unit_processes=True,
                              provider_linking=o.ProviderLinking.PREFER_DEFAULTS)
        ps = client.create_product_system(proc, cfg)
        full = client.get(o.ProductSystem, ps.id)
        full.name = ps_name
        client.put(full)
        print(f"[{m['id']}] product system '{ps_name}' created ({len(exch)-2} material inputs + AIT)")

if __name__ == "__main__":
    main(sys.argv[1:])
