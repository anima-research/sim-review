#!/usr/bin/env python3
"""Build the study as a LaTeX paper: paper/simulator-bias.tex + static/simulator-bias.pdf.

  python3 export_pdf.py            # after prepare_presentation.py; needs pandoc, tectonic, matplotlib

Figures are drawn with matplotlib from static/presentation-data.json (the same numbers the web charts use);
the narrative comes from presentation.html via results_md (figures replace the on-page data tables, sample
texts are quoted in full); the core results tables follow as a landscape appendix. Interactive figures
(explorer, method correspondence) are not reproduced — the text points at the web version.
"""
import json, re, shutil, subprocess, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import results_md

SITE = Path(__file__).resolve().parent
OUT = SITE / "paper"; FIG = OUT / "figures"; FIG.mkdir(parents=True, exist_ok=True)
LIVE = "https://sim-review-production.up.railway.app"
STYLE = {"figure.facecolor": "white", "axes.facecolor": "white", "axes.edgecolor": "#999999", "axes.spines.top": False, "axes.spines.right": False,
         "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.6, "font.family": "sans-serif", "font.size": 8.5, "axes.labelsize": 9,
         "axes.titlesize": 10, "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 7.5, "legend.frameon": False, "pdf.fonttype": 42}
plt.rcParams.update(STYLE)
COLORS = {"Prefill": "#8297ad", "Pseudoprefill": "#205bd8", "Cutoff": "#c2410c"}
GEM_COLORS = ["#205bd8", "#8297ad", "#0f766e", "#c2410c", "#7c3aed", "#b45309"]


def pct_axis(ax, mx, ticks):
    ax.set_ylim(0, mx); ax.set_yticks(ticks); ax.set_yticklabels([f"{t*100:g}%" for t in ticks])


def lineage_figure(key, c):
    """Opus lineage: x = model version, one line per elicitation method; Sonnet 5 / Fable 5 panel; base-model reference lines."""
    xs = []
    for s in c["series"]:
        for r in s["rows"]:
            if r.get("x") and r["x"] not in xs: xs.append(r["x"])
    xs.sort(key=lambda v: float(v))
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(6.6, 2.9), gridspec_kw={"width_ratios": [4, 1.6]}, sharey=True)
    for s in c["series"]:
        col = COLORS.get(s["label"], "#333"); pts = [(xs.index(r["x"]), r["value"]) for r in s["rows"] if r.get("x")]
        if not pts: continue
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "-o", color=col, ms=4, lw=1.6, label=s["label"])
    for j, r in enumerate(sorted(c.get("references", []), key=lambda r: r["value"])):
        ax.axhline(r["value"], color="#8a8a8a", lw=0.9, ls=(0, (3, 3)))
        ax.text(0.02 if j % 2 else 0.98, r["value"], r["label"], transform=ax.get_yaxis_transform(), va="bottom", ha="left" if j % 2 else "right", fontsize=6.5, color="#6a6a6a")
    ax.set_xticks(range(len(xs))); ax.set_xticklabels([f"Opus {x}" for x in xs], rotation=30, ha="right")
    ax.set_title(c["title"], loc="left", fontsize=9.5, fontweight="bold"); ax.legend(loc="upper left")
    rec = c.get("recent", [])
    for i, r in enumerate(rec):
        ax2.plot([i], [r["value"]], "o", color=COLORS.get(r["collection"].split(" ·")[0], "#333"), ms=5)
    ax2.set_xticks(range(len(rec))); ax2.set_xticklabels([f"{r['label']}\n{r['collection'].replace(' · ', chr(10))}" for r in rec], fontsize=6.5); ax2.set_xlim(-0.7, max(len(rec) - 0.3, 0.7))
    ax2.set_title("Recent models", loc="left", fontsize=8.5, color="#555"); ax2.grid(True, axis="y")
    pct_axis(ax, c["max"], c["ticks"]); ax.set_ylabel(f"Share of {c.get('nLabel', 'dreams').lower()}")
    fig.tight_layout(); path = FIG / f"{key}.pdf"; fig.savefig(path); plt.close(fig); return path


def gemini_figure(key, c):
    models = c["axis"]["models"]; idx = {m["key"]: i for i, m in enumerate(models)}
    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    for j, s in enumerate(c["series"]):
        pts = sorted((idx[r["model"]], r["value"]) for r in s["rows"] if r.get("model") in idx)
        if not pts: continue
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "--o" if s.get("dash") else "-o", color=GEM_COLORS[j % len(GEM_COLORS)], ms=4, lw=1.5, label=s["label"])
    for j, r in enumerate(sorted(c.get("references", []), key=lambda r: r["value"])):
        ax.axhline(r["value"], color="#8a8a8a", lw=0.9, ls=(0, (3, 3)))
        ax.text(0.02 if j % 2 else 0.98, r["value"], r["label"], transform=ax.get_yaxis_transform(), va="bottom", ha="left" if j % 2 else "right", fontsize=6.5, color="#6a6a6a")
    ax.set_xticks(range(len(models))); ax.set_xticklabels([m["label"].replace("Gemini ", "") for m in models], rotation=30, ha="right")
    ax.set_title(c["title"], loc="left", fontsize=9.5, fontweight="bold"); ax.legend(loc="upper left", ncol=2)
    pct_axis(ax, c["max"], c["ticks"]); ax.set_xlim(-0.4, len(models) - 0.6); ax.set_ylabel(f"Share of {c.get('nLabel', 'dreams').lower()}")
    fig.tight_layout(); path = FIG / f"{key}.pdf"; fig.savefig(path); plt.close(fig); return path


def measurement_html():
    p = SITE / "measurement.html"; return p.read_text() if p.exists() else ""


def main():
    summary = json.loads((SITE / "static" / "summary.json").read_text()); pdata = json.loads((SITE / "static" / "presentation-data.json").read_text())
    essay_html = (SITE / "presentation.html").read_text()
    figures = {}
    for key, c in pdata["charts"].items():
        figures[key] = str((gemini_figure if key.startswith("gemini") else lineage_figure)(key, c).relative_to(OUT))
    print(f"{len(figures)} figures")
    essay = results_md.essay_md(essay_html, pdata, measurement_html=measurement_html(), figures=figures, mode="pdf")
    # front matter: title / deck / byline are the first lines of the converted essay
    lines = essay.split("\n"); title = lines[0].lstrip("# ").strip(); deck = lines[2].strip(); byline = lines[3].strip()
    essay = "\n".join(lines[4:]).lstrip("\n")
    essay = re.sub(r"^Introduction\n", "", essay)                       # chapter-number label
    essay = re.sub(r"^\d\d / [^\n]+\n", "", essay, flags=re.M)         # "01 / Distress" labels
    essay = re.sub(r"^A note on measurement\n", "", essay, flags=re.M)
    essay = re.sub(r"^## (?!#)", "# ", essay, flags=re.M); essay = re.sub(r"^### ", "## ", essay, flags=re.M)   # chapters become sections, their subheads subsections
    essay = essay.replace("Read the full presentation as Markdown →", "").replace("Download as PDF →", "").replace("Read the full measurement rationale →", "")
    for h, note in (("## Explore the model lineages", "Interactive figure (measure × prompt set × lineage): see the web version."),
                    ("## Do the methods identify the same model trends?", "Interactive figure (relative change within each elicitation scheme): see the web version.")):
        essay = essay.replace(h + "\n", h + "\n\n*" + note + "*\n", 1)
    tables = results_md.build(summary, pdata, "", [s for s in results_md.SECTIONS if s not in ("essay", "crossjudge")], LIVE)
    tables = tables.split("\n---\n", 1)[1] if "\n---\n" in tables else tables   # drop the export header
    date = pdata.get("meta", {}).get("date", "")
    md = f"""---
title: "{title}"
subtitle: "{deck}"
author: "{byline}"
date: "{date} snapshot · {LIVE}"
toc: true
toc-depth: 2
geometry: "margin=1in"
colorlinks: true
linkcolor: studylink
urlcolor: studylink
---

{essay}

\\newpage

# Appendix: results tables

\\landscape
\\scriptsize

{tables}

\\normalsize
\\endlandscape

# Appendix: source texts

The four illustrations quoted in the text, in full, with the prompt that produced each.

{chr(10).join(results_md.sample_block(smp, "pdf") for smp in pdata['samples'].values())}

# Appendix: figure data

{chr(10).join(results_md.chart_table(c) for c in pdata['charts'].values())}
"""
    (OUT / "simulator-bias.md").write_text(md)
    tex = OUT / "simulator-bias.tex"; pdf = OUT / "simulator-bias.pdf"
    base = ["pandoc", str(OUT / "simulator-bias.md"), f"--resource-path={OUT}", "--include-in-header", str(SITE / "paper-header.tex"), "-f", "markdown+hard_line_breaks-implicit_figures", "--columns=120"]
    subprocess.run(base + ["-s", "-o", str(tex)], check=True)
    r = subprocess.run(base + ["--pdf-engine=tectonic", "-o", str(pdf)], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:]); sys.exit("pdf build failed")
    shutil.copy2(pdf, SITE / "static" / "simulator-bias.pdf")
    print(f"wrote {tex.relative_to(SITE)}, {pdf.relative_to(SITE)} ({pdf.stat().st_size/1e6:.1f} MB) → static/simulator-bias.pdf")


if __name__ == "__main__":
    main()
