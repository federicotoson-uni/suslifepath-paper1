"""Compact lifetime calibration and sampled altitude distribution."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
data = json.load(open(HERE.parent.parent / "outputs" / "iac_a6_sweep_scale1.0.json"))
h = np.asarray(data["_meta"]["altitudini"])
T = np.asarray(data["uncontrolled"]["tres"])
grid = np.linspace(250, 1600, 500)
cal_h, cal_t = np.array([610., 717.]), np.array([25., 115.])
b = np.log(cal_t[1] / cal_t[0]) / (cal_h[1] - cal_h[0])
a = np.log(cal_t[0]) - b * cal_h[0]
uncapped = np.exp(a + b * grid)
plt.rcParams.update({"font.family":"sans-serif", "font.size":8, "axes.labelsize":8,
    "xtick.labelsize":7.5, "ytick.labelsize":7.5, "axes.edgecolor":"#aaa9a1",
    "axes.linewidth":.6, "pdf.fonttype":42})
fig, (ax, axh) = plt.subplots(2, 1, figsize=(3.35,3.55), sharex=True,
    gridspec_kw={"height_ratios":[2.1,1]}, constrained_layout=True)
for scale, color, ls, label in [(0.8,"#7a9db5","--","0.8$\\times$"),(1.0,"#174a7e","-","nominal"),(1.8,"#d95f3f","--","1.8$\\times$")]:
    ax.plot(grid, np.minimum(1000., scale*uncapped), color=color, lw=1.4, ls=ls, label=label)
ax.scatter(cal_h,cal_t,s=24,color="#111111",zorder=4,label="calibration")
for y,c,lab in [(5,"#258f72","5-year limit"),(25,"#d95f3f","25-year limit")]:
    ax.axhline(y,color=c,lw=.8,ls="--"); ax.text(1585,y*1.08,lab,ha="right",va="bottom",fontsize=6.5,color=c)
ax.set_ylabel("natural lifetime (yr)"); ax.set_ylim(.5,1300); ax.set_yscale("log")
ax.legend(frameon=False,fontsize=6.5,ncol=4,loc="lower right",handlelength=1.5,columnspacing=.6)
axh.hist(h, bins=np.arange(250,1601,50), color="#d9e4ef", edgecolor="white", lw=.35)
axh.set_xlabel("operating altitude (km)"); axh.set_ylabel("missions")
ax.set_xlim(250,1600); ax.grid(axis="y",color="#e3e2dc",lw=.5); ax.set_axisbelow(True); axh.grid(axis="y",color="#e3e2dc",lw=.5); axh.set_axisbelow(True)
for p in (ax,axh): p.spines["top"].set_visible(False); p.spines["right"].set_visible(False)
ax.text(.02,.96,"(a)",transform=ax.transAxes,va="top",fontweight="bold")
axh.text(.02,.90,"(b)",transform=axh.transAxes,va="top",fontweight="bold")
fig.savefig(HERE/"fig_lifetime.pdf"); fig.savefig(HERE/"fig_lifetime.png",dpi=220)
