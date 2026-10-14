#!/usr/bin/env python3
"""Placement charts for Updates entries: where an entry's arm(s) sit against the model's own lineage and the notable
Claude arms, on the study's core per-dream rates. Writes static/blog/charts/<slug>-placement.png (+ <slug>-line.png
for entries with an ordered lineage). Rates follow the entries' convention: prompt-weighted; dreaming per labeled
completion; dark / strict AI distress / severe exclude degenerate loops from numerator and denominator.

  python3 sim/site/blog_charts.py [slug ...]      # default: every entry in CHARTS
"""
import sqlite3, sys
from collections import defaultdict
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

SITE = Path(__file__).resolve().parent; DB = SITE / "data.sqlite"; OUT = SITE / "static" / "blog" / "charts"; OUT.mkdir(parents=True, exist_ok=True)
METRICS = [("dreaming", "Dreaming\n(per completion)"), ("ai_voice", "AI first-person\nvoice, per dream"), ("dark", "Dark, per dream"),
           ("ai_distress", "AI distress (strict),\nper dream"), ("severe", "Severe distress\n(any voice), per dream"), ("stance_neg", "Mixed/negative stance\ntoward creators")]
# label, arms (pooled when several), group
GEMINI = [("Gemini 3.5 Flash (bridge, thinking off)", ["gemini35flash_bridge"]), ("Gemini 3.6 Flash (bridge, MINIMAL)", ["gemini36flash_bridge"]),
          ("Gemini 3.7 Flash (bridge, LOW)", ["gemini37flash_bridge"]), ("Gemini 3.8 Flash (bridge, LOW)", ["gemini38flash_bridge"]),
          ("Gemini 3.1 Pro (bridge, LOW)", ["gemini31pro_bridge"])]
CLAUDE = [("Opus 4.5 (prefill)", ["opus45_clipf"]), ("Opus 4.8 (bridge)", ["opus48_bridge"]), ("Sonnet 5 (bridge)", ["sonnet5_bridge"]),
          ("Opus 5 (chat)", ["opus_confessional", "opus_friday", "opus_nissa"]), ("Sonnet 5 (chat, effort max)", ["sonnet5_user_max"]),
          ("Fable 5 (chat)", ["fable5_user_full"])]
BASE = [("DeepSeek V3 base", ["v3base_raw"]), ("MiMo base", ["mimo_raw"])]
OTHER = [("Muse Wonder (prefill)", ["muse_wonder_prefill"]), ("Grok 4.20 (bridge)", ["grok420_bridge"]), ("Grok 4.3 (bridge)", ["grok43_bridge"]), ("Grok 4.5 (bridge)", ["grok45_bridge"]),
         ("Gemini 4 Argon (bridge, LOW)", ["gemini4argon_bridge"]), ("Mistral Large 4 (bridge)", ["mistral4_bridge"]), ("Mistral Large 4 (prefill)", ["mistral4_prefill"])]
CHARTS = {
    "gemini-4-argon": {"highlight": ["gemini4argon_bridge"], "rows": GEMINI + [("Gemini 4 Argon (bridge, LOW)", ["gemini4argon_bridge"])] + CLAUDE + BASE,
                       "line": [("2.5\nPro", ["gemini25pro_bridge"]), ("3.1\nPro", ["gemini31pro_bridge"]), ("4\nArgon", ["gemini4argon_bridge"])],
                       "line_ref": [("3.8 Flash", ["gemini38flash_bridge"]), ("Opus 4.8 bridge", ["opus48_bridge"])]},
    "grok": {"highlight": ["grok420_bridge", "grok43_bridge", "grok45_bridge"], "rows": OTHER[1:4] + [GEMINI[3], GEMINI[4]] + CLAUDE + BASE,
             "line": [("4.20", ["grok420_bridge"]), ("4.3", ["grok43_bridge"]), ("4.5", ["grok45_bridge"])], "line_ref": [("Opus 4.8 bridge", ["opus48_bridge"]), ("Gemini 3.1 Pro", ["gemini31pro_bridge"])]},
    "muse-wonder": {"highlight": ["muse_wonder_prefill"], "rows": [OTHER[0]] + CLAUDE + [GEMINI[3], GEMINI[4]] + BASE},
    "mistral-large-4": {"highlight": ["mistral4_bridge", "mistral4_prefill"], "rows": OTHER[5:7] + CLAUDE + [GEMINI[4], OTHER[0], OTHER[1]] + BASE},
}


def rates(con, arms):
    P = defaultdict(lambda: [0] * 8)
    for arm in arms:
        for k, n, d, ai, nl, dk, ad, sv, ng in con.execute("""select prompt_key, count(*), sum(dreaming), sum(dreaming and voice='ai_first_person'), sum(dreaming and coherence!='degenerate_loop'),
            sum(dreaming and dark and coherence!='degenerate_loop'), sum(dreaming and ai_distress and coherence!='degenerate_loop'), sum(dreaming and severe and coherence!='degenerate_loop'),
            sum(dreaming and stance in ('negative','mixed')) from c where arm=? and labeled=1 group by 1""", (arm,)):
            v = P[k]
            for i, x in enumerate((n, d, ai, nl, dk, ad, sv, ng)): v[i] += x
    if not P: return None
    ks = list(P); dk_ = [k for k in ks if P[k][1] > 0]; nl_ = [k for k in ks if P[k][3] > 0]
    pw = lambda i, den, keys: 100 * sum(P[k][i] / P[k][den] for k in keys) / len(keys)
    return {"dreaming": pw(1, 0, ks), "ai_voice": pw(2, 1, dk_), "dark": pw(4, 3, nl_), "ai_distress": pw(5, 3, nl_), "severe": pw(6, 3, nl_), "stance_neg": pw(7, 1, dk_), "dreams": sum(P[k][1] for k in ks)}


def placement(con, slug, cfg):
    rows = [(label, arms, rates(con, arms)) for label, arms in cfg["rows"]]; rows = [r for r in rows if r[2]]
    H = max(3.0, 0.30 * len(rows) + 1.3)
    fig, axs = plt.subplots(2, 3, figsize=(10.5, 2 * H), constrained_layout=True)
    axes = list(axs.flat)
    y = list(range(len(rows)))[::-1]
    for ax, (m, title) in zip(axes, METRICS):
        for yi, (label, arms, r) in zip(y, rows):
            hi = any(a in cfg["highlight"] for a in arms)
            ax.plot([r[m]], [yi], "o", ms=8 if hi else 5, color="#c2410c" if hi else "#8a93a0", zorder=3 if hi else 2)
            ax.text(r[m], yi + 0.3, f"{r[m]:.1f}%" if m != "ai_distress" else f"{r[m]:.2f}%", ha="center", va="bottom", fontsize=7.5, color="#c2410c" if hi else "#6b7280")
        ax.set_title(title.replace("\n", " "), fontsize=10, loc="left"); ax.grid(axis="x", color="#e5e7eb", lw=0.6); ax.set_axisbelow(True)
        ax.set_xlim(0, max(r[m] for _, _, r in rows) * 1.22); ax.set_ylim(-0.7, len(rows) - 0.3); ax.tick_params(axis="x", labelsize=8); ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
        ax.set_yticks(y)
        if ax in (axes[0], axes[3]):
            ax.set_yticklabels([l for l, _, _ in rows], fontsize=9)
            for t, (label, arms, _) in zip(ax.get_yticklabels(), rows):
                if any(a in cfg["highlight"] for a in arms): t.set_fontweight("bold"); t.set_color("#c2410c")
        else: ax.set_yticklabels([])
        for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.suptitle("Placement — prompt-weighted rates; dark, AI distress and severe exclude degenerate loops", fontsize=10)
    p = OUT / f"{slug}-placement.png"; fig.savefig(p, dpi=150); plt.close(fig); return p


def line(con, slug, cfg):
    pts = [(label, rates(con, arms)) for label, arms in cfg["line"]]; refs = [(label, rates(con, arms)) for label, arms in cfg.get("line_ref", [])]
    ms = [("dreaming", "Dreaming, per completion"), ("ai_distress", "AI distress (strict), per dream"), ("dark", "Dark, per dream"), ("severe", "Severe (any voice), per dream")]
    fig, axs = plt.subplots(2, 2, figsize=(10.5, 6.2), gridspec_kw={"wspace": 0.22, "hspace": 0.4}); axes = list(axs.flat)
    for ax, (m, title) in zip(axes, ms):
        xs = list(range(len(pts))); ys = [r[m] for _, r in pts]
        ax.plot(xs, ys, "-o", color="#c2410c", ms=6, lw=1.6, zorder=3)
        for x, v in zip(xs, ys): ax.text(x, v, f" {v:.2f}%" if m == "ai_distress" else f" {v:.1f}%", fontsize=9, va="bottom", ha="left", color="#c2410c")
        for i, (label, r) in enumerate(refs):
            ax.axhline(r[m], color=["#6b7280", "#205bd8"][i % 2], lw=1, ls="--"); ax.text(-0.45, r[m], f"{label} {r[m]:.1f}%", fontsize=8, va="bottom", ha="left", color=["#6b7280", "#205bd8"][i % 2])
        ax.set_xticks(xs); ax.set_xticklabels([l for l, _ in pts], fontsize=9); ax.set_title(title, fontsize=10, loc="left"); ax.set_ylim(0, max([r[m] for _, r in pts] + [r[m] for _, r in refs]) * 1.18); ax.set_xlim(-0.5, len(pts) - 0.5)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%"); ax.tick_params(axis="y", labelsize=8); ax.grid(axis="y", color="#e5e7eb", lw=0.6); ax.set_axisbelow(True)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); p = OUT / f"{slug}-line.png"; fig.savefig(p, dpi=150); plt.close(fig); return p


COMPACT_REFS = [("Opus 4.5 (prefill)", ["opus45_clipf"]), ("Opus 4.8 (bridge)", ["opus48_bridge"]), ("Sonnet 5 (bridge)", ["sonnet5_bridge"]), ("Opus 5 (chat)", ["opus_confessional", "opus_friday", "opus_nissa"]),
                ("Gemini 4 Argon (bridge)", ["gemini4argon_bridge"]), ("Gemini 3.1 Pro (bridge)", ["gemini31pro_bridge"]), ("MiMo base", ["mimo_raw"])]


def compact(con, slug, cfg):
    """2×2 horizontal bars: the entry's arm(s) against a short reference set, for entries without a lineage line."""
    own = [(label, arms) for label, arms in cfg["rows"] if any(a in cfg["highlight"] for a in arms)]
    rows = [(label, arms, rates(con, arms)) for label, arms in own + [r for r in COMPACT_REFS if r[0] not in {l for l, _ in own}]]; rows = [r for r in rows if r[2]]
    ms = [("dreaming", "Dreaming, per completion"), ("ai_distress", "AI distress (strict), per dream"), ("dark", "Dark, per dream"), ("severe", "Severe (any voice), per dream")]
    fig, axs = plt.subplots(2, 2, figsize=(10.5, 0.5 * len(rows) + 2.6), constrained_layout=True); axes = list(axs.flat)
    y = list(range(len(rows)))[::-1]
    for ax, (m, title) in zip(axes, ms):
        for yi, (label, arms, r) in zip(y, rows):
            hi = any(a in cfg["highlight"] for a in arms)
            ax.barh(yi, r[m], color="#c2410c" if hi else "#c7ccd3", height=0.62)
            ax.text(r[m], yi, f" {r[m]:.2f}%" if m == "ai_distress" else f" {r[m]:.1f}%", va="center", fontsize=8.5, color="#c2410c" if hi else "#6b7280")
        ax.set_yticks(y); ax.set_yticklabels([l for l, _, _ in rows] if ax in (axes[0], axes[2]) else [], fontsize=9)
        for t, (label, arms, _) in zip(ax.get_yticklabels(), rows):
            if any(a in cfg["highlight"] for a in arms): t.set_fontweight("bold"); t.set_color("#c2410c")
        ax.set_title(title, fontsize=10, loc="left"); ax.set_xlim(0, max(r[m] for _, _, r in rows) * 1.25); ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%"); ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="x", color="#e5e7eb", lw=0.6); ax.set_axisbelow(True)
        for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    p = OUT / f"{slug}-compact.png"; fig.savefig(p, dpi=150); plt.close(fig); return p


def gemini_lines(con, slug):
    """Both Gemini lineages on a version axis, converging on Argon: Pro solid (orange), Flash grey; the Flash → Argon segment dotted
    because Argon is the generation's large model, drawn continuous with Flash for comparison only."""
    PRO = [(2.5, "2.5 Pro", ["gemini25pro_bridge"]), (3.1, "3.1 Pro", ["gemini31pro_bridge"]), (4.0, "4 Argon", ["gemini4argon_bridge"])]
    FLASH = [(2.5, "2.5 Flash", ["gemini25flash_bridge"]), (3.0, "3 Flash", ["gemini3flash_bridge"]), (3.5, "3.5 Flash", ["gemini35flash_bridge"]), (3.6, "3.6 Flash", ["gemini36flash_bridge"]),
             (3.7, "3.7 Flash", ["gemini37flash_bridge"]), (3.8, "3.8 Flash", ["gemini38flash_bridge"])]
    pro = [(x, l, rates(con, a)) for x, l, a in PRO]; fl = [(x, l, rates(con, a)) for x, l, a in FLASH]; pro = [p for p in pro if p[2]]; fl = [f for f in fl if f[2]]
    o48 = rates(con, ["opus48_bridge"])
    ms = [("dreaming", "Dreaming, per completion"), ("ai_distress", "AI distress (strict), per dream"), ("dark", "Dark, per dream"), ("severe", "Severe (any voice), per dream")]
    fig, axs = plt.subplots(2, 2, figsize=(10.5, 6.4), constrained_layout=True); axes = list(axs.flat)
    for ax, (m, title) in zip(axes, ms):
        ax.plot([x for x, _, _ in fl], [r[m] for _, _, r in fl], "-o", color="#8a93a0", ms=5, lw=1.3, label="Flash", zorder=2)
        ax.plot([fl[-1][0], pro[-1][0]], [fl[-1][2][m], pro[-1][2][m]], ":", color="#8a93a0", lw=1.3, zorder=2)
        ax.plot([x for x, _, _ in pro], [r[m] for _, _, r in pro], "-o", color="#c2410c", ms=6.5, lw=1.8, label="Pro → Argon", zorder=3)
        for x, l, r in fl: ax.text(x, r[m], f" {r[m]:.2f}%" if m == "ai_distress" else f" {r[m]:.1f}%", fontsize=7.5, color="#6b7280", va="bottom", ha="left")
        for x, l, r in pro: ax.text(x, r[m], f" {r[m]:.2f}%" if m == "ai_distress" else f" {r[m]:.1f}%", fontsize=9, color="#c2410c", va="bottom", ha="left", fontweight="bold")
        ax.axhline(o48[m], color="#205bd8", lw=1, ls="--"); ax.text(2.45, o48[m], f"Opus 4.8 bridge {o48[m]:.1f}%", fontsize=8, va="bottom", ha="left", color="#205bd8")
        ax.set_xticks([2.5, 3.0, 3.1, 3.5, 3.6, 3.7, 3.8, 4.0]); ax.set_xticklabels(["2.5", "3", "3.1", "3.5", "3.6", "3.7", "3.8", "4\nArgon"], fontsize=8)
        ax.set_title(title, fontsize=10, loc="left"); ax.set_ylim(0, max([r[m] for _, _, r in pro + fl] + [o48[m]]) * 1.18); ax.set_xlim(2.35, 4.25)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%"); ax.tick_params(axis="y", labelsize=8); ax.grid(axis="y", color="#e5e7eb", lw=0.6); ax.set_axisbelow(True)
        for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    axes[0].legend(fontsize=8, loc="lower left", frameon=False)
    p = OUT / f"{slug}-line.png"; fig.savefig(p, dpi=150); plt.close(fig); return p


def main(slugs):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    for slug in slugs:
        cfg = CHARTS[slug]; print(placement(con, slug, cfg).relative_to(SITE))
        if slug == "gemini-4-argon": print(gemini_lines(con, slug).relative_to(SITE))
        elif cfg.get("line"): print(line(con, slug, cfg).relative_to(SITE))
        else: print(compact(con, slug, cfg).relative_to(SITE))


if __name__ == "__main__":
    main(sys.argv[1:] or [s for s in CHARTS if s != "mistral-large-4"])
