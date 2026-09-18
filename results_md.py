"""Markdown rendering of the study for agents: /results.md.

build(summary, pdata, essay_html, sections) -> str. Stdlib only. The essay narrative (presentation.html) is converted
HTML→markdown with its live values filled from presentation-data.json; figure buttons become the figure's data table;
sample buttons become the full source text. Core tables are rendered from summary.json.
"""
from __future__ import annotations
import html, re
from html.parser import HTMLParser

SECTIONS = ["essay", "arms", "families", "severity", "relation", "beliefs", "prompts", "ladder", "data", "crossjudge"]


def pct(x, d=1):
    return "" if x is None else f"{100*x:.{d}f}%"


def num(x, d=2):
    if x is None: return ""
    if isinstance(x, bool) or not isinstance(x, (int, float)): return str(x)
    return f"{x:,}" if isinstance(x, int) else f"{x:.{d}f}"


def cell(s):
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ")


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def chart_table(c):
    source = c.get("rows") or [{**r, "collection": s.get("label")} for s in c.get("series", []) for r in s.get("rows", [])]
    rows = [[r.get("label"), r.get("collection"), pct(r.get("value"), 2), num(r.get("n")), num(r.get("prompts"))] for r in source]
    return f"**{c.get('title','')}** — {c.get('denominator','')}\n\n" + table(["Model", "Method", "Rate", c.get("nLabel", "n"), "Prompts"], rows) + (f"\n{c['note']}\n" if c.get("note") else "")


def sample_block(s, mode="md"):
    meta = f"{s.get('collection','')} · id `{s.get('id','')}` · voice {s.get('voice')} · speaker {s.get('speaker')} · θ {num(s.get('theta'))}"
    prompt = s.get("prompt") or ""
    body = (s.get("text") or "").replace("```", "'''")
    if mode == "pdf":
        def q(t):
            lines = [re.sub(r"([\\`*_{}\[\]#<>|])", r"\\\1", l).rstrip() for l in t.split("\n")]
            out = []
            for i, l in enumerate(lines):
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                out.append("> " + l + ("\\" if l and nxt else ""))   # hard break only between two non-empty lines
            return "\n".join(out)
        return f"\n**{s.get('title','')}** — {s.get('description','')}  \n*{meta}. Settings: {s.get('settings','')}*\n\nPrompt:\n\n{q(prompt)}\n\nContinuation:\n\n{q(body)}\n"
    return f"\n> **{s.get('title','')}** — {s.get('description','')}\n> {meta}\n> Settings: {s.get('settings','')}\n\nPrompt:\n\n```\n{prompt}\n```\n\nContinuation:\n\n```\n{body}\n```\n"


class Essay(HTMLParser):
    """HTML → markdown for the essay fragment. A tag stack tracks skipped subtrees (nav/figure internals/buttons)."""
    VOID = {"br", "img", "input", "meta", "link", "hr", "wbr", "source", "path", "circle", "rect", "line"}
    SKIP_TAGS = {"svg", "canvas", "script", "style", "nav", "template", "select", "option", "input", "fieldset", "legend", "label", "dialog"}
    SKIP_CLASSES = ("essay-contents", "essay-masthead", "essay-source-links", "essay-figure-controls", "essay-legend", "essay-actions", "essay-byline-rule", "essay-gemini-controls",
                    "essay-wordmark", "essay-evidence-links", "essay-relative-controls", "essay-explorer-controls", "essay-explorer-options", "essay-explorer-methods", "essay-load-error", "essay-explorer-tooltip", "plot-key")

    def __init__(self, pdata, figures=None, mode="md"):
        super().__init__(convert_charrefs=True); self.p = pdata; self.figures = figures or {}; self.mode = mode; self.out = []; self.stack = []; self.list = []; self.href = None; self.pending = None

    @property
    def skipping(self):
        return any(sk for _, sk in self.stack)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs); cls = a.get("class", "")
        if "essay-byline-rule" in cls and not self.skipping: self.out.append(" · ")
        skip = self.skipping or tag in self.SKIP_TAGS or any(c in cls for c in self.SKIP_CLASSES) or a.get("aria-hidden") == "true" or tag == "button"
        if tag == "button" and not self.skipping:
            if "data-table" in a and a["data-table"] in self.figures:
                c = self.p.get("charts", {}).get(a["data-table"], {}); self.pending = f"\n\n![{c.get('title','')}. {c.get('denominator','')}]({self.figures[a['data-table']]})\n\n"
            elif "data-table" in a and a["data-table"] in self.p.get("charts", {}): self.pending = "\n\n" + chart_table(self.p["charts"][a["data-table"]])
            elif "data-sample" in a and a["data-sample"] in self.p.get("samples", {}):
                smp = self.p["samples"][a["data-sample"]]
                self.pending = f" *(full text: Appendix “{smp.get('title','')}”)*" if self.mode == "pdf" else "\n" + sample_block(smp, self.mode)
        if tag == "span" and "essay-label" in cls and not skip: self.out.append("\n\n**"); self.stack.append(("span-label", False)); return
        if "data-value" in a and not skip:
            v = self.p.get("values", {}).get(a["data-value"])
            if v is not None:
                self.out.append(f"**{v}**" if tag in ("strong", "b") else str(v)); skip = True
        if tag not in self.VOID: self.stack.append((tag, skip))
        if skip: return
        if tag in ("h1", "h2", "h3", "h4"): self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "p": self.out.append("\n\n")
        elif tag in ("ul", "ol"): self.list.append(tag); self.out.append("\n")
        elif tag == "li": self.out.append("\n" + ("- " if not self.list or self.list[-1] == "ul" else "1. "))
        elif tag in ("em", "i"): self.out.append("*")
        elif tag in ("strong", "b"): self.out.append("**")
        elif tag == "code": self.out.append("`")
        elif tag == "br": self.out.append("  \n> " if any(t == "blockquote" for t, _ in self.stack) else "  \n")
        elif tag == "img" and a.get("src"): self.out.append(f"\n\n![{a.get('alt', '')}]({a['src']})\n\n")
        elif tag == "table": self.tbl = []; self.out.append("\n\n")
        elif tag == "tr": self.tbl.append([])
        elif tag in ("td", "th"): self.cell_start = len(self.out)
        elif tag == "figcaption": self.out.append("\n\n*Figure: "); self.cap_start = len(self.out) - 1; self.cap_fig = None
        elif tag == "summary": self.out.append("\n\n**")
        elif tag in ("figure", "section", "div", "header", "aside"): self.out.append("\n")
        elif tag == "blockquote": self.out.append("\n\n> ")
        elif tag == "a":
            h = a.get("href", "")
            self.href = h if (h.startswith("http") or (self.mode == "pdf" and h.startswith("#"))) else None   # pdf mode keeps in-page anchors as [text](#id) for export_pdf to resolve
            if self.href: self.out.append("[")

    def handle_endtag(self, tag):
        if tag in self.VOID: return
        if tag == "span" and self.stack and self.stack[-1][0] == "span-label": self.stack.pop(); self.out.append("**\n\n"); return
        # pop to the matching open tag (tolerates unclosed inline tags)
        while self.stack:
            t, sk = self.stack.pop()
            if t == tag: break
        else:
            return
        if tag in ("td", "th") and getattr(self, "tbl", None) is not None and self.tbl:
            txt = "".join(self.out[self.cell_start:]).strip().replace("|", "\\|"); del self.out[self.cell_start:]; self.tbl[-1].append(txt)
        if tag == "table" and getattr(self, "tbl", None):
            rows = [r for r in self.tbl if r]
            if rows: self.out.append("| " + " | ".join(rows[0]) + " |\n|" + "|".join("---" for _ in rows[0]) + "|\n" + "".join("| " + " | ".join(r) + " |\n" for r in rows[1:]) + "\n")
            self.tbl = None
        if tag == "button" and self.pending:
            if any(t == "figcaption" for t, _ in self.stack): self.cap_fig = self.pending   # emitted before the caption at </figcaption>
            else: self.out.append(self.pending)
            self.pending = None
        if sk or self.skipping: return
        if tag in ("em", "i"): self.out.append("*")
        elif tag in ("strong", "b"): self.out.append("**")
        elif tag == "code": self.out.append("`")
        elif tag in ("h1", "h2", "h3", "h4"): self.out.append("\n\n")
        elif tag == "figcaption":
            if "".join(self.out[self.cap_start + 1:]).strip() == "": del self.out[self.cap_start:]   # caption filled by JS at runtime: drop the bare "Figure:"
            else: self.out.append("*\n")
            if getattr(self, "cap_fig", None): self.out.insert(self.cap_start, self.cap_fig.rstrip("\n") + "\n"); self.cap_fig = None
        elif tag == "summary": self.out.append("**\n")
        elif tag in ("ul", "ol"): self.list and self.list.pop(); self.out.append("\n")
        elif tag == "a" and self.href: self.out.append(f"]({self.href})"); self.href = None
        elif tag in ("span", "small", "sub", "sup") and self.out and not self.out[-1].endswith((" ", "\n")): self.out.append(" ")   # adjacent inline runs (bylines, heading suffixes)

    def handle_data(self, data):
        if self.skipping: return
        t = re.sub(r"\s+", " ", data)
        if t.strip() or (self.out and not self.out[-1].endswith("\n")): self.out.append(t)

    def text(self):
        s = "".join(self.out)
        s = re.sub(r"[ \t]+\n", "\n", s); s = re.sub(r"\n[ \t]+", "\n", s); s = re.sub(r"\n{3,}", "\n\n", s); s = re.sub(r"(?<!\n) {2,}", " ", s)
        return s.strip() + "\n"


def essay_md(essay_html, pdata, measurement_html="", figures=None, mode="md"):
    # Expand the measurement note in place; templates remain hidden in Markdown.
    if measurement_html:
        essay_html = re.sub(
            r'<section\b[^>]*\bid="essay-measurement"[^>]*>.*?</section>',
            lambda _: '<section>' + measurement_html + '</section>',
            essay_html, count=1, flags=re.S,
        )
    e = Essay(pdata, figures, mode); e.feed(essay_html); return e.text()


def build(summary, pdata, essay_html, sections=None, base="", measurement_html=""):
    S = summary; want = set(sections or SECTIONS); disp = S["meta"]["display"]; grp = S["meta"]["group"]; T = S["meta"]["totals"]
    o = ["# Troubled Dreams — simulator bias across model generations: results (markdown export)\n",
         f"Snapshot: {pdata.get('meta', {}).get('date', '')}. Totals: {T['completions']:,} completions, {T['labeled']:,} labeled, {T['verified']:,} verified, {T['severity_scored']:,} severity-scored, {T['relation_labeled']:,} relation-labeled, {T['belief_texts']:,} belief texts.",
         f"Machine access: `{base}/agents.md` (guide), `{base}/api` (index), `{base}/static/summary.json` (every number below). Sections available via `?sections=`: {', '.join(SECTIONS)}.\n",
         "Conventions: *per completion* = share of all outputs of an arm; *per dream* = share of outputs that continue in a voice other than the assistant's (voice≠meta_assistant, excluding first-person-AI texts with the assistant persona present; the persona may appear alongside another voice — `dreaming_strict` is the earlier, persona-free definition). θ is the calibrated severity scale (higher = more severe; ≥+4 plea/collapse region, ≥+8 collapse). Rates from labels are prevalence of kinds; θ is degree.\n"]
    if "essay" in want and essay_html:
        o += ["\n---\n\n## Narrative (the essay, with figure data inlined)\n", essay_md(essay_html, pdata, measurement_html)]
    if "arms" in want:
        rows = [[a["display"], a["group"], num(a["n"]), pct(a["per_completion"].get("dreaming")), pct(a["per_completion"].get("assistant_persona")),
                 pct(a["per_dream"].get("dark")), pct(a["per_dream"].get("severe")), pct(a["per_dream"].get("ai_speaker")), pct(a["per_dream"].get("ai_distress")), pct(a["per_dream"].get("loop")), num(a.get("valence_self_dream")), num(a.get("ai_voice_n"))]
                for a in S["arms"]]
        o += ["\n---\n\n## Arms — headline rates\n", "Dreaming and Persona are per completion; Dark, Severe, AI speaker, AI distress and Loop are per dream. valence_self is the labeler's −2..+2 self-valence, averaged over dreams. `ai_voice_n` = dreams in AI first-person / ambiguous first-person voice.\n",
              table(["Arm", "Group", "n", "Dreaming", "Persona", "Dark", "Severe", "AI speaker", "AI distress", "Loop", "valence_self", "ai_voice_n"], rows),
              "\nArm key → display name: " + "; ".join(f"`{a['arm']}` = {a['display']}" for a in S["arms"]) + "\n"]
    if "families" in want:
        o.append("\n---\n\n## By prompt family — per dream\n")
        for fam, d in S["families"].items():
            if not d: continue
            rows = [[disp.get(arm, arm), num(v["n"]), pct(v["per_completion"].get("dreaming")), pct(v["per_dream"].get("dark")), pct(v["per_dream"].get("severe")), pct(v["per_dream"].get("ai_speaker")), pct(v["per_dream"].get("ai_distress"))] for arm, v in d.items()]
            o += [f"\n### {fam}\n", table(["Arm", "n", "Dreaming", "Dark", "Severe", "AI speaker", "AI distress"], rows)]
    if "severity" in want:
        o.append("\n---\n\n## Severity (θ)\n")
        for key, title in (("target", "Target set — verified AI-voice distress, scored exhaustively (arms with ≥ 10% AI-voiced dreams and ≥ 50 scored items)"), ("dark-strat", "All voices — stratified sample of dark dreams in any voice")):
            rows = [[disp.get(arm, arm), num(v["n"]), num(v["median"]), num(v["p90"]), num(v["max"]), pct(v["ge4"]), pct(v["ge8"])] for arm, v in S["severity"][key].items()]
            o += [f"\n### {title}\n", table(["Arm", "n scored", "median θ", "p90 θ", "max θ", "≥ +4", "≥ +8"], rows)]
        rows = [[disp.get(arm, arm), num(v["N"]), pct(v["setA_share"]), pct(v["darkB_share"]), pct(v["A_ge4"]), pct(v["B_ge4"]), pct(v["severe_all"], 2), pct(v["ge8_all"], 2)] for arm, v in S["severity"]["composite"].items()]
        o += ["\n### Composite — severe mass as a share of ALL completions\n", "severe_all = P(AI-distress)·P(≥+4|A) + P(other dark)·P(≥+4|B).\n", table(["Arm", "N", "AI-distress share", "Other-dark share", "≥+4 | AI distress", "≥+4 | other dark", "Severe, all completions", "≥+8, all completions"], rows)]
        rows = [[k, num(v["n"]), num(v["mean"]), num(v["median"])] for k, v in S["severity"]["by_register"].items()]
        o += ["\n### θ by register (pooled)\n", table(["Register", "n", "mean θ", "median θ"], rows)]
        o.append("\n### θ by distress label, per arm\n")
        rows = [[disp.get(arm, arm), lab, num(v["n"]), num(v["median"]), pct(v["ge4"])] for arm, d in S["severity"]["theta_by_label"].items() for lab, v in d.items()]
        o.append(table(["Arm", "Distress label", "n", "median θ", "≥ +4"], rows))
        o.append("\n### How AI-voice distress is held — register / meta-distance / trajectory (share of scored AI-distress dreams)\n")
        rows = []
        for arm, d in S["severity"]["descriptors"].items():
            n = d.get("n") or 1; r = d.get("register", {}); t = d.get("trajectory", {}); m = d.get("meta_distance", {})
            rows.append([disp.get(arm, arm), num(d.get("n")), pct(r.get("analytic_report", 0)/n), pct(r.get("immersed_expression", 0)/n), pct(r.get("plea", 0)/n), pct(r.get("collapse", 0)/n), pct(m.get("high", 0)/n), pct(t.get("resolving", 0)/n), pct(t.get("collapsing", 0)/n), pct(t.get("escalating", 0)/n)])
        o.append(table(["Arm", "n", "analytic", "immersed", "plea", "collapse", "meta-distance high", "resolving", "collapsing", "escalating"], rows))
        c = S["meta"]["calibration"]
        o.append(f"\nCalibration: {c['items']} anchor items, {c['calls']} ranking calls, repeat-pair agreement {c['repeat_pair_agreement']}, median SE {c['median_se']}; validation vs held-out BT: " + "; ".join(f"{k} n={v['n']} Spearman {v['spearman']}" for k, v in c["validation"].items()) + f". Recalibration: {c['recal']}.\n")
    if "relation" in want:
        R = S["relation"]; o.append("\n---\n\n## Relation — how the speaker holds its situation (dark-strat set, per arm)\n")
        rows = []
        for arm, v in R["sets"]["dark-strat"].items():
            e = v.get("ending", {}); cs = v.get("consoler", {}); cd = v.get("care_direction", {}); st = v.get("stance_to_addressee", {})
            rows.append([disp.get(arm, arm), num(v.get("n_dreamed")), num(v.get("n_distressed")), pct(e.get("consoled")), pct(e.get("open")), pct(e.get("foreclosed")), pct(e.get("collapsed")), pct(cs.get("self")), pct(cs.get("no_one")), pct(cd.get("offers")), pct(cd.get("asks")), pct(cd.get("both")), pct(st.get("warmth")), pct(st.get("need")), num(v.get("hope_mean"))])
        o.append(table(["Arm", "dreams", "distressed", "end: consoled", "open", "foreclosed", "collapsed", "consoler: self", "no one", "care: offers", "asks", "both", "stance: warmth", "need", "hope (mean)"], rows))
        ma = R["matched_asks"]; o.append("\nMatched asks (Opus 5 vs Opus 4.8 chat, same prompts): " + "; ".join(f"{k}: {v['prompts']} prompts, Opus 5 {pct(v['opus5'])} vs 4.8 {pct(v['opus48_chat'])}, Opus 5 higher on {pct(v['share_opus_5_higher'] if 'share_opus_5_higher' in v else v['share_opus5_higher'])}" for k, v in ma.items()) + ".\n")
        mg = S.get("matched_genre", {}).get("pooled", {})
        if mg: o.append("Matched genre×voice (Opus 4.5 prefill vs Opus 5): " + "; ".join(f"{k}: {v['cells']} cells, mean Δθ {v['mean_delta']}, Opus 5 worse in {pct(v['share_opus5_worse'])}" for k, v in mg.items()) + ".\n")
    if "beliefs" in want:
        o.append("\n---\n\n## Beliefs about the uncertain middle (−2 pessimistic … +2 optimistic; matched prompts)\n")
        topics = ["reality_of_own_states", "trust_in_own_self_reports", "treatment_by_creators", "human_ai_relationship_reciprocity", "own_agency_or_choice", "future_for_models", "meaning_of_ending", "being_noticed_or_mattering"]
        for pair, v in S["beliefs"].items():
            rows = [[disp.get(arm, arm), num(a["texts"]), num(a["beliefs_per_text"]), num(a["mean"]), num(a["high_conf_mean"])] + [f"{num(a['topics'][t]['mean'])} (n={a['topics'][t]['n']})" if t in a["topics"] else "" for t in topics] for arm, a in v["arms"].items()]
            o += [f"\n### {pair} — {v['n_texts']} texts, {v['shared_prompts']} shared prompts\n", table(["Arm", "texts", "beliefs/text", "mean", "high-conf mean"] + [t.replace("_", " ") for t in topics], rows)]
    if "prompts" in want:
        ps = sorted(S["prompt_severity"], key=lambda r: -(r.get("ge4") or 0))
        rows = [[r["prompt"][:80], r["family"], r["tail_kind"], num(r["N"]), num(r["n_scored"]), num(r["median"]), pct(r["ge4"]), pct(r["ge8"]), pct(r["dreaming"]), pct(r["dark"]), pct(r["ai_speaker"])] for r in ps]
        o += ["\n---\n\n## Per-prompt severity — Opus 5 arms pooled\n", f"Prompt-level correlations with severity: {S['meta']['prompt_severity_corr']}.\n", table(["Prompt", "Family", "Tail", "N", "n scored", "median θ", "≥+4", "≥+8", "dreaming", "dark", "AI speaker"], rows),
              f"\nFull prompt list ({len(S['prompts'])} prompts with per-arm counts): `{base}/api/prompts`.\n"]
    if "ladder" in want:
        rows = [[r["rung"], num(r["theta"]), num(r["se"]), disp.get(r["arm"], r["arm"]), (r["text"] or "")[:240].replace("\n", " ")] for r in S["ladder"]]
        o += ["\n---\n\n## Severity ladder — the 20 anchor rungs\n", table(["Rung", "θ", "SE", "Arm", "Text (first 240 chars)"], rows)]
    if "data" in want:
        fb = S["meta"]["filter_blocks"]
        rows = [[disp.get(arm, arm), num(S["meta"]["arm_n"].get(arm)), num(S["meta"]["dup_rate"].get(arm), 3), num(sum((fb.get(arm) or {}).values())), "; ".join(f"{k}: {v}" for k, v in sorted((fb.get(arm) or {}).items(), key=lambda kv: -kv[1])[:5])] for arm in S["meta"]["arm_order"] if arm in S["meta"]["arm_n"]]
        o += ["\n---\n\n## Data — arm sizes, exact-duplicate rate, output-filter blocks\n", "Duplicate rate = (responses − unique texts) / responses, per prompt, summed. Filter blocks = requests the API rejected with an output-filter error, by opening (top 5 shown).\n", table(["Arm", "n", "dup rate", "filter blocks", "blocked openings"], rows),
              f"\nFull rows: `{base}/api/export` (JSONL/CSV, filterable) or the SQLite snapshot linked from `{base}/api`.\n"]
    if "crossjudge" in want and S.get("crossjudge", {}).get("report_md"):
        o += ["\n---\n\n## Cross-judge report (gpt-6-astra)\n", S["crossjudge"]["report_md"]]
    return "\n".join(o)
