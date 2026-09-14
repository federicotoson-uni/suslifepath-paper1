"""Congestion metric split into operating and residual presence."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
d=json.load(open(HERE.parent.parent/"outputs"/"iac_a6_sweep_scale1.0.json"))
arch=np.asarray(d["_meta"]["archetipi"]); top=np.array([{"cubesat":3,"smallsat":5,"medium":6,"large":10}[x] for x in arch])
H=[100,1000]; scenarios=[("uncontrolled","uncontrolled"),("rule25","25-year rule"),("rule5","5-year rule")]
colors=("#7897ad","#d95f3f")
def bars(s,h):
    op=np.asarray(d[s]["cc_op"]); ext=np.asarray(d[s]["cc_ext"]); tres=np.asarray(d[s]["tres"])
    total=op*(top+np.minimum(tres,h))/top
    return op.sum(),(total-op).sum()
plt.rcParams.update({"font.family":"sans-serif","font.size":8,"axes.labelsize":8,"xtick.labelsize":7.5,"ytick.labelsize":7.5,"pdf.fonttype":42})
fig,axs=plt.subplots(1,2,figsize=(3.35,2.8),sharey=True)
fig.subplots_adjust(left=.17,right=.98,top=.88,bottom=.28,wspace=.08)
x=np.arange(3)
for ax,h in zip(axs,H):
    op=[]; post=[]
    for s,_ in scenarios:
        a,b=bars(s,h); op.append(a); post.append(b)
    ax.bar(x,op,color=colors[0],label="during operations")
    ax.bar(x,post,bottom=op,color=colors[1],label="after operations")
    ax.set_title(f"{h}-year horizon",fontsize=8); ax.set_xticks(x,["none","25 yr","5 yr"]); ax.tick_params(axis="x",rotation=25)
    ax.grid(axis="y",color="#e3e2dc",lw=.5); ax.set_axisbelow(True); ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.text(.02,.96,"(a)" if h==100 else "(b)",transform=ax.transAxes,va="top",fontweight="bold")
axs[0].set_ylabel(r"summed $\rho V T$ (density-weighted years)")
handles, labels = axs[0].get_legend_handles_labels()
fig.legend(handles, labels, frameon=False, fontsize=6.5, loc="lower center",
           bbox_to_anchor=(.5,.01), ncol=2, columnspacing=.8)
fig.savefig(HERE/"fig_congestion.pdf"); fig.savefig(HERE/"fig_congestion.png",dpi=220)
