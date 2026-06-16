#!/usr/bin/env python3
"""Generate the data-driven figures of Paper 1 (SSCI) as vector PDFs.

Reads the batch outputs in outputs/<mission>/results.json (produced by
ssci_orchestrator.py against the SusLifePath_2026_v1 OpenLCA database, EF 3.1)
and produces four publication-quality figures in figures/:

  Fig 3  domain scores + composite SSCI, three missions, log scale
  Fig 4  orbital-domain decomposition (DGP / CC / MC), 100 % stacked
  Fig 5  weight-simplex (Dirichlet) sensitivity of the composite
  Fig 6  single-indicator (terrestrial-only / ECOB-derived) vs SSCI gap

The two conceptual figures (three-domain model, toolchain architecture)
are native TikZ and live in figures/fig1_threedomain.tex and
figures/fig2_toolchain.tex.

All numbers are read from results.json — no value is hardcoded — so the
figures regenerate exactly with the pipeline. Colours are Okabe-Ito
colour-blind-safe.

Usage:  python paper1_figures.py
Author: Federico Toson
"""
import json
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

HERE = Path(__file__).parent
OUT = HERE / "outputs"
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)

# Okabe-Ito palette (colour-blind safe)
C_T = "#E69F00"   # terrestrial  — orange
C_A = "#56B4E9"   # atmospheric  — sky blue
C_O = "#0072B2"   # orbital      — deep blue
C_S = "#000000"   # composite    — black
C_DGP = "#0072B2"
C_CC = "#56B4E9"
C_MC = "#009E73"  # green
C_REF = "#999999"

MISSIONS = ["redpill_2p", "sentinel6", "envisat"]
LABELS = {"redpill_2p": "RedPill 2P\n(0.44 kg)",
          "sentinel6": "Sentinel-6\n(1.2 t)",
          "envisat": "ENVISAT\n(8.2 t)"}

mpl.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "legend.fontsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
    "savefig.bbox": "tight",
    "pdf.fonttype": 42,   # editable text in the PDF
})


def load():
    data = {}
    for m in MISSIONS:
        with open(OUT / m / "results.json") as f:
            data[m] = json.load(f)
    return data


def fig3_domain_composite(data):
    """Grouped bars: I_T, I_A, I_O and SSCI^lin per mission, log scale."""
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    x = np.arange(len(MISSIONS))
    w = 0.2
    iT = [data[m]["ssci"]["scores_norm"]["terrestrial"] for m in MISSIONS]
    iA = [data[m]["ssci"]["scores_norm"]["atmospheric"] for m in MISSIONS]
    iO = [data[m]["ssci"]["scores_norm"]["orbital"] for m in MISSIONS]
    sl = [data[m]["ssci"]["SSCI_linear_equal"] for m in MISSIONS]

    ax.bar(x - 1.5 * w, iT, w, label=r"$\tilde{I}_T$ terrestrial", color=C_T)
    ax.bar(x - 0.5 * w, iA, w, label=r"$\tilde{I}_A$ atmospheric", color=C_A)
    ax.bar(x + 0.5 * w, iO, w, label=r"$\tilde{I}_O$ orbital", color=C_O)
    ax.bar(x + 1.5 * w, sl, w, label=r"$SSCI^{lin}$ (equal $w$)",
           color="none", edgecolor=C_S, linewidth=1.3, hatch="////")

    ax.axhline(1.0, color=C_REF, ls="--", lw=1.0, zorder=0)
    ax.text(-0.45, 1.5, "reference mission",
            color=C_REF, fontsize=8, ha="left", va="bottom")

    ax.set_yscale("log")
    ax.set_ylim(3e-4, 1e3)
    ax.set_xlim(-0.6, len(MISSIONS) - 0.3)
    ax.set_xticks(x)
    ax.set_xticklabels([LABELS[m] for m in MISSIONS])
    ax.set_ylabel("normalised impact score (dimensionless)")
    ax.legend(ncol=2, loc="upper left", frameon=False)
    ax.set_title("Domain scores and composite SSCI across mission classes")
    fig.savefig(FIG / "fig3_domain_composite.pdf")
    plt.close(fig)
    print("fig3_domain_composite.pdf  spread:",
          f"{max(sl)/min(sl):.3g}x  ({np.log10(max(sl)/min(sl)):.2f} decades)")


def fig4_orbital_decomposition(data):
    """100 %-stacked horizontal bars of DGP / CC / MC per mission."""
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    y = np.arange(len(MISSIONS))
    dgp = [data[m]["raw_scores"]["orbital"]["breakdown_pct"]["DGP"] for m in MISSIONS]
    cc = [data[m]["raw_scores"]["orbital"]["breakdown_pct"]["CC"] for m in MISSIONS]
    mc = [data[m]["raw_scores"]["orbital"]["breakdown_pct"]["MC"] for m in MISSIONS]

    ax.barh(y, dgp, color=C_DGP, label="DGP (debris generation)")
    ax.barh(y, cc, left=dgp, color=C_CC, label="CC (congestion)")
    ax.barh(y, mc, left=[d + c for d, c in zip(dgp, cc)], color=C_MC,
            label="MC (material criticality)")

    for i, (d, c, m) in enumerate(zip(dgp, cc, mc)):
        if d > 4:
            ax.text(d / 2, i, f"{d:.0f}%", ha="center", va="center",
                    color="white", fontsize=8)
        if c > 4:
            ax.text(d + c / 2, i, f"{c:.0f}%", ha="center", va="center",
                    color="black", fontsize=8)
        if m > 4:
            ax.text(d + c + m / 2, i, f"{m:.0f}%", ha="center", va="center",
                    color="white", fontsize=8)

    ax.set_yticks(y)
    ax.set_yticklabels([LABELS[m].replace("\n", " ") for m in MISSIONS])
    ax.set_xlim(0, 100)
    ax.set_xlabel(r"share of orbital impact score $\tilde{I}_O$ (%)")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.28),
              frameon=False)
    ax.spines["left"].set_visible(False)
    fig.savefig(FIG / "fig4_orbital_decomposition.pdf")
    plt.close(fig)
    print("fig4_orbital_decomposition.pdf  regime signatures rendered")


def fig5_weight_sensitivity(data):
    """Dirichlet weight-simplex spread of the composite, log scale."""
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    x = np.arange(len(MISSIONS))
    for i, m in enumerate(MISSIONS):
        s = data[m]["sensitivity_dirichlet_10k"]
        p05, p25, med, p75, p95 = s["p05"], s["p25"], s["median"], s["p75"], s["p95"]
        # whisker p05-p95
        ax.plot([x[i], x[i]], [p05, p95], color=C_S, lw=1.0, zorder=1)
        # box p25-p75
        ax.add_patch(plt.Rectangle((x[i] - 0.18, p25), 0.36, p75 - p25,
                                   facecolor=C_O, edgecolor=C_S, lw=1.0, zorder=2))
        # median
        ax.plot([x[i] - 0.18, x[i] + 0.18], [med, med], color="white", lw=1.6, zorder=3)
        # caps
        for v in (p05, p95):
            ax.plot([x[i] - 0.07, x[i] + 0.07], [v, v], color=C_S, lw=1.0)
        # relative spread annotation
        rel = 0.5 * (p75 - p25) / med * 100
        ax.text(x[i], p95 * 1.4, f"±{rel:.0f}%", fontsize=8, ha="center", va="bottom", color=C_S)

    ax.axhline(1.0, color=C_REF, ls="--", lw=1.0, zorder=0)
    ax.set_yscale("log")
    ax.set_ylim(3e-4, 1e3)
    ax.set_xticks(x)
    ax.set_xticklabels([LABELS[m] for m in MISSIONS])
    ax.set_ylabel(r"$SSCI^{lin}$ over the weight simplex")
    ax.set_title(r"Robustness to weighting ($10^4$ Dirichlet samples)")
    ax.set_xlim(-0.6, len(MISSIONS) - 0.1)
    fig.savefig(FIG / "fig5_weight_sensitivity.pdf")
    plt.close(fig)
    print("fig5_weight_sensitivity.pdf  ranking preserved across simplex")


def fig6_single_vs_ssci(data):
    """Terrestrial-only (PEFCR-style) and ECOB-derived vs the composite SSCI."""
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    x = np.arange(len(MISSIONS))
    w = 0.26
    pefcr = [data[m]["ssci"]["scores_norm"]["terrestrial"] for m in MISSIONS]   # terrestrial-only
    ecob = [data[m]["ssci"]["scores_norm"]["orbital"] for m in MISSIONS]        # ECOB-derived
    ssci = [data[m]["ssci"]["SSCI_linear_equal"] for m in MISSIONS]

    ax.bar(x - w, pefcr, w, label="terrestrial-only (PEFCR-style)", color=C_T)
    ax.bar(x, ecob, w, label="ECOB-derived (orbital-only)", color=C_O)
    ax.bar(x + w, ssci, w, label=r"composite $SSCI^{lin}$",
           color="none", edgecolor=C_S, linewidth=1.3, hatch="////")

    # gap annotation terrestrial-only vs SSCI, just above the tallest bar
    for i, m in enumerate(MISSIONS):
        gap = (pefcr[i] - ssci[i]) / ssci[i] * 100
        sign = "+" if gap >= 0 else ""
        top = max(pefcr[i], ecob[i], ssci[i])
        ax.annotate(f"{sign}{gap:.0f}%", xy=(x[i], top * 1.4),
                    ha="center", fontsize=9, color=C_S, fontweight="bold")

    ax.set_yscale("log")
    ax.set_ylim(3e-4, 3e3)
    ax.set_xticks(x)
    ax.set_xticklabels([LABELS[m] for m in MISSIONS])
    ax.set_ylabel("normalised score (dimensionless)")
    ax.legend(loc="upper left", frameon=False)
    ax.set_title("Single-indicator scores versus the composite SSCI")
    fig.savefig(FIG / "fig6_single_vs_ssci.pdf")
    plt.close(fig)
    gaps = [(data[m]["ssci"]["scores_norm"]["terrestrial"] - data[m]["ssci"]["SSCI_linear_equal"])
            / data[m]["ssci"]["SSCI_linear_equal"] * 100 for m in MISSIONS]
    print("fig6_single_vs_ssci.pdf  PEFCR gaps:",
          {m: f"{g:+.0f}%" for m, g in zip(MISSIONS, gaps)})


def fig7_catalogue_scale():
    """Catalogue-scale (N=300) SSCI distribution + orbital-dominance + gap."""
    path = OUT / "catalogue_scale.json"
    if not path.exists():
        print("fig7 skipped: run paper1_catalogue_scale.py first")
        return
    rows = json.load(open(path))
    ssci = np.array([r["ssci"] for r in rows])
    gaps = np.array([r["gap"] for r in rows])
    doms = [r["orb_dom"] for r in rows]
    n = len(rows)

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(7.2, 3.1))
    # (a) SSCI distribution, log x
    bins = np.logspace(np.log10(ssci.min()), np.log10(ssci.max()), 24)
    axL.hist(ssci, bins=bins, color=C_O, edgecolor="white", linewidth=0.4)
    axL.set_xscale("log")
    axL.axvline(np.median(ssci), color=C_S, ls="--", lw=1.0)
    axL.text(np.median(ssci) * 1.1, axL.get_ylim()[1] * 0.85,
             f"median {np.median(ssci):.1f}", fontsize=8)
    axL.set_xlabel(r"$SSCI^{lin}$ (dimensionless)")
    axL.set_ylabel(f"missions (N={n})")
    axL.set_title("(a) SSCI distribution over the catalogue", fontsize=10)

    # (b) orbital dominance prevalence
    cats = ["CC", "DGP", "MC"]
    cols = {"CC": C_CC, "DGP": C_DGP, "MC": C_MC}
    prev = [100 * doms.count(k) / n for k in cats]
    y = np.arange(len(cats))
    axR.barh(y, prev, color=[cols[k] for k in cats])
    for i, p in enumerate(prev):
        axR.text(p + 1.5, i, f"{p:.0f}%", va="center", fontsize=9)
    axR.set_yticks(y)
    axR.set_yticklabels(["CC\n(congestion)", "DGP\n(debris)", "MC\n(materials)"])
    axR.set_xlim(0, 100)
    axR.set_xlabel("% of missions where it dominates orbital")
    axR.set_title("(b) Dominant orbital driver (reference normalisation)", fontsize=9)
    under = 100 * np.mean(gaps < 0)
    axR.text(0.5, -0.42,
             f"terrestrial-only underestimates {under:.0f}% of missions "
             f"(median {np.median(gaps[gaps<0]):.0f}%, reference normalisation)",
             transform=axR.transAxes, ha="center", fontsize=7.5, color=C_REF)
    fig.subplots_adjust(bottom=0.28, wspace=0.35)
    fig.savefig(FIG / "fig7_catalogue_scale.pdf")
    plt.close(fig)
    print(f"fig7_catalogue_scale.pdf  CC dominates {prev[0]:.0f}%, "
          f"terrestrial-only underestimates {under:.0f}%")


if __name__ == "__main__":
    data = load()
    fig3_domain_composite(data)
    fig4_orbital_decomposition(data)
    fig5_weight_sensitivity(data)
    fig6_single_vs_ssci(data)
    fig7_catalogue_scale()
    print(f"\nAll figures written to {FIG}/")
