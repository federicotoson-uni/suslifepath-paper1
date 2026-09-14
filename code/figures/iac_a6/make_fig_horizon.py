"""Figura 2 per l'A6: valore delle due leve in funzione continua dell'orizzonte.

Per ogni orizzonte H (anni dopo la fine delle operazioni) ricalcola, dal JSON dello
sweep, l'onere non controllato contato fino a H con il riscalaggio esatto
u_H = u (T_op + min(T_res, H)) / (T_op + T_res), e da quello:
  enforcement(H) = 1 - R25 / U_H          (tolto dalla regola dei 25 anni)
  tightening(H)  = (R25 - R5) / U_H       (tolto stringendo da 25 a 5)
  ratio(H)       = enforcement / tightening
Nominale in linea piena, banda 0,8x-1,8x del decadimento in ombra. Stampa il
pareggio H* (ratio = 1) per i tre modelli.

Uso: python3 make_fig_horizon.py
"""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / "outputs"
T_OP = {"cubesat": 3.0, "smallsat": 5.0, "medium": 6.0, "large": 10.0}
C_ENF, C_TIGHT, C_RATIO = "#1c5cab", "#eb6834", "#0d366b"
INK, MUTED, GRID, AXIS = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7"

H = np.logspace(np.log10(10), np.log10(1000), 400)


def curves(scale):
    d = json.load(open(OUT / f"iac_a6_sweep_scale{scale}.json"))
    top = np.array([T_OP[a] for a in d["_meta"]["archetipi"]])
    u = np.array(d["uncontrolled"]["dgp"]); tres = np.array(d["uncontrolled"]["tres"])
    R25 = np.sum(d["rule25"]["dgp"]); R5 = np.sum(d["rule5"]["dgp"])
    enf, tight = [], []
    for h in H:
        UH = np.sum(u * (top + np.minimum(tres, h)) / (top + tres))
        enf.append(1 - R25 / UH); tight.append((R25 - R5) / UH)
    enf, tight = np.array(enf), np.array(tight)
    return enf, tight, enf / tight


res = {s: curves(s) for s in ("0.8", "1.0", "1.8")}
for s, (e, t, r) in res.items():
    k = np.where(r >= 1)[0]
    hstar = H[k[0]] if len(k) else float("nan")
    i200 = np.argmin(abs(H - 200)); i100 = np.argmin(abs(H - 100))
    print(f"scale {s}: H* (ratio=1) = {hstar:5.0f} yr | at 100 yr enf {100*e[i100]:.1f}% tight {100*t[i100]:.1f}% ratio {r[i100]:.2f} | at 200 yr enf {100*e[i200]:.1f}% tight {100*t[i200]:.1f}% ratio {r[i200]:.2f}")

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 8, "axes.labelsize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.6, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.labelcolor": INK, "text.color": INK, "pdf.fonttype": 42,
})
fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(3.35, 4.6), constrained_layout=True, sharex=True)
for ax in (ax_a, ax_b):
    ax.set_xscale("log"); ax.grid(True, color=GRID, linewidth=0.5, which="major"); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.tick_params(length=2.5, width=0.5)
    for x in (100, 200):
        ax.axvline(x, color=AXIS, lw=0.6, ls=":")
    ax.set_xlim(10, 1000)

e08, t08, r08 = res["0.8"]; e10, t10, r10 = res["1.0"]; e18, t18, r18 = res["1.8"]
# (a) quote tolte
ax_a.fill_between(H, 100 * np.minimum(e08, e18), 100 * np.maximum(e08, e18), color=C_ENF, alpha=0.15, lw=0)
ax_a.fill_between(H, 100 * np.minimum(t08, t18), 100 * np.maximum(t08, t18), color=C_TIGHT, alpha=0.15, lw=0)
ax_a.plot(H, 100 * e10, color=C_ENF, lw=1.5, label="enforcing the 25-year rule")
ax_a.plot(H, 100 * t10, color=C_TIGHT, lw=1.5, ls="--", label="tightening 25 to 5 years")
ax_a.set_ylabel("share of summed burden removed (%)")
ax_a.set_ylim(0, 50)
ax_a.legend(frameon=False, loc="upper left", handlelength=2.2, borderaxespad=0.2)
ax_a.text(0.98, 0.96, "(a)", transform=ax_a.transAxes, va="top", ha="right", fontweight="bold")
ax_b.text(100, 14, "100", fontsize=6.5, color=MUTED, ha="center")
ax_b.text(200, 14, "200 yr", fontsize=6.5, color=MUTED, ha="center")
# (b) rapporto
ax_b.fill_between(H, np.minimum(r08, r18), np.maximum(r08, r18), color=C_RATIO, alpha=0.15, lw=0)
ax_b.plot(H, r10, color=C_RATIO, lw=1.5)
ax_b.axhline(1, color=AXIS, lw=0.8)
ax_b.set_yscale("log"); ax_b.set_ylim(0.2, 20)
ax_b.set_yticks([0.3, 1, 3, 10]); ax_b.set_yticklabels(["0.3", "1", "3", "10"])
ax_b.set_ylabel("enforcement over tightening")
ax_b.set_xlabel("horizon after the end of operations (years)")
ax_b.text(0.98, 0.96, "(b)", transform=ax_b.transAxes, va="top", ha="right", fontweight="bold")
k = np.where(r10 >= 1)[0]; hstar = H[k[0]]
ax_b.plot([hstar], [1], marker="o", ms=4, color=C_RATIO)
ax_b.annotate(f"break-even {hstar:.0f} yr", (hstar, 1), xytext=(6, -12), textcoords="offset points", fontsize=7, color=INK)

fig.savefig(HERE / "fig_horizon.pdf"); fig.savefig(HERE / "fig_horizon.png", dpi=220)
print("written", HERE / "fig_horizon.pdf")
