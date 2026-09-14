"""Sensibilita' al mix degli archetipi per l'A6, per ripeso del campione.

Quota e archetipo sono estratti in modo indipendente, quindi un mix diverso si
ottiene pesando ogni missione con p_nuovo(archetipo) / p_realizzato(archetipo),
senza rieseguire MATLAB. Stampa le cifre di testa a 100 e 1000 anni per il mix
del paper e per tre mix alternativi. Numeri citati in Sezione 3.5.

Uso: python3 mix_reweight.py
"""
import json
from pathlib import Path

import numpy as np

JSON = Path(__file__).resolve().parent.parent.parent / "outputs" / "iac_a6_sweep_scale1.0.json"
T_OP = {"cubesat": 3, "smallsat": 5, "medium": 6, "large": 10}
NAMES = ["cubesat", "smallsat", "medium", "large"]
MIXES = {
    "paper 50/35/12/3": [.50, .35, .12, .03],
    "costellazioni 20/60/15/5": [.20, .60, .15, .05],
    "cubesat 70/25/4/1": [.70, .25, .04, .01],
    "pesante 30/40/20/10": [.30, .40, .20, .10],
}

d = json.load(open(JSON))
h = np.array(d["_meta"]["altitudini"])
arch = np.array(d["_meta"]["archetipi"])
top = np.array([T_OP[a] for a in arch])
u = np.array(d["uncontrolled"]["dgp"])
tres = np.array(d["uncontrolled"]["tres"])
r25 = np.array(d["rule25"]["dgp"])
r5 = np.array(d["rule5"]["dgp"])
p_real = {a: float((arch == a).mean()) for a in NAMES}


def at_horizon(H):
    return u * (top + np.minimum(tres, H)) / (top + tres)


print(f"{'mix':26s} {'H':>5s} {'rim25':>6s} {'strin':>6s} {'rapp':>6s} {'>800':>6s} {'large':>6s}")
for name, p in MIXES.items():
    w = np.array([p[NAMES.index(a)] / p_real[a] for a in arch])
    for H in (100, 1000):
        x = at_horizon(H)
        tot = (w * x).sum()
        rem25 = 1 - (w * r25).sum() / tot
        tight = ((w * r25).sum() - (w * r5).sum()) / tot
        share800 = (w * x)[h > 800].sum() / tot
        large = (w * x)[arch == "large"].sum() / tot
        print(f"{name:26s} {H:5d} {100*rem25:5.1f}% {100*tight:5.1f}% {rem25/tight:6.2f} {100*share800:5.1f}% {100*large:5.1f}%")
