"""Builds supplementary.tex for the JCLEPRO revision from the released inputs:
the SusLifePath library export (seed v4: 57 unit processes and the four product
systems, exported from the openLCA database of the results), the mission descriptors, the atmospheric
module constants, the catalogue archetypes and the revision sensitivities.
Run from code/: python3 build_supplementary.py  (writes ../supplementary.tex)
"""
import json, zipfile, yaml
from pathlib import Path
import domain_atmospheric as atm
from paper1_catalogue_scale import ARCHETYPES
import re

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "supplementary.tex"

# openlca_build_mission_ps.py imports olca_ipc at module level (needs the openLCA
# environment), so the mapping and the AIT overhead are read from its source text.
_src = (HERE / "openlca_build_mission_ps.py").read_text(encoding="utf-8")
AIT_KWH_PER_KG = float(re.search(r"AIT_KWH_PER_KG\s*=\s*([0-9.]+)", _src).group(1))
MATERIAL_TO_PROCESS = dict(re.findall(r'"([A-Za-z0-9_]+)":\s*"([^"]+)"', _src))
AIT_MIN_KWH = float(re.search(r"AIT_MIN_KWH\s*=\s*([0-9.]+)", _src).group(1))

# blue-water consumption per material class, read from the script that writes it
# into the openLCA database (first match wins there, as here)
_wsrc = (HERE / "reground_water.py").read_text(encoding="utf-8")
_i = _wsrc.index("RULES = [")
WATER = dict(re.findall(r'\(\s*"([^"]+)",\s*([0-9.]+)\s*\)', _wsrc[_i:_wsrc.index("\n]", _i)]))
WATER_DEFAULT = float(re.search(r"^DEFAULT\s*=\s*([0-9.]+)", _wsrc, re.M).group(1))
WATER_ROWS = [  # (material class, key in RULES, reference unit, basis)
    ("Gold", "Gold", "kg", "Norgate and Lovel (2006): 252, embodied water"),
    ("Electronic-grade silicon", "Silicon, electronic", "kg", "Stolz et al. (2017): 3.12 evaporated on site"),
    ("Gallium arsenide wafer, GaAs solar panel", "Gallium arsenide", "kg, m$^2$", "order of magnitude, no published data"),
    ("Beryllium", "Beryllium", "kg", "order of magnitude, no published data"),
    ("Titanium alloy and machined titanium", "Titanium", "kg", "upper bound, no published consumption data"),
    ("Primary aluminium, ingot and machined part", "Aluminium", "kg", "IAI (2022): 0.014 direct; the smelter electricity is a separate input"),
    ("Copper cathode", "Copper", "kg", "ICA (2023): 0.057; Pe\\~na and Huijbregts (2014)"),
    ("Stainless steel", "Stainless", "kg", "Gerbens-Leenes et al. (2018): 0.077 for chromium-nickel steel"),
    ("Nickel alloys (Incoloy, Nichrome)", "Incoloy", "kg", "Mudd (2008): 0.107 for nickel"),
    ("Magnesium oxide", "Magnesium", "kg", "upper bound, no published data"),
    ("Li-ion battery, LiCoO$_2$", "Li-ion battery", "kg", "order of magnitude; lithium compounds alone 0.016 to 0.077 (Kelly et al., 2021)"),
    ("PCB and FR4 laminate", "PCB", "kg", "order of magnitude, no consumption data per kilogram"),
    ("CFRP prepreg and structure", "CFRP", "kg", "order of magnitude, no published consumption data"),
    ("Glass and glass-ceramic", "Zerodur", "kg", "upper bound; float glass 0.0058 (Gerbens-Leenes et al., 2018)"),
    ("Mylar film and MLI blanket", "Mylar", "kg, m$^2$", "upper bound for PET"),
    ("Polyimide and PTFE", "Kapton", "kg", "order of magnitude, no published data"),
    ("RP-1 kerosene", "RP-1", "kg", "Mekonnen et al. (2015): crude oil extraction and refining"),
    ("Liquid oxygen", "LOX", "kg", "Gerbens-Leenes et al. (2018): 0.0117"),
    ("MMH and N$_2$O$_4$", "MMH", "kg", "order of magnitude, no published data"),
    ("HTPB solid propellant", "HTPB", "kg", "order of magnitude, no published data"),
    ("Iodine", "Iodine", "kg", "order of magnitude, no published data"),
    ("Electricity, EU grid mix 2023", "Electricity", "kWh", "Mekonnen et al. (2015): 0.012 over the life cycle, Europe"),
]


def tex(s):
    return str(s).replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("#", r"\#")


def translate(name):
    for it, en in (("Produzione ", "Production of "), ("Assemblaggio ", "Assembly of "),
                   ("Deorbit e rientro ", "Deorbit and re-entry of "),
                   ("Operazioni Ground Station 1 anno", "Ground station operations, one year")):
        if name.startswith(it):
            return en + name[len(it):] if it.endswith(" ") else en
    return name


def processes():
    z = zipfile.ZipFile(HERE / "SusLifePath_seed_v4.zip")
    rows = []
    for n in z.namelist():
        if n.startswith("processes/") and n.endswith(".json"):
            j = json.loads(z.read(n))
            cat = j.get("category") or ""
            if cat.startswith("Missions/SSCI"):  # mission-level assemblies of the four product systems
                continue
            cat = cat.split("/")[-1]
            desc = (j.get("description") or "").replace("\n", " ").replace(" — ", ": ").replace("—", ", ").strip()
            rows.append((translate(j.get("name", "")), cat, desc))
    return sorted(rows, key=lambda r: (r[1], r[0]))


def missions():
    out = []
    for f in ("redpill_2p", "sentinel6", "envisat", "_reference_smallsat"):
        d = yaml.safe_load(open(HERE / "missions" / f"{f}.yaml"))
        out.append((f, d))
    return out


def main():
    L = []
    L.append(r"""\documentclass[11pt,a4paper]{article}
\usepackage[margin=2.2cm]{geometry}
\usepackage{booktabs,longtable,array,amsmath,siunitx}
\usepackage[hidelinks]{hyperref}
\setlength{\parskip}{4pt}\setlength{\parindent}{0pt}
\title{Supplementary material\\[4pt]\large Bridging Life Cycle Assessment and orbital sustainability assessment: a multi-domain composite indicator for the environmental assessment of space missions}
\author{Federico Toson}
\date{Revised version, October 2026}
\begin{document}\maketitle
All tables are generated by \texttt{code/build\_supplementary.py} from the released inputs (SusLifePath library export v4, mission descriptors, atmospheric module, catalogue archetypes), so that every value here is the one used in the computations.
""")
    # S1 archetypes
    L.append(r"""\section{Mission-class archetypes of the catalogue-scale sample}
Altitudes are drawn from the active-LEO distribution of the Celestrak snapshot; every other property comes from the archetype of the class drawn with the illustrative mix below. The mix is not the class mix of the catalogue.
\begin{table}[h]\centering\small
\begin{tabular}{lrrrrrrrll}\toprule
Class & Mix & Dry mass & $T_{op}$ & $T_{res}$ & Exposed area & Total area & Terrestrial intensity & Launcher & Demise \\
 & & kg & yr & yr & m$^2$ & m$^2$ & Pt per kg & chemistry & fraction \\\midrule""")
    for name, p, m, top, tres, ex, tot, pt, launcher, dem in ARCHETYPES:
        L.append(f"{name} & {p*100:.0f}\\% & {m:g} & {top:g} & {tres:g} & {ex:g} & {tot:g} & {pt:.4f} & {launcher} & {dem:.2f} \\\\")
    L.append(r"""\bottomrule\end{tabular}
\caption{Archetypes used in Section 4.5 (\texttt{paper1\_catalogue\_scale.py}). ``Mixed'' launcher chemistry means the kerosene-oxygen and the solid-booster stacks in equal shares. The terrestrial intensity is the EF 3.1 single score per kilogram of dry mass of the case study of the same class.}
\end{table}
""")
    # S2 inventories
    L.append(r"""\section{Material inventories of the case studies and of the reference mission}
Each product system is built from the material inventory below plus an assembly, integration and test electricity overhead of """ + f"{AIT_KWH_PER_KG:g}" + r""" kWh per kilogram of dry mass, and no less than """ + f"{AIT_MIN_KWH:g}" + r""" kWh (EU grid mix 2023). The floor applies to the PocketCube only, whose test campaign does not scale with its mass. The criticality factor $\chi_i$ is the terrestrial criticality score used by the in-orbit material criticality category. The last column is the unit process of the SusLifePath library that characterises the material; where that process is defined per square metre (the MLI blanket), one square metre per kilogram is assumed.
""")
    for f, d in missions():
        mb = d["mass_budget"]; g = d["geometry"]
        L.append(r"\subsection*{" + tex(d["id"]) + r"}" + f" Dry mass {mb['dry_mass_kg']:g} kg; exposed surface {g['exposed_surface_m2']:g} m$^2$, total surface {g['total_surface_m2']:g} m$^2$, cross-section {g['cross_section_m2']:g} m$^2$; altitude {d['orbit']['altitude_km']:g} km; operational lifetime {d['orbit']['operational_lifetime_yr']:g} yr, residual lifetime {d['orbit']['residual_lifetime_yr']:g} yr; launcher {tex(d['launch']['vehicle'])}, propellant share " + ", ".join(f"{tex(k)} {v:g} kg" for k, v in d["launch"]["propellant_share_kg"].items()) + f"; re-entry class {tex(d['reentry']['reentry_class'])}, expected demise fraction {d['reentry']['expected_demise_fraction']:g}.")
        L.append(r"\begin{center}\small\begin{tabular}{lrrl}\toprule Material & Mass (kg) & $\chi_i$ & Unit process \\\midrule")
        for m in d["materials"]:
            L.append(f"{tex(m['id'])} & {m['mass_kg']:g} & {m['criticality_factor']:g} & {tex(translate(MATERIAL_TO_PROCESS.get(m['id'], 'not mapped')))} \\\\")
        L.append(r"\bottomrule\end{tabular}\end{center}")
    L.append(r"""Sources of the inventories: the PocketCube inventory follows the J2050 RedPill architecture (Porcarelli et al., 2026; Vignato et al., 2025); the Sentinel-6 and ENVISAT inventories are derived from the public dry-mass budgets of the two platforms, split by subsystem class with typical material fractions of the bus families (Jason-3 and SPOT-Mk2 derivatives); the reference mission is notional. Where a material has no dedicated process (NiCd battery), the nearest process of the library is used as a proxy and is marked in the mapping.
""")
    # S3 process library
    lib = processes()
    L.append(r"""\section{The SusLifePath unit-process library (""" + f"{len(lib)}" + r""" processes)}
Foreground processes of the openLCA library used for the terrestrial domain, with the category and the basis stated in each process description (literature value or proxy). The library is released with the toolchain; processes not used by the three case studies belong to other missions of the same library.
\begin{small}\begin{longtable}{p{5.2cm}p{2.4cm}p{8.2cm}}\toprule Unit process & Category & Basis \\\midrule\endhead""")
    for name, cat, desc in lib:
        L.append(f"{tex(name)} & {tex(cat)} & {tex(desc)} \\\\")
    L.append(r"\bottomrule\end{longtable}\end{small}")
    # S3b blue water
    L.append(r"""\subsection*{Blue-water consumption}
Water enters the library as consumption (water evaporated or incorporated into the product), the quantity that AWARE characterises in EF~3.1, and not as water use or withdrawal. Every process carries its own electricity input, so the values below are direct; the water of power generation enters once, through the grid-mix process. Values are in m$^3$ per reference unit of the process and are the ones written into the database by \texttt{code/reground\_water.py}.
\begin{small}\begin{longtable}{p{4.6cm}rlp{7.2cm}}\toprule Material class & m$^3$ & per & Basis (published consumption, m$^3$ per unit) \\\midrule\endhead""")
    for label, key, unit, basis in WATER_ROWS:
        L.append(f"{label} & {float(WATER[key]):g} & {unit} & {basis} \\\\")
    L.append(r"""\bottomrule\end{longtable}\end{small}
Components modelled per item or per square metre (sensors, wheels, connectors, heaters, radiators) carry """ + f"{WATER_DEFAULT:g}" + r""" m$^3$ per unit, the assembly processes """ + f"{float(WATER['Assemblaggio']):g}" + r""" m$^3$ per item and the ground station """ + f"{float(WATER['Ground Station']):g}" + r""" m$^3$ per year; none of them enters the three case studies or the reference mission.

References for the water values: Gerbens-Leenes, P.W., Hoekstra, A.Y., Bosman, R., 2018. The blue and grey water footprint of construction materials: steel, cement and glass. Water Resources and Industry 19, 1--12, doi:10.1016/j.wri.2017.11.002. International Aluminium Institute (IAI), 2022. Life cycle inventory data and environmental metrics for the primary aluminium industry, 2019 data. London. International Copper Association (ICA), 2023. Copper environmental profile, global 2023. Kelly, J.C., Wang, M., Dai, Q., Winjobi, O., 2021. Energy, greenhouse gas, and water life cycle analysis of lithium carbonate and lithium hydroxide monohydrate from brine and ore resources and their use in lithium ion battery cathodes and lithium ion batteries. Resources, Conservation and Recycling 174, 105762, doi:10.1016/j.resconrec.2021.105762. Mekonnen, M.M., Gerbens-Leenes, P.W., Hoekstra, A.Y., 2015. The consumptive water footprint of electricity and heat: a global assessment. Environmental Science: Water Research \& Technology 1, 285--297, doi:10.1039/C5EW00026B. Mudd, G.M., 2008. Sustainability reporting and water resources: a preliminary assessment of embodied water and sustainable mining. Mine Water and the Environment 27, 136--144, doi:10.1007/s10230-008-0037-5. Norgate, T., Lovel, R., 2006. Sustainable water use in minerals and metal production. Proceedings of Water in Mining 2006, AusIMM, 331--340. Pe\~na, C.A., Huijbregts, M.A.J., 2014. The blue water footprint of primary copper production in northern Chile. Journal of Industrial Ecology 18, 49--58, doi:10.1111/jiec.12036. Stolz, P., Frischknecht, R., Heath, G., Komoto, K., Macknick, J., Sinha, P., Wade, A., 2017. Water footprint of European rooftop photovoltaic electricity based on regionalised life cycle inventories. IEA PVPS Task 12, report IEA-PVPS T12-11:2017.
""")
    # S4 atmospheric factors
    L.append(r"""\section{Atmospheric domain: emission factors and characterisation factors}
Emission factors per kilogram of propellant burnt above the tropopause (launch) and per kilogram of demised material (re-entry), and the species-level characterisation factor $\kappa_e \tau_e$, where $\kappa_e$ is a dimensionless effectiveness coefficient relative to NO$_x$ and $\tau_e$ the stratospheric residence time in years. Sources and the reasoning behind each value are given in the comments of \texttt{code/domain\_atmospheric.py} (Ross and Toohey, 2019; Maloney et al., 2022; Ryan et al., 2022; Ferreira et al., 2024; WMO, 2022).
\begin{center}\small\begin{tabular}{lrrrr}\toprule Species & $\kappa_e$ (--) & $\tau_e$ (yr) & $\kappa_e\tau_e$ (yr) \\\midrule""")
    for sp in atm.STRATOSPHERIC_KAPPA:
        L.append(f"{tex(sp)} & {atm.STRATOSPHERIC_KAPPA[sp]:g} & {atm.STRATOSPHERIC_TAU[sp]:g} & {atm.STRATOSPHERIC_KT[sp]:g} \\\\")
    L.append(r"\bottomrule\end{tabular}\end{center}")
    species = list(atm.STRATOSPHERIC_KAPPA)
    L.append(r"\begin{center}\small\begin{tabular}{l" + "r" * len(species) + r"}\toprule Propellant (launch), kg per kg & " + " & ".join(tex(s) for s in species) + r" \\\midrule")
    for prop, ef in atm.EMISSION_FACTORS_LAUNCH.items():
        L.append(f"{tex(prop)} & " + " & ".join(f"{ef.get(s, 0):g}" for s in species) + r" \\")
    L.append(r"\midrule Material (re-entry), kg per kg demised & " + " & ".join(tex(s) for s in species) + r" \\\midrule")
    for mat, ef in atm.EMISSION_FACTORS_REENTRY.items():
        L.append(f"{tex(mat)} & " + " & ".join(f"{ef.get(s, 0):g}" for s in species) + r" \\")
    L.append(r"\bottomrule\end{tabular}\end{center}")
    # S4b atmospheric flows and species decomposition
    L.append(r"""\subsection*{Emitted masses as elementary flows, and species decomposition}
Masses of each species emitted above the tropopause by the payload's share of the launch and by the demise of the platform at re-entry, computed from the propellant shares, the demise fractions and the factors above (the demising mass is split evenly across the three material families of the re-entry factors, a first-order heuristic). They are reported here as elementary flows, so that the inventory can be used without the characterisation. The last rows give the characterised contribution of each species to the raw atmospheric score ($\kappa_e \tau_e m_e$, in kg-years of NO$_x$ equivalent) from the pilot outputs.
""")
    cases = [(f, d) for f, d in missions() if not f.startswith("_")]
    L.append(r"\begin{center}\small\begin{tabular}{l" + "r" * len(cases) + r"}\toprule Emitted mass (kg) & " + " & ".join(tex(d["id"]) for f, d in cases) + r" \\\midrule")
    masses = {}
    for f, d in cases:
        m = {s: 0.0 for s in species}
        for prop, kg in d["launch"]["propellant_share_kg"].items():
            for s, fac in atm.EMISSION_FACTORS_LAUNCH.get(prop, {}).items():
                m[s] += fac * kg
        dem = d["mass_budget"]["dry_mass_kg"] * d["reentry"]["expected_demise_fraction"]
        per_fam = dem / max(1, len(atm.EMISSION_FACTORS_REENTRY))
        for fam, ef in atm.EMISSION_FACTORS_REENTRY.items():
            for s, fac in ef.items():
                m[s] += fac * per_fam
        masses[f] = m
    for s in species:
        L.append(f"{tex(s)} & " + " & ".join(f"{masses[f][s]:.4g}" for f, d in cases) + r" \\")
    L.append(r"\midrule Characterised contribution (kg yr NO$_x$ eq) & " + " & ".join("" for _ in cases) + r" \\\midrule")
    scores_sp = {f: json.load(open(HERE / "outputs" / f / "results.json"))["raw_scores"]["atmospheric"] for f, d in cases}
    for s in species:
        L.append(f"{tex(s)} & " + " & ".join(f"{scores_sp[f]['by_species'].get(s, 0):.4g}" for f, d in cases) + r" \\")
    L.append("Launch phase & " + " & ".join(f"{scores_sp[f]['by_phase']['launch']:.4g}" for f, d in cases) + r" \\")
    L.append("Re-entry phase & " + " & ".join(f"{scores_sp[f]['by_phase']['reentry']:.4g}" for f, d in cases) + r" \\")
    L.append("Raw atmospheric score & " + " & ".join(f"{scores_sp[f]['raw_score']:.4g}" for f, d in cases) + r" \\")
    L.append(r"\bottomrule\end{tabular}\end{center}")
    # S5 sensitivities
    r = json.load(open(HERE / "outputs" / "revision_sensitivities.json"))
    L.append(r"""\section{Sensitivities added in revision}
Computed by \texttt{code/paper1\_revision\_sensitivities.py} from the pilot outputs and the catalogue snapshot (\texttt{outputs/revision\_sensitivities.json}).
\begin{center}\small\begin{tabular}{lrrr}\toprule Congestion boundary, $T_{op}+T_{res}$ against $T_{op}$ & PocketCube & Sentinel-6 & ENVISAT \\\midrule""")
    a = r["A_cc_boundary"]
    L.append("Factor on $CC$ & " + " & ".join(f"{a[c]['ratio_ext_op']:.1f}" for c in ("redpill_2p", "sentinel6", "envisat")) + r" \\")
    L.append("Share of the extended count after operations & " + " & ".join(f"{a[c]['share_after_ops']*100:.0f}\\%" for c in ("redpill_2p", "sentinel6", "envisat")) + r" \\")
    L.append(r"\midrule Sample ($N=300$) & archetype $T_{res}$ & natural, uncontrolled & \\\midrule")
    s1, s2 = a["sample_archetype"], a["sample_natural_uncontrolled"]
    L.append(f"Median factor on $CC$ & {s1['median_ratio']:.1f} & {s2['median_ratio']:.1f} & \\\\")
    L.append(f"Share of summed $CC$ after operations & {s1['share_after_ops_total']*100:.0f}\\% & {s2['share_after_ops_total']*100:.0f}\\% & \\\\")
    L.append(f"Rank correlation of $CC$ with the operational count & {s1['spearman_rank_ext_vs_op']:.2f} & {s2['spearman_rank_ext_vs_op']:.2f} & \\\\")
    L.append(r"\bottomrule\end{tabular}\end{center}")
    b = r["B_same_constellation"]
    L.append(r"\begin{center}\small\begin{tabular}{lrrr}\toprule Shell (25 km half-width) & Objects & Dominant constellation & Share \\\midrule")
    for k, v in b.items():
        h, pref = k.split("_")
        L.append(f"{h} & {v['objects_in_shell']} & {pref.title()} & {v['own_share']*100:.0f}\\% \\\\")
    L.append(r"\bottomrule\end{tabular}\end{center}")
    c = r["C_terrestrial_uncertainty"]
    L.append(r"\begin{center}\small\begin{tabular}{lrrr}\toprule Terrestrial score scaled by & 0.1 & 1 & 10 \\\midrule")
    L.append("Share of the sample with terrestrial score below the composite & " + " & ".join(f"{c[k]['catalogue']['share_terrestrial_below']*100:.0f}\\%" for k in ("terrestrial_x0.1", "terrestrial_x1", "terrestrial_x10")) + r" \\")
    L.append("Median difference & " + " & ".join(f"{c[k]['catalogue']['median_difference']*100:.0f}\\%" for k in ("terrestrial_x0.1", "terrestrial_x1", "terrestrial_x10")) + r" \\")
    for case in ("redpill_2p", "sentinel6", "envisat"):
        L.append(f"$SSCI^{{lin}}$, {tex(case)} & " + " & ".join(f"{c[k][case]['lin']:.3g}" for k in ("terrestrial_x0.1", "terrestrial_x1", "terrestrial_x10")) + r" \\")
    L.append(r"\bottomrule\end{tabular}\end{center}")
    d = r["D_without_atmospheric"]; e = r["E_dgp_horizon_factor"]
    L.append(r"\begin{center}\small\begin{tabular}{lrrr}\toprule & PocketCube & Sentinel-6 & ENVISAT \\\midrule")
    L.append("Composite from terrestrial and orbital only ($SSCI^{lin}$, equal weights) & " + " & ".join(f"{d[c]['TO_lin']:.3g}" for c in ("redpill_2p", "sentinel6", "envisat")) + r" \\")
    L.append("Full composite & " + " & ".join(f"{d[c]['full_lin']:.3g}" for c in ("redpill_2p", "sentinel6", "envisat")) + r" \\")
    for H in (100, 200, 1000):
        L.append(f"Factor on $DGP$ for an accounting horizon $H={H}$ yr & " + " & ".join(f"{e[c][f'horizon_H{H}']:.2f}" for c in ("redpill_2p", "sentinel6", "envisat")) + r" \\")
    L.append("Factor on normalised $DGP$, mass-weighted proxy with fixed 200-yr horizon & " + " & ".join(f"{e[c]['mass_fixed200_over_presence_area']:.2f}" for c in ("redpill_2p", "sentinel6", "envisat")) + r" \\")
    fa = r["F_launch_allocation"]
    L.append(r"\midrule Launch allocation: capacity share (pilot) against full attribution of dedicated launches & & & \\\midrule")
    L.append("Launch factor under full attribution & " + " & ".join(f"{fa[c]['launch_factor']:.1f}" for c in ("redpill_2p", "sentinel6", "envisat")) + r" \\")
    L.append("Normalised atmospheric score, capacity share & " + " & ".join(f"{fa[c]['iA_capacity_share']:.3g}" for c in ("redpill_2p", "sentinel6", "envisat")) + r" \\")
    L.append("Normalised atmospheric score, full attribution & " + " & ".join(f"{fa[c]['iA_full_attribution']:.3g}" for c in ("redpill_2p", "sentinel6", "envisat")) + r" \\")
    L.append("$SSCI^{lin}$, full attribution & " + " & ".join(f"{fa[c]['ssci_lin_full_attribution']:.3g}" for c in ("redpill_2p", "sentinel6", "envisat")) + r" \\")
    L.append(f"\\midrule Rank correlation over the sample, full composite against terrestrial plus orbital & \\multicolumn{{3}}{{r}}{{{d['sample_spearman_full_vs_TO']:.3f}}} \\\\")
    L.append(f"Median atmospheric share of the composite over the sample & \\multicolumn{{3}}{{r}}{{{d['sample_median_share_atmospheric']*100:.1f}\\%}} \\\\")
    L.append(r"\bottomrule\end{tabular}\end{center}")
    gp = r.get("G_propellant_production")
    if gp:
        L.append(r"""\subsection*{Propellant production, climate-only estimate}
Cradle-to-gate climate factors per kilogram of propellant (low, mid, high): kerosene 0.31, 0.64, 0.90 (Jing et al., 2022, well-to-tank jet fuel); liquid oxygen 0.2, 1.2, 1.2 (Dominguez Calabuig et al., 2024, with an energy-based lower bound); liquid hydrogen 10, 12, 14 (Dominguez Calabuig et al., 2024; Elgowainy et al., 2024); APCP 1.5, 2.2, 3.0, MMH 20, 30, 40 and N$_2$O$_4$ 11, 14, 17 as order-of-magnitude estimates from relative ratios (Blondel-Canepari et al., 2025), since no public cradle-to-gate value exists for them. The added burden is converted to EF~3.1 single-score points with the pipeline's own """ + f"{gp['kg_co2e_per_climate_point']:.0f}" + r""" kg CO$_2$ eq per weighted climate point, and the terrestrial score is renormalised to the reference mission, which receives its own propellant production.
\begin{center}\small\begin{tabular}{lrrrr}\toprule & PocketCube & Sentinel-6 & ENVISAT & Reference \\\midrule""")
        cs = ("redpill_2p", "sentinel6", "envisat", "_reference_smallsat")
        for lvl in ("low", "mid", "high"):
            L.append(f"Added climate burden, {lvl} factors (kg CO$_2$ eq) & " + " & ".join(f"{gp[c]['added_climate_kg'][lvl]:.3g}" for c in cs) + r" \\")
        L.append("Terrestrial single score, pilot (Pt) & " + " & ".join(f"{gp[c]['single_score']:.3g}" for c in cs) + r" \\")
        for lvl in ("low", "mid", "high"):
            L.append(f"Relative increase of the single score, {lvl} & " + " & ".join(f"{gp[c]['relative_increase'][lvl]*100:.0f}\\%" for c in cs) + r" \\")
        for lvl in ("low", "mid", "high"):
            L.append(f"Factor on the normalised terrestrial score, {lvl} & " + " & ".join(f"{gp[c]['normalised_terrestrial_ratio'][lvl]:.2f}" for c in cs[:3]) + r" & 1 \\")
        L.append(r"\bottomrule\end{tabular}\end{center}")
    L.append(r"\end{document}")
    OUT.write_text("\n".join(L), encoding="utf-8")
    print("written", OUT)


if __name__ == "__main__":
    main()
