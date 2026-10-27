"""Draw the lineage graph (sources -> staging -> marts -> tests) from target/manifest.json."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

m = json.load(open(ROOT / "target" / "manifest.json"))
nodes = {}
for uid, s in m["sources"].items():
    nodes[uid] = ("source", f"raw.{s['name']}")
for uid, n in m["nodes"].items():
    if n["resource_type"] == "model":
        nodes[uid] = ("staging" if n["name"].startswith("stg_") else "mart", n["name"])
edges = [(p, uid) for uid, n in m["nodes"].items() if n["resource_type"] == "model"
         for p in n["depends_on"]["nodes"] if p in nodes]

def depth(u):
    ps = [a for a, b in edges if b == u]
    return 0 if not ps else 1 + max(depth(p) for p in ps)
cols = {}
for u in nodes:
    cols.setdefault(depth(u), []).append(u)
pos = {}
for d, us in cols.items():
    us.sort(key=lambda u: nodes[u][1])
    for i, u in enumerate(us):
        pos[u] = (d * 3.6, -(i - (len(us) - 1) / 2) * 1.3)

color = {"source": "#9AA5B1", "staging": "#4C9BE8", "mart": "#2E7D32"}
fig, ax = plt.subplots(figsize=(14, 6.5))
for a, b in edges:
    (x1, y1), (x2, y2) = pos[a], pos[b]
    ax.annotate("", xy=(x2 - 1.45, y2), xytext=(x1 + 1.45, y1),
                arrowprops=dict(arrowstyle="-|>", color="#555", lw=1.4))
for u, (x, y) in pos.items():
    kind, label = nodes[u]
    ax.add_patch(FancyBboxPatch((x - 1.45, y - 0.35), 2.9, 0.7, boxstyle="round,pad=0.05",
                                fc=color[kind], ec="black", lw=0.8))
    ax.text(x, y, label, ha="center", va="center", color="white", fontsize=8.5, weight="bold")
for d, title in [(0, "RAW (sources)"), (1, "STAGING (views)"), (3, "MARTS (tables)")]:
    if d in cols:
        ax.text(d * 3.6, max(p[1] for p in pos.values()) + 1.0, title, ha="center", fontsize=11, weight="bold")
ax.set_title("dbt lineage - berlin project (built from target/manifest.json)", fontsize=13)
ax.set_xlim(-1.8, max(p[0] for p in pos.values()) + 1.8)
ax.set_ylim(min(p[1] for p in pos.values()) - 0.9, max(p[1] for p in pos.values()) + 1.5)
ax.axis("off")
plt.tight_layout()
plt.savefig(str(ROOT / "outputs" / "lineage.png"), dpi=130)
for a, b in sorted(edges, key=lambda e: nodes[e[1]][1]):
    print(f"{nodes[a][1]:<28} -> {nodes[b][1]}")
