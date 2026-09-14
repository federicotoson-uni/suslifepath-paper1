"""Figure for IAC-26 A6: where the orbital burden sits by altitude, and how the
answer moves with the horizon after the end of operations.

Reads the nominal sweep output written by Paper1_SSCI/code/iac_a6_disposal_sweep.py
(scale 1.0) and rescales the uncontrolled burden to a finite horizon H exactly:
DGP is linear in T_tot = T_op + T_res, so u_H = u * (T_op + min(T_res, H)) / (T_op + T_res).
No MATLAB run is needed. Prints the checks against Table 1 of the paper.

Usage: python3 make_fig_altitude.py   (from any directory)
"""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
JSON = HERE.parent.parent / "outputs" / "iac_a6_sweep_scale1.0.json"

T_OP = {"cubesat": 3.0, "smallsat": 5.0, "medium": 6.0, "large": 10.0}
HORIZONS = [100, 200, 500, 1000]

# palette (dataviz reference instance, validated 7/9/2026 on white):
# blue ordinal ramp for the horizons, orange and aqua for the two rules
C_H = {100: "#86b6ef", 200: "#3987e5", 500: "#1c5cab", 1000: "#0d366b"}
C_R25, C_R5 = "#eb6834", "#1baf7a"
INK, MUTED, GRID, AXIS = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7"

d = json.load(open(JSON))
h = np.array(d["_meta"]["altitudini"])
arch = d["_meta"]["archetipi"]
top = np.array([T_OP[a] for a in arch])
u = np.array(d["uncontrolled"]["dgp"])
tres = np.array(d["uncontrolled"]["tres"])
r25 = np.array(d["rule25"]["dgp"])
r5 = np.array(d["rule5"]["dgp"])

def at_horizon(H):
    return u * (top + np.minimum(tres, H)) / (top + tres)

def share_above(v, grid):
    tot = v.sum()
    return np.array([v[h > x].sum() / tot for x in grid])

grid = np.arange(300, 2001, 2.0)
series = {H: at_horizon(H) for H in HORIZONS}

# ---- checks against the paper's Table 1 ---------------------------------
print("horizon  removed25  removed5vs25  share>800 unc  share>800 r25")
for H in HORIZONS:
    uH = series[H]
    rem25 = 1 - r25.sum() / uH.sum()
    tight = (r25.sum() - r5.sum()) / uH.sum()
    print(f"{H:>7d}  {100*rem25:8.1f}%  {100*tight:11.1f}%  {100*uH[h>800].sum()/uH.sum():12.1f}%  {100*r25[h>800].sum()/r25.sum():12.1f}%")
print(f"share>800 under 5-year rule: {100*r5[h>800].sum()/r5.sum():.1f}%")

# ---- figure --------------------------------------------------------------
plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 8, "axes.labelsize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.6, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.labelcolor": INK, "text.color": INK,
    "pdf.fonttype": 42,
})
fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(3.35, 5.3), constrained_layout=True)

for ax in (ax_a, ax_b):
    ax.grid(True, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.set_xlim(300, 1600)
    ax.tick_params(length=2.5, width=0.5)
print("missions above 1600 km:", int((h > 1600).sum()))

# (a) share of the summed burden above altitude h
for H in HORIZONS:
    ax_a.plot(grid, 100 * share_above(series[H], grid), color=C_H[H], lw=1.4,
              label=f"uncontrolled, {H}-yr horizon")
ax_a.plot(grid, 100 * share_above(r25, grid), color=C_R25, lw=1.4, ls="--", label="25-year rule")
ax_a.plot(grid, 100 * share_above(r5, grid), color=C_R5, lw=1.4, ls=(0, (1.2, 1.2)), label="5-year rule")
ax_a.axvline(800, color=AXIS, lw=0.6, ls=":")
ax_a.set_ylim(0, 100)
ax_a.set_ylabel("share of summed DGP above $h$ (%)")
ax_a.legend(frameon=False, loc="upper right", handlelength=2.2, borderaxespad=0.2)
ax_a.text(0.02, 0.96, "(a)", transform=ax_a.transAxes, va="top", fontweight="bold")
# direct labels at 800 km for the two extremes and the rule
for H, dy in ((1000, 3.0), (100, 2.0)):
    y = 100 * share_above(series[H], np.array([800.0]))[0]
    ax_a.annotate(f"{y:.0f}%", (800, y), xytext=(4, dy), textcoords="offset points",
                  fontsize=7, color=INK, va="bottom")
y = 100 * share_above(r25, np.array([800.0]))[0]
ax_a.annotate(f"{y:.0f}%", (800, y), xytext=(4, 2), textcoords="offset points", fontsize=7,
              color=INK, va="bottom")

# (b) per-mission DGP against altitude under the three rules (full horizon)
order = np.argsort(h)
# hollow ring for the uncontrolled case so that coincident points (below 500 km
# the three rules give the same value) still show all three marks
ax_b.scatter(h, u, s=22, facecolors="none", edgecolors=C_H[1000], lw=0.7,
             label="uncontrolled (1000 yr)")
ax_b.scatter(h, r25, s=9, color=C_R25, lw=0, label="25-year rule")
ax_b.scatter(h, r5, s=3.5, color=C_R5, lw=0, label="5-year rule")
ax_b.set_yscale("log")
ax_b.set_ylim(1e-5, 3e3)
for x, lab, ha in ((497, "5 yr ", "right"), (610, " 25 yr", "left"), (869, "cap", "center")):
    ax_b.axvline(x, color=AXIS, lw=0.6, ls=":")
    ax_b.text(x, 1.4e3, lab, fontsize=6.5, color=MUTED, ha=ha, va="bottom")
ax_b.set_xlabel("operating altitude $h$ (km)")
ax_b.set_ylabel("DGP per mission (reference = 1)")
ax_b.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3,
            markerscale=1.6, columnspacing=1.0, handletextpad=0.3)
ax_b.text(0.02, 0.96, "(b)", transform=ax_b.transAxes, va="top", fontweight="bold")

fig.savefig(HERE / "fig_altitude.pdf")
fig.savefig(HERE / "fig_altitude.png", dpi=220)
print("written", HERE / "fig_altitude.pdf")
