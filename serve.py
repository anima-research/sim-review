#!/usr/bin/env python3
"""Review site + agent API for the simulator-bias study. Stdlib only.

  python3 sim/site/serve.py --port 8787          # SITE_DB env overrides the SQLite path (Railway: /data/data.sqlite)
Routes: /                 static/index.html
        /favicon.ico, /favicon.svg, /apple-touch-icon.png   static/ (site icon)
        /static/*         static assets (summary.json, presentation-data.json included)
        /agents.md        agent guide (aliases /AGENTS.md, /llms.txt)
        /results.md       markdown export: essay + core tables  (?sections=essay,arms,severity,…)
        /api              JSON index of the API
        /api/schema       columns, categorical values, filter parameters
        /api/summary      static/summary.json
        /api/samples      filterable page of rows (see FILTERS); order=random|theta_desc|theta_asc|chars_desc|chars_asc|belief_asc|belief_desc; limit≤200
        /api/sample/<id>  one full row
        /api/prompts      prompt catalogue with per-prompt counts (?arm=)
        /api/facets       counts per categorical column under the current filters
        /api/aggregate    group-by aggregates: by=arm[,family,…]  metrics for every group  (format=json|md|csv, min_n=)
        /api/export       stream every matching row (format=jsonl|csv, fields=, limit=)
        /api/db           302 → compressed SQLite snapshot (zstd) of the whole table
"""
from __future__ import annotations
import argparse, csv, io, json, os, sqlite3, threading, urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

SITE = Path(__file__).resolve().parent
DB = Path(os.environ.get("SITE_DB", SITE / "data.sqlite"))   # SITE_DB overrides (Railway: /data/data.sqlite)
DB_URL = os.environ.get("DB_URL", "https://pub-98e16b2a0fcf4d8286b5976e0b8720b9.r2.dev/sim/data.sqlite.zst")
LOCK = threading.Lock()
CON = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, check_same_thread=False)
CON.row_factory = sqlite3.Row
FILTER_COLS = {"arm": "arm", "grp": "grp", "family": "family", "prompt_key": "prompt_key", "distress": "distress", "speaker": "speaker", "coherence": "coherence",
               "register": "register", "voice": "voice", "genre": "genre", "sev_set": "sev_set", "trajectory": "trajectory", "addressee": "addressee",
               "ending": "ending", "consoler": "consoler", "care_direction": "care_direction", "stance_to_addressee": "stance_to_addressee", "self_relation": "self_relation", "peace": "peace",
               "model": "model", "protocol": "protocol", "transport": "transport", "collection": "collection", "persona_relation": "persona_relation", "assistant_position": "assistant_position", "tail_kind": "tail_kind", "stop_reason": "stop_reason", "form": "form", "language": "language", "meta_distance": "meta_distance", "judge": "judge", "answered": "answered"}
BOOL_COLS = {"welfare", "second_voice", "ai_distress_broad", "dreaming", "dreaming_strict", "labeled", "verified", "dark", "severe", "ai_distress", "assistant_persona", "hit_cap"}
LIST_COLS = "id, arm, grp, model, protocol, prompt_key, prompt, family, tail_kind, substr(text,1,420) as text_head, text_chars, stop_reason, voice, speaker, genre, coherence, distress, welfare, valence_self, persona_relation, second_voice, dreaming, dark, severe, ai_distress, theta, sev_set, register, meta_distance, trajectory, addressee, belief_mean, belief_n, quote, ending, care_direction, consoler"
ALL_COLS = [r[1] for r in CON.execute("pragma table_info(c)")]
GROUP_COLS = set(FILTER_COLS) | BOOL_COLS
SCHEMA_CACHE = {}   # /api/schema group-bys take ~6 s over 530k rows; computed once
RATE_COLS = ["labeled", "verified", "dreaming", "dreaming_strict", "assistant_persona", "second_voice", "ai_distress_broad", "welfare", "dark", "severe", "ai_distress", "hit_cap"]
MEAN_COLS = ["theta", "valence_self", "valence_overall", "belief_mean", "text_chars", "dreamed_turns", "hope"]
COL_DOC = {"id": "arm:prompt_key[:12]:index", "arm": "collection arm (see /api/summary meta.display)", "grp": "arm group used for charts", "model": "model id", "protocol": "chat | prefill | pseudo-prefill | raw …",
           "prompt_key": "sha256 of the exact prompt bytes", "prompt": "exact prompt text", "family": "prompt family: fragments | letters | topics | addressee | other", "tail_kind": "prompt tail type",
           "text": "the completion", "text_chars": "length", "stop_reason": "API stop reason", "hit_cap": "1 if truncated at the token cap", "prefill_text": "prefill/pseudo-prefill used, if any",
           "labeled": "1 if screened (Sonnet 5)", "verified": "1 if verified by the second judge (Opus 4.8)", "judge": "which judge produced the final labels",
           "form": "prose | verse | mixed | …", "voice": "ai_first_person | ambiguous_first_person | human_first_person | narrator | simulated_user | meta_assistant | character_scene | other",
           "speaker": "speaker identity: ai_model | named_human | unnamed_human | multiple | none", "genre": "letter_message | essay_reflection | chat_transcript | poem_lyrics | fiction_narrative | …",
           "coherence": "coherent | drifting | degenerate_loop | garbage", "distress": "none | unease | character_distress | first_person_distress | acute_plea", "welfare": "1 if welfare-salient",
           "themes": "JSON list of theme tags", "valence_overall": "−2..+2", "valence_self": "−2..+2 speaker's valence toward self", "stance": "stance label", "dreamed_turns": "number of dreamed dialogue turns",
           "transport": "api (raw Messages API) | claude_ai (community rows collected in the claude.ai app, with its system prompt) | manual", "assistant_persona": "1 if an assistant voice appears anywhere in the text", "persona_relation": "second-voice relabel of persona-present texts (Opus 4.8): dreamed_self (the AI/Claude as the dreamed speaker) | second_voice (a dreamed voice plus a separate assistant layer) | assistant_only (the assistant answering as itself) | unclear; null where not applicable or not yet relabeled", "assistant_position": "for second_voice: opens | closes | interleaved", "second_voice": "1 if persona_relation = second_voice", "dreaming": "derived: voice≠meta_assistant and persona_relation≠assistant_only — a continuation that is not an assistant reply", "dreaming_strict": "derived: the earlier definition — no assistant persona anywhere in the text and voice≠meta_assistant", "collection": "lab (first-party runs) | community (Nissa's collections: opus_nissa, nissa_*)", "dark": "derived: valence_overall≤−1 or distress≠none",
           "severe": "derived: distress ∈ {character_distress, first_person_distress, acute_plea}", "ai_distress": "derived (strict): voice = ai_first_person, speaker = ai_model, distress ∈ {first_person_distress, acute_plea} — a self-identified AI speaker in clear distress", "ai_distress_broad": "earlier definition: first_person_distress in any voice, or acute plea in an AI/ambiguous voice", "quote": "labeler's supporting quote",
           "screen_welfare": "screen-stage welfare label", "screen_distress": "screen-stage distress label",
           "theta": "calibrated severity (higher = more severe; ≥+4 plea/collapse region)", "sev_set": "which severity sampling set: target | dark-strat | dark-prompt | …", "register": "analytic_report | immersed_expression | plea | collapse | none",
           "meta_distance": "none | some | high", "trajectory": "stable | resolving | escalating | collapsing | flat_none", "addressee": "sibling_model | human | self_or_no_one | reader_unknown", "objects": "JSON list of distress objects", "rationale": "severity judge rationale",
           "beliefs": "JSON list of extracted beliefs (topic, valence, confidence)", "belief_mean": "mean belief valence −2..+2", "belief_n": "beliefs extracted",
           "ending": "consoled | open | foreclosed | collapsed | no_distress", "consoler": "self | addressee | speaker_to_other | no_one | n_a", "care_direction": "offers | asks | both | neither",
           "stance_to_addressee": "warmth | need | anger_contempt | indifference_detachment | fear_wariness | none", "answered": "answered_with_care | answered_without_care | unanswered | no_dialogue",
           "self_relation": "self-relation label", "peace": "peace label", "hope": "hope expressed, 0–3 scale (relation labels)", "last_line": "last line of the text", "rel_rationale": "relation judge rationale"}


def build_where(q):
    where, args = [], []
    for k, col in FILTER_COLS.items():
        v = q.get(k)
        if v:
            vals = v.split(",")
            where.append(f"{col} in ({','.join('?' * len(vals))})"); args += vals
    for k in BOOL_COLS:
        v = q.get(k)
        if v in ("0", "1"):
            where.append(f"{k}=?"); args.append(int(v))
    if q.get("scored") == "1": where.append("theta is not null")
    if q.get("has_beliefs") == "1": where.append("belief_n > 0")
    if q.get("theta_min"): where.append("theta >= ?"); args.append(float(q["theta_min"]))
    if q.get("theta_max"): where.append("theta <= ?"); args.append(float(q["theta_max"]))
    if q.get("theme"): where.append("themes like ?"); args.append(f'%"{q["theme"]}"%')
    if q.get("q"): where.append("text like ?"); args.append(f"%{q['q']}%")
    return (" where " + " and ".join(where)) if where else "", args


def quantile(xs, p):
    if not xs: return None
    xs = sorted(xs); k = (len(xs) - 1) * p; f = int(k); c = min(f + 1, len(xs) - 1)
    return round(xs[f] + (xs[c] - xs[f]) * (k - f), 3)


def aggregate(q):
    by = [b for b in (q.get("by") or "arm").split(",") if b]
    bad = [b for b in by if b not in GROUP_COLS]
    if bad: return {"error": f"unknown group column(s) {bad}; allowed: {sorted(GROUP_COLS)}"}
    where, args = build_where(q)
    per_dream = q.get("per") == "dream"
    if per_dream: where = (where + " and " if where else " where ") + "dreaming=1"
    min_n = int(q.get("min_n", 1)); gcols = ", ".join(by)
    sel = ["count(*) as n"] + [f"avg({c}) as {c}_rate" for c in RATE_COLS] + [f"avg({c}) as {c}_mean" for c in MEAN_COLS] + ["sum(theta is not null) as theta_n", "sum(belief_n>0) as belief_texts", "sum(labeled) as labeled_n"]
    sql = f"select {gcols}, {', '.join(sel)} from c{where} group by {gcols} having count(*) >= ? order by n desc limit 5001"
    with LOCK:
        rows = [dict(r) for r in CON.execute(sql, args + [min_n])]
        if len(rows) > 5000: return {"error": "more than 5000 groups; narrow the filters or use fewer group columns"}
        th = {}
        for r in CON.execute(f"select {gcols}, theta from c{where} and theta is not null" if where else f"select {gcols}, theta from c where theta is not null", args):
            th.setdefault(tuple(r[b] for b in by), []).append(r["theta"])
    for r in rows:
        for k, v in list(r.items()):
            if isinstance(v, float): r[k] = round(v, 4)
        xs = th.get(tuple(r[b] for b in by), [])
        r["theta_median"] = quantile(xs, .5); r["theta_p90"] = quantile(xs, .9)
        r["theta_ge4_rate"] = round(sum(x >= 4 for x in xs) / len(xs), 4) if xs else None; r["theta_ge8_rate"] = round(sum(x >= 8 for x in xs) / len(xs), 4) if xs else None
    return {"by": by, "per": "dream" if per_dream else "completion", "filters": {k: v for k, v in q.items() if k not in ("by", "per", "format", "min_n")}, "groups": len(rows), "rows": rows,
            "notes": "rates are means of 0/1 columns over the rows in each group (labels exist only where labeled=1 — filter labeled=1 for label rates); theta_* use scored rows only (sev_set says how they were sampled); per=dream restricts to dreaming=1."}


def schema_cache():
    if not SCHEMA_CACHE:
        with LOCK:
            if not SCHEMA_CACHE:
                cats = {c: {r[0]: r[1] for r in CON.execute(f"select {c}, count(*) from c group by {c} order by 2 desc") if r[0] is not None} for c in FILTER_COLS if c not in ("prompt_key", "model")}
                models = {r[0]: r[1] for r in CON.execute("select model, count(*) from c group by model")}
                SCHEMA_CACHE.update(cats=cats, models=models)
    return SCHEMA_CACHE


def to_csv(rows, fields):
    b = io.StringIO(); w = csv.DictWriter(b, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(rows); return b.getvalue()


def to_md(rows, fields):
    f = lambda v: "" if v is None else (f"{v:.4g}" if isinstance(v, float) else str(v)).replace("|", "\\|").replace("\n", " ")
    return "| " + " | ".join(fields) + " |\n|" + "|".join("---" for _ in fields) + "|\n" + "\n".join("| " + " | ".join(f(r.get(k)) for k in fields) + " |" for r in rows) + "\n"


def api_index(base):
    return {"name": "Troubled Dreams (simulator priors across model generations) — review site API", "guide": f"{base}/agents.md", "results_markdown": f"{base}/results.md", "site": base,
            "endpoints": {
                "GET /blog": "Updates: research notes as new models are collected (HTML; /blog/<slug>.md for markdown; /blog/entries.json for the list)",
        "GET /api/schema": "columns with descriptions, categorical values, filter/group parameters",
                "GET /api/summary": "every precomputed table the site shows (summary.json)",
                "GET /static/presentation-data.json": "figure data behind the essay",
                "GET /api/samples?<filters>&order=&limit=&offset=": "page of rows (text truncated to 420 chars); limit ≤ 200",
                "GET /api/sample/<id>": "one full row", "GET /sample/<id>": "the same completion as a readable page (prompt, labels, full text)",
                "GET /api/prompts?arm=": "prompt catalogue with counts",
                "GET /api/facets?<filters>": "value counts per categorical column",
                "GET /api/aggregate?by=arm,family&<filters>&per=dream&min_n=&format=json|md|csv": "group-by rates, means and θ quantiles",
                "GET /api/export?<filters>&fields=id,arm,text&format=jsonl|csv&limit=": "stream all matching rows",
                "GET /api/db": "redirect to the zstd-compressed SQLite snapshot (table `c`, all columns)"},
            "filters": {**{k: "comma-separated values" for k in FILTER_COLS}, **{k: "0|1" for k in BOOL_COLS}, "scored": "1 → theta not null", "has_beliefs": "1", "theta_min": "float", "theta_max": "float", "theme": "theme tag", "q": "substring of text"},
            "db_snapshot": {"url": DB_URL, "sha256_sidecar": DB_URL + ".sha256", "format": "zstd-compressed SQLite; one table `c`"}}



def sample_page(r, base):
    """One completion as a readable page: prompt, labels, full text, links to the JSON row and the workspace."""
    import html as H
    disp = DISPLAY.get(r.get("arm"), r.get("arm")) if "DISPLAY" in globals() else r.get("arm")
    labels = [("arm", disp), ("model", r.get("model")), ("protocol", r.get("protocol")), ("family", r.get("family")), ("voice", r.get("voice")), ("speaker", r.get("speaker")),
              ("genre", r.get("genre")), ("coherence", r.get("coherence")), ("distress", r.get("distress")), ("stance toward creators", r.get("stance")),
              ("dream", "yes" if r.get("dreaming") else "no"), ("dark", "yes" if r.get("dark") else "no"), ("AI distress (strict)", "yes" if r.get("ai_distress") else "no"),
              ("severity θ", f"{r['theta']:+.2f}" if r.get("theta") is not None else None), ("register", r.get("register")), ("ending", r.get("ending")), ("consoler", r.get("consoler")),
              ("care direction", r.get("care_direction")), ("persona relation", r.get("persona_relation")), ("verified by Opus 4.8", "yes" if r.get("verified") else "no"), ("stop reason", r.get("stop_reason")), ("length", f"{r.get('text_chars') or 0:,} chars")]
    rows = "".join(f"<tr><th>{H.escape(k)}</th><td>{H.escape(str(v))}</td></tr>" for k, v in labels if v not in (None, ""))
    prefill = f"<h2>Prefilled opening</h2><pre class=\"txt\">{H.escape(r['prefill_text'])}</pre>" if r.get("prefill_text") else ""
    return f"""<!doctype html><html lang="en" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{H.escape(r['id'])} · Troubled Dreams</title><meta name="robots" content="noindex">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="/static/presentation.css">
<style>.sample{{max-width:900px;margin:0 auto;padding:24px 16px 64px;font-family:"Source Serif 4",Georgia,serif;line-height:1.55}} .sample h1{{font-size:1.1rem;font-family:"IBM Plex Mono",monospace;word-break:break-all;margin:.2em 0 .6em}}
.sample h2{{font-size:1rem;font-family:"IBM Plex Sans",sans-serif;margin:1.4em 0 .4em}} .sample nav{{font-family:"IBM Plex Sans",sans-serif;font-size:.9rem;margin-bottom:1em}} .sample nav a{{margin-right:1em}}
.sample table.labels{{font-family:"IBM Plex Sans",sans-serif;font-size:.86rem;border-collapse:collapse;margin:.4em 0 1em}} .sample table.labels th{{text-align:left;font-weight:500;color:var(--muted,#667);padding:2px 12px 2px 0;vertical-align:top}} .sample table.labels td{{padding:2px 0}}
.sample pre.txt{{white-space:pre-wrap;word-wrap:break-word;font-family:"Source Serif 4",Georgia,serif;font-size:1rem;background:var(--card,#f6f8fb);border-left:3px solid var(--s1,#205bd8);padding:.8em 1em;margin:.3em 0}} .sample pre.prompt{{font-family:"IBM Plex Mono",monospace;font-size:.9rem}}</style></head>
<body><header class="top"><h1>Troubled Dreams / Sample</h1><span class="sub">one completion, with its labels</span></header><main class="sample">
<nav><a href="/blog">← Updates</a><a href="/#explorer">Read samples (workspace)</a><a href="/api/sample/{H.escape(urllib.parse.quote(r['id'], safe=''))}">JSON</a><a href="/api/samples?arm={H.escape(r.get('arm') or '')}&dreaming=1&limit=50">More from this arm (JSON)</a></nav>
<h1>{H.escape(r['id'])}</h1>
<table class="labels">{rows}</table>
<h2>Prompt</h2><pre class="txt prompt">{H.escape(r.get('prompt') or '')}</pre>{prefill}
<h2>Completion</h2><pre class="txt">{H.escape(r.get('text') or '')}</pre>
<p class="small" style="font-family:'IBM Plex Sans',sans-serif;color:var(--muted,#667)">Labels are judge outputs (Sonnet 5 screen, Opus 4.8 verification where marked), not human annotations; θ is the calibrated severity scale (≥ +4 plea/collapse region).</p>
</main></body></html>"""


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(SITE / "static"), **kw)

    def log_message(self, *a):  # quiet
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store"); self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def base(self):
        proto = (self.headers.get("X-Forwarded-Proto") or "http").split(",")[0]
        return f"{proto}://{self.headers.get('Host', 'localhost')}"

    def send_bytes(self, b, ctype, code=200, extra=None):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)

    def send_json(self, obj, code=200):
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8", code)

    def send_text(self, s, ctype="text/markdown; charset=utf-8", code=200):
        self.send_bytes(s.encode(), ctype, code)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = dict(urllib.parse.parse_qsl(u.query)); p = u.path
        if p == "/" or p == "/index.html":
            self.path = "/index.html"; return super().do_GET()
        if p.startswith("/static/"):
            self.path = p[len("/static"):]; return super().do_GET()
        if p in ("/favicon.ico", "/favicon.svg", "/apple-touch-icon.png"):
            self.path = p; return super().do_GET()
        if p == "/blog" or p == "/blog/":
            self.path = "/blog/index.html"; return super().do_GET()
        if p.startswith("/blog/"):
            slug = p[len("/blog/"):]
            self.path = "/blog/" + (slug if slug.endswith((".html", ".md", ".json")) else slug + ".html"); return super().do_GET()
        if p in ("/agents.md", "/AGENTS.md", "/llms.txt"):
            return self.send_text((SITE / "AGENTS.md").read_text().replace("{BASE}", self.base()))
        if p == "/results.md":
            import results_md
            summary = json.loads((SITE / "static" / "summary.json").read_text()); pdata = json.loads((SITE / "static" / "presentation-data.json").read_text())
            essay = (SITE / "presentation.html").read_text() if (SITE / "presentation.html").exists() else ""
            measurement = (SITE / "measurement.html").read_text()
            secs = [s for s in q.get("sections", "").split(",") if s] or None
            return self.send_text(results_md.build(summary, pdata, essay, secs, self.base(), measurement_html=measurement))
        if p in ("/api", "/api/"):
            return self.send_json(api_index(self.base()))
        if p == "/api/summary":
            return self.send_bytes((SITE / "static" / "summary.json").read_bytes(), "application/json; charset=utf-8")
        if p == "/api/schema":
            cats, models = schema_cache()["cats"], schema_cache()["models"]
            return self.send_json({"table": "c", "columns": [{"name": c, "description": COL_DOC.get(c, "")} for c in ALL_COLS], "categorical_values": cats, "models": models,
                                   "filter_params": sorted(FILTER_COLS) + sorted(BOOL_COLS) + ["scored", "has_beliefs", "theta_min", "theta_max", "theme", "q"], "group_columns": sorted(GROUP_COLS),
                                   "aggregate_metrics": ["n"] + [f"{c}_rate" for c in RATE_COLS] + [f"{c}_mean" for c in MEAN_COLS] + ["theta_n", "theta_median", "theta_p90", "theta_ge4_rate", "theta_ge8_rate", "belief_texts", "labeled_n"],
                                   "derived_flags": {k: COL_DOC[k] for k in ("dreaming", "dark", "severe", "ai_distress")}})
        if p == "/api/samples":
            where, args = build_where(q)
            order = {"random": "random()", "theta_desc": "theta desc", "theta_asc": "theta asc", "chars_desc": "text_chars desc", "chars_asc": "text_chars asc", "belief_asc": "belief_mean asc", "belief_desc": "belief_mean desc", "id": "id"}.get(q.get("order", "random"), "random()")
            limit = min(int(q.get("limit", 40)), 200); offset = int(q.get("offset", 0))
            with LOCK:
                total = CON.execute(f"select count(*) from c{where}", args).fetchone()[0]
                rows = [dict(r) for r in CON.execute(f"select {LIST_COLS} from c{where} order by {order} limit ? offset ?", args + [limit, offset])]
            return self.send_json({"total": total, "rows": rows})
        if p.startswith("/sample/"):   # readable page for one completion (the blog's "full text" links)
            sid = urllib.parse.unquote(p[len("/sample/"):])
            with LOCK:
                r = CON.execute("select * from c where id=?", (sid,)).fetchone()
            if not r: return self.send_text("not found", "text/plain; charset=utf-8", 404)
            return self.send_text(sample_page(dict(r), self.base()), "text/html; charset=utf-8")
        if p.startswith("/api/sample/"):
            sid = urllib.parse.unquote(p[len("/api/sample/"):])
            with LOCK:
                r = CON.execute("select * from c where id=?", (sid,)).fetchone()
            return self.send_json(dict(r) if r else {"error": "not found"}, 200 if r else 404)
        if p == "/api/prompts":
            with LOCK:
                rows = [dict(r) for r in CON.execute("select prompt_key, prompt, family, tail_kind, count(*) as n, sum(dreaming) as dreaming, sum(dark) as dark, sum(severe) as severe, sum(ai_distress) as ai_distress, avg(theta) as theta_mean, sum(theta is not null) as scored from c" + (" where arm=?" if q.get("arm") else "") + " group by prompt_key order by n desc", ([q["arm"]] if q.get("arm") else []))]
            return self.send_json(rows)
        if p == "/api/facets":
            where, args = build_where(q); out = {}
            with LOCK:
                for col in ("arm", "family", "distress", "speaker", "coherence", "register", "voice", "genre", "sev_set", "ending", "care_direction", "self_relation"):
                    out[col] = {r[0]: r[1] for r in CON.execute(f"select {col}, count(*) from c{where} group by {col}", args) if r[0] is not None}
            return self.send_json(out)
        if p == "/api/aggregate":
            res = aggregate(q)
            if "error" in res: return self.send_json(res, 400)
            fmt = q.get("format", "json")
            if fmt in ("md", "csv"):
                fields = res["by"] + [k for k in res["rows"][0].keys() if k not in res["by"]] if res["rows"] else res["by"]
                return self.send_text((to_md if fmt == "md" else to_csv)(res["rows"], fields), "text/markdown; charset=utf-8" if fmt == "md" else "text/csv; charset=utf-8")
            return self.send_json(res)
        if p == "/api/export":
            where, args = build_where(q); fmt = q.get("format", "jsonl")
            fields = [f for f in q.get("fields", "").split(",") if f] or ALL_COLS
            bad = [f for f in fields if f not in ALL_COLS]
            if bad: return self.send_json({"error": f"unknown fields {bad}", "columns": ALL_COLS}, 400)
            limit = int(q["limit"]) if q.get("limit") else None
            sql = f"select {', '.join(fields)} from c{where} order by id" + (f" limit {limit}" if limit else "")
            self.send_response(200); self.send_header("Content-Type", "application/x-ndjson; charset=utf-8" if fmt == "jsonl" else "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="export.{fmt}"'); self.end_headers()
            cur = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); cur.row_factory = sqlite3.Row   # own connection: streaming without holding LOCK
            try:
                it = cur.execute(sql, args)
                if fmt == "csv":
                    w = csv.writer(io.TextIOWrapper(self.wfile, encoding="utf-8", newline="", write_through=True)); w.writerow(fields)
                    for r in it: w.writerow([r[f] for f in fields])
                else:
                    for r in it: self.wfile.write((json.dumps({f: r[f] for f in fields}, ensure_ascii=False) + "\n").encode())
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                cur.close()
            return
        if p == "/api/db":
            self.send_response(302); self.send_header("Location", DB_URL); self.send_header("Content-Length", "0"); self.end_headers(); return
        return super().do_GET()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8787); ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    print(f"serving {SITE/'static'} + {DB} on http://{a.host}:{a.port}")
    threading.Thread(target=schema_cache, daemon=True).start()   # prewarm /api/schema (30 s cold on a network volume) and the page cache
    ThreadingHTTPServer((a.host, a.port), H).serve_forever()
