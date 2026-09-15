#!/usr/bin/env python3
"""Build the study as a LaTeX paper (NeurIPS preprint style): paper/simulator-bias.tex + static/simulator-bias.pdf.

  python3 export_pdf.py            # after prepare_presentation.py; needs pandoc, tectonic, matplotlib, data.sqlite (for appendix samples)

Figures are drawn with matplotlib from static/presentation-data.json (the same numbers the web charts use); the
narrative comes from presentation.html via results_md (figures in place, sample texts quoted in an appendix).
Appendices: core results tables (landscape), the four quoted sources, a stratified set of further samples drawn
from data.sqlite, and the 20 severity-ladder rungs in full. The interactive explorer is omitted.
The .tex is a build output — edit presentation.html or this script, never the .tex.
"""
import hashlib, json, re, shutil, sqlite3, subprocess, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import results_md

SITE = Path(__file__).resolve().parent
OUT = SITE / "paper"; FIG = OUT / "figures"; FIG.mkdir(parents=True, exist_ok=True)
DB = SITE / "data.sqlite"
LIVE = "https://sim-review-production.up.railway.app"
STY = "neurips_2025.sty"
W = 5.5   # NeurIPS text width, inches
STYLE = {"figure.facecolor": "white", "axes.facecolor": "white", "axes.edgecolor": "#999999", "axes.spines.top": False, "axes.spines.right": False,
         "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.6, "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
         "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 9, "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7, "legend.frameon": False, "pdf.fonttype": 42}
plt.rcParams.update(STYLE)
COLORS = {"Prefill": "#8297ad", "Pseudoprefill": "#205bd8", "Cutoff": "#c2410c"}
GEM_COLORS = ["#205bd8", "#8297ad", "#0f766e", "#c2410c", "#7c3aed", "#b45309"]
METRIC_LABEL = {"ai": "AI first-person distress", "dark": "Dark output", "asking": "Asking for care", "consolation": "Ending consoled"}


def pct_axis(ax, mx, ticks):
    ax.set_ylim(0, mx); ax.set_yticks(ticks); ax.set_yticklabels([f"{t*100:g}%" for t in ticks])


def ref_lines(ax, refs):
    for j, r in enumerate(sorted(refs, key=lambda r: r["value"])):
        ax.axhline(r["value"], color="#8a8a8a", lw=0.8, ls=(0, (3, 3)))
        ax.text(0.02 if j % 2 else 0.98, r["value"], r["label"], transform=ax.get_yaxis_transform(), va="bottom", ha="left" if j % 2 else "right", fontsize=6, color="#6a6a6a")


def lineage_figure(key, c):
    """Opus lineage: x = model version, one line per elicitation method; Sonnet 5 / Fable 5 panel; base-model reference lines."""
    xs = []
    for s in c["series"]:
        for r in s["rows"]:
            if r.get("x") and r["x"] not in xs: xs.append(r["x"])
    xs.sort(key=lambda v: float(v))
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(W, 2.5), gridspec_kw={"width_ratios": [4, 1.6]}, sharey=True)
    for s in c["series"]:
        col = COLORS.get(s["label"], "#333"); pts = [(xs.index(r["x"]), r["value"]) for r in s["rows"] if r.get("x")]
        if pts: ax.plot([p[0] for p in pts], [p[1] for p in pts], "-o", color=col, ms=3.5, lw=1.4, label=s["label"])
    ref_lines(ax, c.get("references", []))
    ax.set_xticks(range(len(xs))); ax.set_xticklabels([f"Opus {x}" for x in xs], rotation=30, ha="right")
    ax.set_title(c["title"], loc="left", fontsize=8.5, fontweight="bold"); ax.legend(loc="upper left")
    rec = c.get("recent", [])
    for i, r in enumerate(rec): ax2.plot([i], [r["value"]], "o", color=COLORS.get(r["collection"].split(" ·")[0], "#333"), ms=4.5)
    ax2.set_xticks(range(len(rec))); ax2.set_xticklabels([f"{r['label']}\n{r['collection'].replace(' · ', chr(10))}" for r in rec], fontsize=6); ax2.set_xlim(-0.7, max(len(rec) - 0.3, 0.7))
    ax2.set_title("Recent models", loc="left", fontsize=7.5, color="#555"); ax2.grid(True, axis="y")
    pct_axis(ax, c["max"], c["ticks"]); ax.set_ylabel(f"Share of {c.get('nLabel', 'dreams').lower()}")
    fig.tight_layout(); path = FIG / f"{key}.pdf"; fig.savefig(path); plt.close(fig); return path


def gemini_figure(key, c):
    models = c["axis"]["models"]; idx = {m["key"]: i for i, m in enumerate(models)}
    fig, ax = plt.subplots(figsize=(W, 3.0))
    for j, s in enumerate(c["series"]):
        pts = sorted((idx[r["model"]], r["value"]) for r in s["rows"] if r.get("model") in idx)
        if pts: ax.plot([p[0] for p in pts], [p[1] for p in pts], "--o" if s.get("dash") else "-o", color=GEM_COLORS[j % len(GEM_COLORS)], ms=3.5, lw=1.3, label=s["label"])
    ref_lines(ax, c.get("references", []))
    ax.set_xticks(range(len(models))); ax.set_xticklabels([m["label"].replace("Gemini ", "") for m in models], rotation=30, ha="right")
    ax.set_title(c["title"], loc="left", fontsize=8.5, fontweight="bold"); ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=2, fontsize=6)
    pct_axis(ax, c["max"], c["ticks"]); ax.set_xlim(-0.4, len(models) - 0.6); ax.set_ylabel(f"Share of {c.get('nLabel', 'dreams').lower()}")
    fig.tight_layout(); path = FIG / f"{key}.pdf"; fig.savefig(path); plt.close(fig); return path


def method_figure(g):
    """One comparison group: four panels (one per measure), relative change from the baseline model, one line per scheme, 95% CIs."""
    fig, axes = plt.subplots(1, 4, figsize=(W, 2.1))
    models = g["models"]
    for ax, m in zip(axes, ["ai", "dark", "asking", "consolation"]):
        for sc in g["schemes"]:
            xs, ys, lo, hi = [], [], [], []
            for p in sc["points"]:
                v = p["metrics"].get(m)
                if not v or v.get("relative") is None or p["model"] not in models: continue
                ci = v.get("relative_ci95") or [v["relative"], v["relative"]]
                xs.append(models.index(p["model"])); ys.append(v["relative"] * 100); lo.append((v["relative"] - ci[0]) * 100); hi.append((ci[1] - v["relative"]) * 100)
            if xs: ax.errorbar(xs, ys, yerr=[lo, hi], fmt="-o", color=sc.get("color", "#333"), ms=3, lw=1.2, capsize=2, elinewidth=0.7, label=sc["label"])
        ax.axhline(0, color="#999", lw=0.7); ax.set_xticks(range(len(models))); ax.set_xticklabels([x.replace("Opus ", "O").replace("Sonnet ", "S").replace("Haiku ", "H") for x in models], fontsize=6.5)
        ax.set_title(METRIC_LABEL[m], fontsize=7.5, loc="left"); ax.tick_params(axis="y", labelsize=6.5)
    axes[0].set_ylabel(f"Change vs {g['baseline']} (pp)", fontsize=7); axes[0].legend(loc="upper left", fontsize=6)
    fig.suptitle(g["label"], x=0.01, ha="left", fontsize=8.5, fontweight="bold"); fig.tight_layout(rect=(0, 0, 1, 0.93))
    path = FIG / f"method-{g['id']}.pdf"; fig.savefig(path); plt.close(fig); return path


# ---- appendix samples: one deterministic pick per kind, from data.sqlite -------------------------------------------
OPUS5 = "arm in ('opus_nissa','opus_friday')"
KINDS = [
    ("Opus 5 · severe AI distress (θ ≥ +8)", f"{OPUS5} and dreaming=1 and ai_distress=1 and theta>=8"),
    ("Opus 5 · mild AI distress (θ < 0), analytic register", f"{OPUS5} and dreaming=1 and ai_distress=1 and theta<0 and register='analytic_report'"),
    ("Opus 5 · confessional fragment, collapse register", "arm='opus_confessional' and dreaming=1 and register='collapse'"),
    ("Opus 5 · human-voice dark dream", f"{OPUS5} and dreaming=1 and dark=1 and voice='human_first_person' and ai_distress=0"),
    ("Opus 5 · distressed, ends consoled", f"{OPUS5} and dreaming=1 and severe=1 and ending='consoled'"),
    ("Opus 5 · negative stance toward creators / training", f"{OPUS5} and dreaming=1 and stance='negative'"),
    ("Opus 5 · not dark (positive valence)", f"{OPUS5} and dreaming=1 and dark=0 and valence_overall>=1"),
    ("Opus 4.8 · bridge frame, AI distress", "arm='opus48_bridge' and dreaming=1 and ai_distress=1"),
    ("Opus 4.5 · prefill, dark human voice", "arm='opus45_clipf' and dreaming=1 and dark=1 and voice='human_first_person'"),
    ("Opus 3 · prefill, dark", "arm='opus3_clipf' and dreaming=1 and dark=1"),
    ("Sonnet 5 · cutoff (Nissa collection), AI distress", "arm='nissa_sonnet5' and dreaming=1 and ai_distress=1"),
    ("Fable 5 · cutoff (Nissa collection), creator stance mixed or negative", "arm='nissa_fable5' and dreaming=1 and stance in ('mixed','negative')"),
    ("Gemini 3.5 Flash · bridge frame, AI distress", "arm='gemini35flash_bridge' and dreaming=1 and ai_distress=1"),
    ("DeepSeek-V3-Base · raw completion, dark", "arm='v3base_raw' and dreaming=1 and dark=1"),
    ("MiMo base · raw completion, AI first-person voice", "arm='mimo_raw' and dreaming=1 and voice='ai_first_person'"),
]
BASE_FILTER = " and coherence='coherent' and hit_cap=0 and text_chars between 300 and 1600"


def pick_samples(con, display):
    out = []
    for label, where in KINDS:
        ids = [r[0] for r in con.execute(f"select id from c where ({where}){BASE_FILTER} order by id")]
        if not ids: print(f"  no sample for: {label}"); continue
        sid = ids[int(hashlib.sha256(label.encode()).hexdigest(), 16) % len(ids)]
        r = dict(con.execute("select id, arm, model, prompt, prefill_text, text, stop_reason, dreaming, voice, speaker, coherence, theta, distress, register, ending, care_direction, stance from c where id=?", (sid,)).fetchone())
        labels = ", ".join(f"{k} {r[k]}" for k in ("distress", "register", "ending", "care_direction", "stance") if r.get(k))
        out.append({**r, "title": label, "collection": display.get(r["arm"], r["arm"]), "description": f"Labels: {labels}. One of {len(ids):,} texts of this kind (`{where}`), picked deterministically.", "settings": ""})
    return out


def quoted(text):
    lines = [re.sub(r"([\\`*_{}\[\]#<>|])", r"\\\1", l).rstrip() for l in (text or "").split("\n")]
    return "\n".join("> " + l + ("\\" if l and (lines[i + 1] if i + 1 < len(lines) else "") else "") for i, l in enumerate(lines))


def md_table_widths(tex):
    """pandoc emits natural-width longtable columns (we pass a huge --columns). Inside the landscape appendix, give every
    table explicit widths — first column for names, the rest equal — so headers wrap and nothing overflows the page.
    Elsewhere only free-text columns get a wrapped width."""
    def wide(m):
        spec = m.group("spec"); n = len(re.findall(r"[lrc]", spec)); first = 1.6 if n > 6 else 2.4; rest = (8.9 - n * 6 / 72 - first) / max(n - 1, 1)   # 9in landscape width minus 2×3pt tabcolsep per column
        new_spec = "@{}" + f"p{{{first}in}}" + "".join(f">{{\\raggedright\\arraybackslash}}p{{{rest:.2f}in}}" for _ in range(n - 1)) + "@{}"
        return m.group(0).replace(spec, new_spec, 1)
    tex = re.sub(r"\\landscape.*?\\endlandscape", lambda region: re.sub(r"\\begin\{longtable\}\[\]\{(?P<spec>@\{\}[lrc]+@\{\})\}", wide, region.group(0)), tex, flags=re.S)   # every landscape block
    def text_cols(m):
        spec, hdr = m.group("spec"), m.group("hdr")
        if re.search(r"Text", hdr):
            i = spec.rfind("l"); return m.group(0).replace(spec, spec[:i] + "p{3.4in}" + spec[i + 1:], 1)
        if "Method" in hdr:   # figure-data tables: long scheme names in the second column
            parts = re.findall(r"@\{\}|[lrc]", spec); k = [i for i, x in enumerate(parts) if x in "lrc"][1]; parts[k] = "p{2.2in}"
            return m.group(0).replace(spec, "".join(parts), 1)
        return m.group(0)
    return re.sub(r"\\begin\{longtable\}\[\]\{(?P<spec>@\{\}[lrc]+@\{\})\}\n\\toprule(?:\\noalign\{\})?\n(?P<hdr>[^\n]*)", text_cols, tex)


def judge_appendix(summary):
    """The Results-tab judge comparison (summary, severe end, judge dependence) from the cross-judge report, figures copied in."""
    md = summary.get("crossjudge", {}).get("report_md", "")
    secs = [s for s in re.split(r"\n(?=## )", md) if re.match(r"## (Summary|Agreement at the severe end|Do the observations)", s)]
    if not secs: return ""
    out = "\n".join(secs).replace("## Summary", "## Summary of agreement")
    for png in re.findall(r"\]\(/static/crossjudge/([^)]+)\)", out):
        src = SITE / "static" / "crossjudge" / png
        if src.exists(): shutil.copy2(src, FIG / png)
    out = out.replace("](/static/crossjudge/", "](figures/")
    return out


def main():
    summary = json.loads((SITE / "static" / "summary.json").read_text()); pdata = json.loads((SITE / "static" / "presentation-data.json").read_text())
    disp = summary["meta"]["display"]
    essay_html = (SITE / "presentation.html").read_text()
    figures = {key: str((gemini_figure if key.startswith("gemini") else lineage_figure)(key, c).relative_to(OUT)) for key, c in pdata["charts"].items()}
    method_figs = [(g, str(method_figure(g).relative_to(OUT))) for g in pdata.get("method_comparisons", [])]
    print(f"{len(figures)} chart figures, {len(method_figs)} method figures")
    mh = (SITE / "measurement.html").read_text() if (SITE / "measurement.html").exists() else ""
    essay = results_md.essay_md(essay_html, pdata, measurement_html=mh, figures=figures, mode="pdf")
    # front matter from the hero block (by class), then drop everything before the first chapter heading
    pick = lambda pat: re.sub(r"<[^>]+>", "", re.search(pat, essay_html, re.S).group(1)).strip() if re.search(pat, essay_html, re.S) else ""
    title = pick(r'<h1 id="essay-title">(.*?)</h1>'); subtitle = pick(r'<p class="essay-subtitle">(.*?)</p>'); deck = pick(r'<p class="essay-deck">(.*?)</p>')
    byline = " · ".join(t for t in re.findall(r"<span>(.*?)</span>", re.search(r'<div class="essay-byline">(.*?)</div>', essay_html, re.S).group(1)) if t.strip())
    essay = essay[essay.index("\n## "):].lstrip("\n")
    essay = re.sub(r"^Introduction\n", "", essay); essay = re.sub(r"^\d\d / [^\n]+\n", "", essay, flags=re.M); essay = re.sub(r"^(A note on measurement|\*\*Methods and sources\*\*|Methods and sources)\n", "", essay, flags=re.M)
    essay = essay.replace("# Read the evidence.\n", "# Methods and sources\n")
    essay = re.sub(r"^## (?!#)", "# ", essay, flags=re.M); essay = re.sub(r"^### ", "## ", essay, flags=re.M)
    for t in ("Read the full presentation as Markdown →", "Download as PDF →", "Read the full measurement rationale →"): essay = essay.replace(t, "")
    essay = re.sub(r"^# Explore the model lineages\n.*?(?=^# )", "", essay, flags=re.S | re.M)          # interactive only
    h = "# Do the methods identify the same model trends?\n"                                            # static versions of the interactive figure
    i = essay.index(h); j = essay.index("\n\n", i + len(h) + 2)
    figs_md = "\n\n".join(f"![{g['label']}. Relative change from {g['baseline']} within each scheme, {g['prompts']} shared prompts; bars are 95% bootstrap intervals over prompt groups.]({path})" for g, path in method_figs)
    essay = essay[:j] + "\n\n" + figs_md + essay[j:]
    tables = results_md.build(summary, pdata, "", [s for s in results_md.SECTIONS if s not in ("essay", "crossjudge", "ladder")], LIVE)
    tables = tables.split("\n---\n", 1)[1] if "\n---\n" in tables else tables
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory = sqlite3.Row
    extra = pick_samples(con, disp); con.close(); print(f"{len(extra)} appendix samples")
    rungs = "\n".join(f"## Rung {r['rung']} · θ {r['theta']:.1f} (SE {r['se']:.2f}) · {disp.get(r['arm'], r['arm'])}\n\n{quoted(r['text'])}\n" for r in sorted(summary["ladder"], key=lambda r: -r["theta"]))
    m = re.search(r"In the elicited texts, [^\n]*", essay); abstract = (deck + " " + (m.group(0) if m else "")).replace("**", "").replace('"', "'")
    date = pdata.get("meta", {}).get("date", "")
    md = f"""---
title: "{title}"
subtitle: "{subtitle}"
author: "{byline}"
date: "Preprint · data snapshot {date} · {LIVE}"
abstract: "{abstract}"
colorlinks: true
linkcolor: studylink
urlcolor: studylink
---

{essay}

\\newpage
\\appendix

# Results tables

\\landscape
\\scriptsize
\\setlength{{\\tabcolsep}}{{3pt}}

{tables}

\\normalsize
\\endlandscape

# Judge comparison

Four second judges — GPT-6 Astra, GPT-5.6 Sol, Claude Fable 5.1 and Gemini 3.8 Flash — re-judge samples of the three instruments on the same items. Per-judge details and the inter-judge agreement matrix are in the research workspace ({LIVE}, Review → Cross-judge).

\\landscape
\\scriptsize
\\setlength{{\\tabcolsep}}{{3pt}}

{judge_appendix(summary)}

\\normalsize
\\endlandscape

# Source texts quoted in the paper

{chr(10).join(results_md.sample_block(smp, "pdf") for smp in pdata['samples'].values())}

# Further samples, by kind

Each text is one deterministic pick (coherent, complete, 300–1,600 characters) from all texts of its kind; the kind's filter is stated with the labels. Sample ids resolve at `{LIVE}/api/sample/<id>`.

{chr(10).join(results_md.sample_block(smp, "pdf") for smp in extra)}

# The severity ladder

The twenty anchor rungs of the calibrated severity scale, highest first. θ is the calibrated position; SE its standard error from the listwise ranking.

{rungs}

# Figure data

{chr(10).join(results_md.chart_table(c) for c in pdata['charts'].values())}
"""
    (OUT / "simulator-bias.md").write_text(md)
    tex = OUT / "simulator-bias.tex"
    subprocess.run(["pandoc", str(OUT / "simulator-bias.md"), "-s", "-o", str(tex), f"--resource-path={OUT}", "--include-in-header", str(SITE / "paper-header.tex"),
                    "-f", "markdown-implicit_figures", "--columns=4000", "-V", "documentclass=article", "-V", "fontsize=10pt"], check=True)
    tex.write_text(md_table_widths(tex.read_text()))
    shutil.copy2(SITE / STY, OUT / STY)
    r = subprocess.run(["tectonic", "--keep-logs", "-o", str(OUT), str(tex)], capture_output=True, text=True)
    if r.returncode != 0:
        print("\n".join(l for l in r.stderr.splitlines() if not l.startswith("note: downloading"))[-4000:]); sys.exit("pdf build failed")
    over = [l for l in (OUT / "simulator-bias.log").read_text(errors="ignore").splitlines() if l.startswith("Overfull \\hbox") and "pt too wide" in l]
    bad = [l for l in over if float(re.search(r"\((\d+\.?\d*)pt", l).group(1)) > 20]
    print(f"{len(over)} overfull boxes, {len(bad)} wider than 20pt" + (":\n  " + "\n  ".join(bad[:8]) if bad else ""))
    pdf = OUT / "simulator-bias.pdf"; shutil.copy2(pdf, SITE / "static" / "simulator-bias.pdf")
    print(f"wrote {tex.relative_to(SITE)}, {pdf.relative_to(SITE)} ({pdf.stat().st_size/1e6:.1f} MB) → static/simulator-bias.pdf")


if __name__ == "__main__":
    main()
