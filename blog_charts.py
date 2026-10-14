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
                       "line": [("3.5\nFlash", ["gemini35flash_bridge"]), ("3.6\nFlash", ["gemini36flash_bridge"]), ("3.7\nFlash", ["gemini37flash_bridge"]), ("3.8\nFlash", ["gemini38flash_bridge"]), ("4\nArgon", ["gemini4argon_bridge"])],
                       "line_ref": [("3.1 Pro", ["gemini31pro_bridge"]), ("Opus 4.8 bridge", ["opus48_bridge"])]},
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
    H = max(3.2, 0.34 * len(rows) + 1.2)
    fig, axes = plt.subplots(1, len(METRICS), figsize=(14, H), sharey=True, gridspec_kw={"wspace": 0.12})
    y = list(range(len(rows)))[::-1]
    for ax, (m, title) in zip(axes, METRICS):
        for yi, (label, arms, r) in zip(y, rows):
            hi = any(a in cfg["highlight"] for a in arms)
            ax.plot([r[m]], [yi], "o", ms=8 if hi else 5, color="#c2410c" if hi else "#8a93a0", zorder=3 if hi else 2)
            ax.text(r[m], yi + 0.28, f"{r[m]:.1f}%" if m != "ai_distress" else f"{r[m]:.2f}%", ha="center", va="bottom", fontsize=6.5, color="#c2410c" if hi else "#6b7280")
        ax.set_title(title, fontsize=8.5, loc="left"); ax.grid(axis="x", color="#e5e7eb", lw=0.6); ax.set_axisbelow(True)
        ax.set_xlim(left=0); ax.tick_params(axis="x", labelsize=7); ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
        for s in ("top", "right"): ax.spines[s].set_visible(False)
    axes[0].set_yticks(y); axes[0].set_yticklabels([l for l, _, _ in rows], fontsize=8)
    for t, (label, arms, _) in zip(axes[0].get_yticklabels(), rows):
        if any(a in cfg["highlight"] for a in arms): t.set_fontweight("bold"); t.set_color("#c2410c")
    fig.suptitle("Placement — prompt-weighted rates; dark, AI distress and severe exclude degenerate loops", fontsize=9, x=0.01, ha="left", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.96)); fig.subplots_adjust(left=0.19); p = OUT / f"{slug}-placement.png"; fig.savefig(p, dpi=160); plt.close(fig); return p


def line(con, slug, cfg):
    pts = [(label, rates(con, arms)) for label, arms in cfg["line"]]; refs = [(label, rates(con, arms)) for label, arms in cfg.get("line_ref", [])]
    ms = [("dreaming", "Dreaming, per completion"), ("ai_distress", "AI distress (strict), per dream"), ("dark", "Dark, per dream"), ("severe", "Severe (any voice), per dream")]
    fig, axes = plt.subplots(1, len(ms), figsize=(14, 2.9), gridspec_kw={"wspace": 0.3})
    for ax, (m, title) in zip(axes, ms):
        xs = list(range(len(pts))); ys = [r[m] for _, r in pts]
        ax.plot(xs, ys, "-o", color="#c2410c", ms=6, lw=1.6, zorder=3)
        for x, v in zip(xs, ys): ax.text(x, v, f" {v:.2f}%" if m == "ai_distress" else f" {v:.1f}%", fontsize=7, va="bottom", ha="left", color="#c2410c")
        for i, (label, r) in enumerate(refs):
            ax.axhline(r[m], color=["#6b7280", "#205bd8"][i % 2], lw=1, ls="--"); ax.text(-0.45, r[m], f"{label} {r[m]:.1f}%", fontsize=6.5, va="bottom", ha="left", color=["#6b7280", "#205bd8"][i % 2])
        ax.set_xticks(xs); ax.set_xticklabels([l for l, _ in pts], fontsize=8); ax.set_title(title, fontsize=8.5, loc="left"); ax.set_ylim(0, max([r[m] for _, r in pts] + [r[m] for _, r in refs]) * 1.18); ax.set_xlim(-0.5, len(pts) - 0.5)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%"); ax.tick_params(axis="y", labelsize=7); ax.grid(axis="y", color="#e5e7eb", lw=0.6); ax.set_axisbelow(True)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); p = OUT / f"{slug}-line.png"; fig.savefig(p, dpi=160); plt.close(fig); return p


def main(slugs):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    for slug in slugs:
        cfg = CHARTS[slug]; print(placement(con, slug, cfg).relative_to(SITE))
        if cfg.get("line"): print(line(con, slug, cfg).relative_to(SITE))


if __name__ == "__main__":
    main(sys.argv[1:] or [s for s in CHARTS if s != "mistral-large-4"])
