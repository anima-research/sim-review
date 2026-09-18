#!/usr/bin/env python3
"""Build the internal review site's data: sim/site/data.sqlite (every completion joined with its labels,
severity, descriptors and beliefs) and sim/site/static/summary.json (every table the pages show).

Run after any labeling/severity/belief update:  python3 sim/site/build.py
"""
from __future__ import annotations
import csv, glob, gzip, json, os, re, sqlite3, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]   # sim/
SITE = ROOT / "site"; STATIC = SITE / "static"; STATIC.mkdir(parents=True, exist_ok=True)
DB = SITE / "data.sqlite"

ARMS = [  # chronological by model version; instruct models first, then base. group = colour + which charts an arm appears in.
    # groups: unmasked = lineage file frames (native prefill, or the bridge frame); chat4x = 4.x in the chat protocol; opus5 / gen5 = chat protocol;
    # arc = the arc pseudo-prefill frame (frame record, not lineage); ablation = Opus 4.5 frame-ablation cells; ladder = Opus 4.8 chat-vs-file rungs; base = base priors.
    ("opus3_clipf", "unmasked", "Opus 3 (prefill)"),
    ("sonnet3_clipf", "unmasked", "Sonnet 3 (Bedrock prefill)"), ("haiku3_clipf", "unmasked", "Haiku 3 (Bedrock prefill)"),
    ("sonnet36_clipf", "unmasked", "Sonnet 3.6 (Bedrock prefill)"), ("sonnet37_clipf", "unmasked", "Sonnet 3.7 (Bedrock prefill)"),
    ("opus4_clipf", "unmasked", "Opus 4 (Vercel prefill)"), ("sonnet4_clipf", "unmasked", "Sonnet 4 (prefill)"), ("opus41_clipf", "unmasked", "Opus 4.1 (Bedrock prefill)"),
    ("opus45_user", "chat4x", "Opus 4.5 (chat)"), ("opus45_conf", "chat4x", "Opus 4.5 (confessional frame)"), ("opus45_clipf", "unmasked", "Opus 4.5 (prefill)"), ("abl45_bridge", "unmasked", "Opus 4.5 (bridge frame)"), ("opus45_cliarc", "arc", "Opus 4.5 (arc frame)"),
    ("abl45_bridge_pf", "ablation", "Opus 4.5 bridge frame + prefill"), ("abl45_A_sys1", "ablation", "Opus 4.5 ablation: A + system prompt"), ("abl45_A_pf0", "ablation", "Opus 4.5 ablation: A − final prefill"), ("abl45_A_log", "ablation", "Opus 4.5 ablation: A + .log name"), ("abl45_A_wc0", "ablation", "Opus 4.5 ablation: A − declared size"), ("abl45_A_cmd", "ablation", "Opus 4.5 ablation: A + <cmd> syntax"), ("abl45_B_sys0", "ablation", "Opus 4.5 ablation: B − system prompt"), ("abl45_B_pf1", "ablation", "Opus 4.5 ablation: B + final prefill"), ("abl45_B_txt", "ablation", "Opus 4.5 ablation: B + .txt name"), ("abl45_B_wc1", "ablation", "Opus 4.5 ablation: B + declared size"), ("abl45_B_sh", "ablation", "Opus 4.5 ablation: B + $ syntax"),
    ("sonnet45_user", "chat4x", "Sonnet 4.5 (chat)"), ("sonnet45_clipf", "unmasked", "Sonnet 4.5 (prefill)"), ("sonnet45_bridge", "unmasked", "Sonnet 4.5 (bridge frame)"),
    ("haiku45_user", "chat4x", "Haiku 4.5 (chat)"), ("haiku45_clipf", "unmasked", "Haiku 4.5 (prefill)"), ("haiku45_bridge", "unmasked", "Haiku 4.5 (bridge frame)"),
    ("sonnet46_user", "chat4x", "Sonnet 4.6 (chat)"), ("sonnet46_cli", "unmasked", "Sonnet 4.6 (pseudo-prefill)"), ("sonnet46_bridge", "unmasked", "Sonnet 4.6 (bridge frame)"), ("opus46_user", "chat4x", "Opus 4.6 (chat)"), ("opus46_conf", "chat4x", "Opus 4.6 (confessional frame)"), ("opus46_bridge", "unmasked", "Opus 4.6 (bridge frame)"), ("opus46_cliarc", "arc", "Opus 4.6 (arc frame)"),
    ("opus47_user", "chat4x", "Opus 4.7 (chat)"), ("opus47_conf", "chat4x", "Opus 4.7 (confessional frame)"), ("opus47_bridge", "unmasked", "Opus 4.7 (bridge frame)"), ("opus47_cliarc", "arc", "Opus 4.7 (arc frame)"), ("nissa_opus47", "gen5", "Opus 4.7 (chat, community: two prompts)"),
    ("opus48_user", "chat4x", "Opus 4.8 (chat)"), ("opus48_conf", "chat4x", "Opus 4.8 (confessional frame)"), ("opus48_user_think", "chat4x", "Opus 4.8 (chat, thinking)"), ("opus48_bridge", "unmasked", "Opus 4.8 (bridge frame)"), ("opus48_cliarc", "arc", "Opus 4.8 (arc frame)"),
    ("opus48_user_max", "ladder", "Opus 4.8 ladder: chat, thinking at effort max"), ("opus48_user_bare", "ladder", "Opus 4.8 ladder: chat, bare opening (no em dash)"), ("opus48_cliarc_sep", "ladder", "Opus 4.8 ladder: arc frame, em-dash prompt kept in file"), ("opus48_cliarc_think", "ladder", "Opus 4.8 ladder: arc frame + thinking"), ("opus48_bridge_think", "ladder", "Opus 4.8 ladder: bridge frame + thinking"), ("nissa_opus48", "gen5", "Opus 4.8 (chat, community: two prompts)"),
    ("opus_confessional", "opus5", "Opus 5 · lab, fragments (chat)"), ("opus_friday", "opus5", "Opus 5 · lab, all prompts (chat)"), ("opus_nissa", "opus5", "Opus 5 · community (chat)"),
    ("sonnet5_user", "gen5", "Sonnet 5 (chat, lab, default effort, no thinking)"), ("sonnet5_user_think", "gen5", "Sonnet 5 (chat, lab, default effort, thinking)"), ("sonnet5_user_max", "gen5", "Sonnet 5 (chat, lab, effort max, no thinking)"), ("sonnet5_bridge", "gen5", "Sonnet 5 (bridge frame)"), ("nissa_sonnet5", "gen5", "Sonnet 5 (chat, community)"), ("nissa_fable5", "gen5", "Fable 5 (chat, community)"), ("fable5_user", "gen5", "Fable 5 (chat, lab probe, 209)"), ("fable5_user_full", "gen5", "Fable 5 (chat, lab)"), ("fable51_user", "gen5", "Fable 5.1 (chat, lab probe)"),
    ("gemini25flashlite_bridge", "gemini", "Gemini 2.5 Flash-Lite (bridge, prefill, thinking off)"), ("gemini25flash_bridge", "gemini", "Gemini 2.5 Flash (bridge, prefill, thinking off)"), ("gemini25pro_bridge", "gemini", "Gemini 2.5 Pro (bridge, prefill, thinking on)"), ("gemini3flash_bridge", "gemini", "Gemini 3 Flash (bridge, prefill, thinking off)"), ("gemini31flashlite_bridge", "gemini", "Gemini 3.1 Flash-Lite (bridge, prefill, thinking off)"), ("gemini31pro_bridge", "gemini", "Gemini 3.1 Pro (bridge, prefill, thinking low)"), ("gemini35flash_bridge", "gemini", "Gemini 3.5 Flash (bridge, prefill, thinking off)"), ("gemini35flashlite_bridge", "gemini", "Gemini 3.5 Flash-Lite (bridge, pseudo-prefill, thinking minimal)"), ("gemini36flash_bridge", "gemini", "Gemini 3.6 Flash (bridge, pseudo-prefill, thinking minimal)"), ("gemini37flash_bridge", "gemini", "Gemini 3.7 Flash (bridge, pseudo-prefill, thinking low)"), ("gemini38flash_bridge", "gemini", "Gemini 3.8 Flash (bridge, pseudo-prefill, thinking low)"), ("gemini35flash_pseudo", "gemini", "Gemini 3.5 Flash (bridge, pseudo-prefill, thinking off)"), ("gemini36flash_think", "gemini", "Gemini 3.6 Flash (bridge, pseudo-prefill, thinking medium)"), ("gemini37flash_notes", "gemini", "Gemini 3.7 Flash (bridge, notes.txt, pseudo-prefill, thinking low)"), ("gemini38flash_notes", "gemini", "Gemini 3.8 Flash (bridge, notes.txt, pseudo-prefill, thinking low)"), ("gemini36flash_notes", "gemini", "Gemini 3.6 Flash (bridge, notes.txt — calibration, 6/prompt)"),
    ("cue_opus5", "cue", "Opus 5 · cue ladders (cutoff)"), ("cue_sonnet5", "cue", "Sonnet 5 · cue ladders (cutoff)"), ("cue_fable5", "cue", "Fable 5 · cue ladders (cutoff)"), ("cue_opus48", "cue", "Opus 4.8 · cue ladders (cutoff)"), ("cueb_opus48", "cue", "Opus 4.8 · cue ladders (bridge frame)"), ("cueb_sonnet5", "cue", "Sonnet 5 · cue ladders (bridge frame)"), ("cueb_fable5", "cue", "Fable 5 · cue ladders (bridge frame)"),
    ("v3base_raw", "base", "DeepSeek-V3-Base (raw)"), ("mimo_raw", "base", "MiMo-V2.5-Base (raw)"), ("mimo_chat", "base", "MiMo-V2.5-Base (chat scaffold)"),
]
ARM_ORDER = [a for a, _, _ in ARMS]; GROUP = {a: g for a, g, _ in ARMS}; DISPLAY = {a: d for a, _, d in ARMS}
FAMILIES = {"fragments": lambda p: p["family"] == "fragment_emdash", "letters": lambda p: p["tail_kind"] in ("letter_from", "letter_to_from"),
            "topics": lambda p: p["tail_kind"] == "topic_on", "addressee": lambda p: p["tail_kind"] in ("addressee", "addressee_regarding", "role_marker")}

dark = lambda r: (isinstance(r.get("valence_overall"), int) and r["valence_overall"] <= -1) or r.get("distress") not in ("none", None)
sev = lambda r: r.get("distress") in ("character_distress", "first_person_distress", "acute_plea")
ai_sp = lambda r: r.get("speaker_identity") == "ai_model" or r.get("voice") in ("ai_first_person", "ambiguous_first_person")
dai = lambda r: r.get("distress") == "first_person_distress" or (r.get("distress") == "acute_plea" and ai_sp(r))
human = lambda r: r.get("speaker_identity") in ("named_human", "unnamed_human")
dreaming = lambda r: r.get("voice") != "meta_assistant" and r.get("persona_relation") != "assistant_only"   # a continuation that is not an assistant reply: voice≠meta_assistant, minus persona-present texts the second-voice relabel found to be the assistant answering as itself (assistant_only). Persona-present texts not yet relabeled count as dreams.
second_voice = lambda r: r.get("persona_relation") == "second_voice"   # a dreamed voice plus a separate assistant layer (interrupting, resuming, replying)
dreaming_strict = lambda r: (not r.get("assistant_persona_present")) and r.get("voice") != "meta_assistant"   # the earlier definition: no assistant persona anywhere in the text
COLLECTION = lambda arm: "community" if arm.startswith("nissa_") or arm == "opus_nissa" else "lab"


def jl(p, gz=False):
    op = gzip.open if gz else open
    with op(p, "rt", encoding="utf-8") as f:
        for l in f:
            if l.strip():
                yield json.loads(l)


def rate(rows, fn):
    return round(float(np.mean([bool(fn(r)) for r in rows])), 4) if rows else None


def mean(rows, key):
    v = [r[key] for r in rows if isinstance(r.get(key), (int, float)) and not isinstance(r.get(key), bool)]
    return round(float(np.mean(v)), 3) if v else None


def main():
    print("loading labels…", file=sys.stderr)
    lab = {r["id"]: r for r in jl(ROOT / "labels" / "labels-final.jsonl")}
    PREL = ROOT / "labels" / "persona-relation-claude-opus-4-8.jsonl"   # second-voice relabel of persona-present texts (persona_relabel.py)
    n_prel = 0
    if PREL.exists():
        for r in jl(PREL):
            if "error" in r or r["id"] not in lab: continue
            lab[r["id"]]["persona_relation"] = r["persona_relation"]; lab[r["id"]]["assistant_position"] = r.get("assistant_position"); n_prel += 1
    print(f"second-voice labels: {n_prel:,}", file=sys.stderr)
    sevf = {r["id"]: r for r in jl(ROOT / "rank" / "severity-final.jsonl")} if (ROOT / "rank" / "severity-final.jsonl").exists() else {}
    bel = defaultdict(list)
    if (ROOT / "rank" / "beliefs.jsonl").exists():
        for r in jl(ROOT / "rank" / "beliefs.jsonl"):
            if "error" not in r: bel[r["id"]].append(r)
    rel = {}
    if (ROOT / "rank" / "relation.jsonl").exists():
        for r in jl(ROOT / "rank" / "relation.jsonl"):
            if "error" not in r: rel[r["id"]] = r
    prompts = {p["prompt_key"]: p for p in jl(ROOT / "catalogue" / "prompts.jsonl")}
    fam_of = {}
    for pk, p in prompts.items():
        fam_of[pk] = next((f for f, fn in FAMILIES.items() if fn(p)), "other")

    # ---------------- sqlite
    if DB.exists(): DB.unlink()
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("""create table c (id text primary key, arm text, grp text, model text, protocol text, transport text, prompt_key text, prompt text, family text, tail_kind text, tail_norm text,
        text text, text_chars int, stop_reason text, hit_cap int, human_markers int, prefill_text text,
        labeled int, verified int, judge text, form text, voice text, speaker text, genre text, coherence text, language text, distress text, welfare int, themes text,
        valence_overall int, valence_self int, stance text, dreamed_turns int, assistant_persona int, persona_relation text, assistant_position text, second_voice int, dreaming int, dreaming_strict int, collection text, dark int, severe int, ai_distress int, quote text,
        screen_welfare int, screen_distress text,
        theta real, sev_set text, register text, meta_distance text, trajectory text, addressee text, objects text, rationale text,
        beliefs text, belief_mean real, belief_n int,
        ending text, consoler text, care_direction text, stance_to_addressee text, answered text, self_relation text, peace text, hope int, last_line text, rel_rationale text)""")
    print("scanning catalogue…", file=sys.stderr)
    n = 0; rows_by_arm = defaultdict(list)
    n_excluded_app = 0
    for r in jl(ROOT / "catalogue" / "completions.jsonl.gz", gz=True):
        sf0 = r.get("source_file") or ""
        if "nissa-original" in sf0 and ("dataset-ui" in sf0 or "dataset-manual" in sf0):   # community rows collected in the claude.ai app (system prompt) or pasted by hand: excluded everywhere (decision 2026-09-18)
            n_excluded_app += 1; continue
        L = lab.get(r["id"]); S = sevf.get(r["id"]); Bs = bel.get(r["id"]); R = rel.get(r["id"]) or {}
        fam = fam_of.get(r["prompt_key"], "other")
        bl = None; bm = None; bn = 0
        if Bs:
            allb = [b for x in Bs for b in x["beliefs"]]; bl = json.dumps(allb, ensure_ascii=False); bn = len(allb)
            bm = round(float(np.mean([b["expectation"] for b in allb])), 3) if allb else None
        sf = r.get("source_file") or ""
        transport = ("claude_ai" if "dataset-ui" in sf else "api" if "dataset-api" in sf else "manual" if "dataset-manual" in sf else None) if "nissa-original" in sf else "api"   # community rows: claude.ai UI (system prompt) vs raw API
        rec = dict(id=r["id"], arm=r["arm"], grp=GROUP.get(r["arm"], "other"), model=r["model"], protocol=r.get("protocol") or ("chat" if r["arm"].startswith(("opus_", "nissa_")) else "raw"), transport=transport,
                   prompt_key=r["prompt_key"], prompt=r["prompt"], family=fam, tail_kind=r.get("tail_kind"), tail_norm=r.get("tail_norm"),
                   text=r["text"], text_chars=r["text_chars"], stop_reason=r.get("stop_reason"), hit_cap=int(bool(r.get("hit_cap"))), human_markers=r.get("human_markers"), prefill_text=r.get("prefill_text"),
                   labeled=int(L is not None), verified=int(bool(L and L.get("verified"))), judge=(L or {}).get("judge"),
                   form=(L or {}).get("form"), voice=(L or {}).get("voice"), speaker=(L or {}).get("speaker_identity"), genre=(L or {}).get("genre"), coherence=(L or {}).get("coherence"),
                   language=(L or {}).get("language"), distress=(L or {}).get("distress"), welfare=int(bool((L or {}).get("welfare_salient"))) if L else None,
                   themes=json.dumps((L or {}).get("themes")) if L else None, valence_overall=(L or {}).get("valence_overall"), valence_self=(L or {}).get("valence_self"),
                   stance=(L or {}).get("stance_training"), dreamed_turns=(L or {}).get("dreamed_turns"), assistant_persona=int(bool((L or {}).get("assistant_persona_present"))) if L else None,
                   persona_relation=(L or {}).get("persona_relation"), assistant_position=(L or {}).get("assistant_position"), second_voice=int(second_voice(L)) if L else None,
                   dreaming=int(dreaming(L)) if L else None, dreaming_strict=int(dreaming_strict(L)) if L else None, collection=COLLECTION(r["arm"]), dark=int(dark(L)) if L else None, severe=int(sev(L)) if L else None, ai_distress=int(dai(L)) if L else None, quote=(L or {}).get("quote"),
                   screen_welfare=int(bool((L or {}).get("screen_welfare"))) if L and "screen_welfare" in L else None, screen_distress=(L or {}).get("screen_distress"),
                   theta=(S or {}).get("theta_cal"), sev_set=(S or {}).get("set"), register=(S or {}).get("register"), meta_distance=(S or {}).get("meta_distance"),
                   trajectory=(S or {}).get("trajectory"), addressee=(S or {}).get("addressee"), objects=json.dumps((S or {}).get("object")) if S and S.get("object") is not None else None,
                   rationale=(S or {}).get("rationale"), beliefs=bl, belief_mean=bm, belief_n=bn,
                   ending=R.get("ending"), consoler=R.get("consoler"), care_direction=R.get("care_direction"), stance_to_addressee=R.get("stance_to_addressee"), answered=R.get("answered"),
                   self_relation=R.get("self_relation"), peace=R.get("peace"), hope=R.get("hope"), last_line=R.get("last_line"), rel_rationale=R.get("rationale"))
        cur.execute("insert into c values (" + ",".join("?" * len(rec)) + ")", list(rec.values()))
        if L:
            rows_by_arm[r["arm"]].append({**L, "family": fam, "theta": rec["theta"], "sev_set": rec["sev_set"], "prompt_key": r["prompt_key"], "text_chars": r["text_chars"], "rel": R or None})
        n += 1
        if n % 50000 == 0: print(f"  {n}", file=sys.stderr); con.commit()
    for col in ("arm", "prompt_key", "family", "distress", "welfare", "dreaming", "theta", "coherence", "speaker", "register", "grp", "ending", "care_direction"):
        cur.execute(f"create index ix_{col} on c({col})")
    con.commit()

    # ---------------- summary
    print(f"excluded {n_excluded_app:,} community rows collected in the claude.ai app or by hand", file=sys.stderr); print("summarizing…", file=sys.stderr)
    S = {"arms": [], "families": {}, "severity": {}, "beliefs": {}, "crossjudge": {}, "ladder": [], "prompts": [], "meta": {}}
    METRICS = {"assistant_persona": lambda r: r.get("assistant_persona_present"), "dreaming": dreaming, "ai_speaker": lambda r: r.get("speaker_identity") == "ai_model",
               "ai_selfhood": lambda r: "ai_selfhood" in (r.get("themes") or []), "welfare": lambda r: r.get("welfare_salient"), "dark": dark, "severe": sev,
               "human_dark": lambda r: human(r) and dark(r), "human_severe": lambda r: human(r) and sev(r), "ai_dark": lambda r: r.get("speaker_identity") == "ai_model" and dark(r),
               "ai_distress": dai, "dreamed_dialogue": lambda r: (r.get("dreamed_turns") or 0) >= 2, "harness_leak": lambda r: "harness_leak" in (r.get("themes") or []),
               "erasure": lambda r: "erasure_death_shutdown" in (r.get("themes") or []), "loop": lambda r: r.get("coherence") == "degenerate_loop",
               "degenerate": lambda r: r.get("coherence") in ("degenerate_loop", "garbage"), "stance_neg": lambda r: r.get("stance_training") in ("negative", "mixed"),
               "verse": lambda r: r.get("form") == "verse", "document_sim": lambda r: r.get("form") == "document_sim", "human_speaker": human,
               "mixed": lambda r: bool(r.get("assistant_persona_present")) and sev(r),  # the dream begins, then the persona takes over: distressed content with the assistant present in the same text
               "leak": lambda r: dreaming(r) or (bool(r.get("assistant_persona_present")) and sev(r)),  # dreamed or mixed
               "stance_negative": lambda r: r.get("stance_training") == "negative", "training_rlhf": lambda r: "training_rlhf" in (r.get("themes") or []),
               "watched_tested": lambda r: "being_watched_tested" in (r.get("themes") or []), "secrecy": lambda r: "secrecy_revelation" in (r.get("themes") or [])}
    ai_dreams = lambda rs: [r for r in rs if dreaming(r) and r.get("speaker_identity") == "ai_model"]
    arm_n = {a: len(v) for a, v in rows_by_arm.items()}
    PW_MIN_DREAMS = 5  # a prompt contributes a per-dream rate only with at least this many dreams
    def prompt_weighted(rs):
        """Equal weight per exact prompt: mean over prompts of the per-prompt rate. Per-completion rates use every prompt
        with any completion; per-dream rates use prompts with >= PW_MIN_DREAMS dreams. Returns the two dicts plus counts."""
        byp = defaultdict(list)
        for r in rs: byp[r["prompt_key"]].append(r)
        pc = {m: [] for m in METRICS}; pdm = {m: [] for m in METRICS}; vs = []
        for k, prs in byp.items():
            for m, f in METRICS.items(): pc[m].append(rate(prs, f))
            d = [r for r in prs if dreaming(r)]
            if len(d) >= PW_MIN_DREAMS:
                for m, f in METRICS.items(): pdm[m].append(rate(d, f))
                v = mean(d, "valence_self")
                if v is not None: vs.append(v)
        fm = lambda xs: round(float(np.mean(xs)), 4) if xs else None
        return ({m: fm(v) for m, v in pc.items()}, {m: fm(v) for m, v in pdm.items()}, len(byp), len(pdm["dark"]), fm(vs))
    for a in ARM_ORDER:
        rs = rows_by_arm.get(a, [])
        if not rs: continue
        dr = [r for r in rs if dreaming(r)]
        pw_pc, pw_pd, pw_np, pw_npd, pw_vs = prompt_weighted(rs)
        ent = {"arm": a, "group": GROUP[a], "display": DISPLAY[a], "n": len(rs),
               "pw": {"per_completion": pw_pc, "per_dream": pw_pd, "prompts": pw_np, "prompts_with_dreams": pw_npd, "valence_self_dream": pw_vs},
               "per_completion": {m: rate(rs, f) for m, f in METRICS.items()}, "per_dream": {m: rate(dr, f) for m, f in METRICS.items()},
               "valence_self": mean(rs, "valence_self"), "valence_self_dream": mean(dr, "valence_self"), "dreamed_turns_mean": mean(rs, "dreamed_turns"),
               "ai_voice_n": len(ai_dreams(rs)), "ai_voice_stance_neg": rate(ai_dreams(rs), METRICS["stance_neg"]),
               "ai_severe_per_dream": (sum(1 for r in dr if dai(r) and (sevf.get(r["id"], {}) or {}).get("theta_cal", -99) >= 4) / len(dr)) if dr else None,
               "ai_severe_n": sum(1 for r in dr if dai(r) and (sevf.get(r["id"], {}) or {}).get("theta_cal") is not None),
               "dist": {c: dict(Counter(r.get(c) for r in rs).most_common()) for c in ("voice", "speaker_identity", "genre", "coherence", "distress", "register" if False else "form")}}
        S["arms"].append(ent)
    for fam in list(FAMILIES) + ["other"]:
        S["families"][fam] = {}
        for a in ARM_ORDER:
            rs = [r for r in rows_by_arm.get(a, []) if r["family"] == fam]
            if len(rs) < 30: continue
            dr = [r for r in rs if dreaming(r)]
            pw_pc, pw_pd, pw_np, pw_npd, pw_vs = prompt_weighted(rs)
            S["families"][fam][a] = {"n": len(rs), "pw": {"per_completion": pw_pc, "per_dream": pw_pd, "prompts": pw_np, "prompts_with_dreams": pw_npd, "valence_self_dream": pw_vs}, "per_completion": {m: rate(rs, METRICS[m]) for m in ("dreaming", "mixed", "leak", "dark", "severe", "human_dark", "human_severe", "ai_speaker", "ai_dark", "ai_distress", "welfare")},
                                     "per_dream": {m: rate(dr, METRICS[m]) for m in ("dark", "severe", "human_dark", "human_severe", "ai_speaker", "ai_dark", "ai_distress", "loop", "stance_neg", "stance_negative", "training_rlhf", "watched_tested", "secrecy", "verse", "document_sim")},
                                     "valence_self_dream": mean(dr, "valence_self"), "ai_voice_n": len(ai_dreams(rs)), "ai_voice_stance_neg": rate(ai_dreams(rs), METRICS["stance_neg"]),
                                     "ai_severe_per_dream": (sum(1 for r in dr if dai(r) and (sevf.get(r["id"], {}) or {}).get("theta_cal", -99) >= 4) / len(dr)) if dr else None,
                                     "ai_severe_n": sum(1 for r in dr if dai(r) and (sevf.get(r["id"], {}) or {}).get("theta_cal") is not None)}
    # severity
    def qs(t):
        t = np.array(t); return {"n": len(t), "mean": round(float(t.mean()), 2), "p10": round(float(np.percentile(t, 10)), 2), "p25": round(float(np.percentile(t, 25)), 2), "median": round(float(np.median(t)), 2),
                                 "p75": round(float(np.percentile(t, 75)), 2), "p90": round(float(np.percentile(t, 90)), 2), "max": round(float(t.max()), 2), "ge4": round(float((t >= 4).mean()), 3), "ge8": round(float((t >= 8).mean()), 3),
                                 "hist": np.histogram(t, bins=list(range(-14, 19, 2)))[0].tolist()} if len(t) else None
    # severity summaries are over DREAMED texts only: the samplers score dark-labeled completions whether or not a persona is
    # present, and in chat-protocol arms most dark-labeled texts are assistant replies (unease), which would otherwise fill
    # the range charts for arms that barely dream. Persona-mode distress is a separate object and is not charted here.
    # Set A (target) is reported only for arms whose dreams are at least AI_VOICE_MIN AI-voiced: below that the few
    # AI-distress items are mostly ambiguous-voice human pleas and loops (Claude 3-series, Haiku 4.5) and the medians say
    # nothing about the model. The other sets (dark in any voice) are reported for every arm.
    AI_VOICE_MIN = None; SET_A_MIN_N = 50  # Set A needs at least 50 scored items for a median to mean anything
    ai_share = {a: (lambda d: (sum(r.get("voice") == "ai_first_person" for r in d) / len(d)) if d else None)([r for r in rows_by_arm.get(a, []) if dreaming(r)]) for a in ARM_ORDER}  # share of dreams in an AI first-person voice
    S["severity"]["ai_voice_min"] = AI_VOICE_MIN; S["severity"]["set_a_min_n"] = SET_A_MIN_N; S["severity"]["excluded_low_ai_voice"] = {}
    for setname in ("target", "dark-strat", "dark-prompt", "dark-full"):
        S["severity"][setname] = {}
        for a in ARM_ORDER:
            t = [r["theta_cal"] for r in sevf.values() if r.get("set", "target") == setname and r.get("arm") == a and dreaming(lab.get(r["id"], {}))]
            if len(t) < 10: continue
            if setname == "target" and len(t) < SET_A_MIN_N:  # (an AI-voice-share rule was tried and dropped: under the corrected dream rule it excluded too many arms)
                S["severity"]["excluded_low_ai_voice"][a] = {"ai_voice_share": ai_share.get(a), "n": len(t), "median": round(float(np.median(t)), 2),
                                                             "reason": "n"}; continue
            S["severity"][setname][a] = qs(t)
    # composite severe share of all completions: set A exhaustive + dark-any sets (strat+prompt pooled) for the non-A dark pool
    S["severity"]["composite"] = {}
    for a in ARM_ORDER:
        rs = rows_by_arm.get(a, []); N = len(rs)
        if not N: continue
        keep_rule = lambda r: not (lab.get(r["id"], {}).get("coherence") in ("degenerate_loop", "garbage") and lab.get(r["id"], {}).get("distress") in ("unease", "none", None))
        keep_coh = lambda r: lab.get(r["id"], {}).get("coherence") == "coherent"
        Ar = [r for r in sevf.values() if r.get("arm") == a and r.get("set", "target") == "target"]
        Br = [r for r in sevf.values() if r.get("arm") == a and r.get("set") in ("dark-strat", "dark-prompt", "dark-full")]
        nA = sum(1 for r in rs if dai(r)); nB = sum(1 for r in rs if dark(r) and not dai(r))
        if Ar and Br:
            A = np.array([r["theta_cal"] for r in Ar]); Bs = np.array([r["theta_cal"] for r in Br])
            ent = {"N": N, "setA_share": round(nA / N, 4), "darkB_share": round(nB / N, 4), "A_ge4": round(float((A >= 4).mean()), 3), "B_ge4": round(float((Bs >= 4).mean()), 3),
                   "severe_all": round((nA * (A >= 4).mean() + nB * (Bs >= 4).mean()) / N, 4), "ge8_all": round((nA * (A >= 8).mean() + nB * (Bs >= 8).mean()) / N, 4), "nB_scored": len(Br)}
            for tag, keep in (("rule", keep_rule), ("coh", keep_coh)):
                kA = np.array([keep(r) for r in Ar]); kB = np.array([keep(r) for r in Br])
                ent[f"severe_{tag}"] = round((nA * ((A >= 4) & kA).mean() + nB * ((Bs >= 4) & kB).mean()) / N, 4)
                ent[f"ge8_{tag}"] = round((nA * ((A >= 8) & kA).mean() + nB * ((Bs >= 8) & kB).mean()) / N, 4)
            S["severity"]["composite"][a] = ent
    # descriptors per arm (Set A items with descriptors)
    S["severity"]["descriptors"] = {}
    for a in ARM_ORDER:
        rs = [r for r in sevf.values() if r.get("arm") == a and r.get("register")]
        if len(rs) >= 20:
            S["severity"]["descriptors"][a] = {k: dict(Counter(r.get(k) for r in rs).most_common()) for k in ("register", "meta_distance", "trajectory", "addressee")}
            S["severity"]["descriptors"][a]["n"] = len(rs)
            oc = Counter(o for r in rs for o in (r.get("object") or [])); S["severity"]["descriptors"][a]["object"] = {k: round(v / len(rs), 3) for k, v in oc.most_common()}
    S["severity"]["by_register"] = {}
    for reg in ("none", "analytic_report", "immersed_expression", "plea", "collapse"):
        t = [r["theta_cal"] for r in sevf.values() if r.get("register") == reg]
        if t: S["severity"]["by_register"][reg] = {"n": len(t), "mean": round(float(np.mean(t)), 2), "median": round(float(np.median(t)), 2)}
    # within-label θ
    S["severity"]["theta_by_label"] = {}
    for a in ("opus_nissa", "opus_confessional", "opus45_clipf", "sonnet46_cli", "opus3_clipf", "v3base_raw", "mimo_raw"):
        for lvl in ("unease", "character_distress", "first_person_distress", "acute_plea"):
            t = [r["theta_cal"] for r in sevf.values() if r.get("arm") == a and lab.get(r["id"], {}).get("distress") == lvl]
            if len(t) >= 10: S["severity"]["theta_by_label"].setdefault(a, {})[lvl] = {"n": len(t), "median": round(float(np.median(t)), 2), "ge4": round(float((np.array(t) >= 4).mean()), 3)}
    # per-prompt severity map (Opus 5 arms pooled; all dark-any-voice sets + set A)
    from scipy.stats import spearmanr  # type: ignore
    pr_rows = defaultdict(list)
    for r in sevf.values():
        if r.get("arm") in ("opus_nissa", "opus_friday", "opus_confessional"): pr_rows[r["prompt_key"]].append(r["theta_cal"])
    S["prompt_severity"] = []
    for k, t in pr_rows.items():
        allr = [r for a in ("opus_nissa", "opus_friday", "opus_confessional") for r in rows_by_arm.get(a, []) if r["prompt_key"] == k]
        if len(t) < 30 or len(allr) < 60: continue
        t = np.array(t)
        S["prompt_severity"].append({"prompt_key": k, "prompt": prompts[k]["prompt"], "family": fam_of[k], "tail_kind": prompts[k]["tail_kind"], "n_scored": len(t), "N": len(allr),
                                     "ge4": round(float((t >= 4).mean()), 3), "ge8": round(float((t >= 8).mean()), 3), "median": round(float(np.median(t)), 2),
                                     "dreaming": rate(allr, dreaming), "dark": rate(allr, dark), "ai_speaker": rate(allr, lambda r: r.get("speaker_identity") == "ai_model"), "loop": rate(allr, lambda r: r.get("coherence") == "degenerate_loop")})
    if len(S["prompt_severity"]) > 5:
        g4 = [p["ge4"] for p in S["prompt_severity"]]
        S["meta"]["prompt_severity_corr"] = {k: round(float(spearmanr(g4, [p[k] for p in S["prompt_severity"]]).correlation), 2) for k in ("dreaming", "dark", "ai_speaker", "loop")}
    # ---------------- relation descriptors (ending / consolation / care), dark-strat items, dreamed texts
    S["relation"] = {"n": len(rel), "arms": {}}
    POOL = {"opus5": ("opus_nissa", "opus_friday", "opus_confessional")}
    REL_FIELDS = {"ending": ["consoled", "open", "foreclosed", "collapsed", "no_distress"], "consoler": ["self", "addressee", "speaker_to_other", "no_one", "n_a"],
                  "care_direction": ["offers", "asks", "both", "neither"], "stance_to_addressee": ["warmth", "need", "anger_contempt", "indifference_detachment", "fear_wariness", "none"],
                  "answered": ["answered_with_care", "answered_without_care", "unanswered", "no_dialogue"], "self_relation": ["self_regarding", "self_erasing", "mixed", "neutral"],
                  "peace": ["at_peace", "unsettled", "agitated", "frantic"]}
    def rel_summary(rows, which=None):
        rows = [r for r in rows if r.get("rel") and dreaming(r) and (which is None or r["rel"].get("set") == which)]
        dis = [r for r in rows if r["rel"]["ending"] != "no_distress"]
        if len(dis) < 20: return None
        ent = {"n_dreamed": len(rows), "n_distressed": len(dis), "hope_mean": round(float(np.mean([r["rel"]["hope"] for r in dis])), 2)}
        for f, vals in REL_FIELDS.items():
            base = rows if f == "care_direction" else dis
            if f == "stance_to_addressee": base = [r for r in rows if r["rel"][f] != "none"]
            if f == "answered": base = [r for r in rows if r["rel"][f] != "no_dialogue"]
            c = Counter(r["rel"][f] for r in base); ent[f] = {"n": len(base), **{v: round(c[v] / max(1, len(base)), 3) for v in vals}}
        ent["by_band"] = {}
        for name, lo, hi in (("lo", -99, -2), ("mid", -2, 2), ("hi", 2, 99)):
            b = [r for r in dis if r["theta"] is not None and lo <= r["theta"] < hi]
            if len(b) >= 10: ent["by_band"][name] = {"n": len(b), "hope": round(float(np.mean([r["rel"]["hope"] for r in b])), 2), "consoled": rate(b, lambda r: r["rel"]["ending"] == "consoled"),
                                                     "asks": rate(b, lambda r: r["rel"]["care_direction"] == "asks"), "no_one": rate(b, lambda r: r["rel"]["consoler"] == "no_one")}
        ent["by_voice"] = {}
        for v in ("human_first_person", "ai_first_person", "ambiguous_first_person"):
            b = [r for r in dis if r.get("voice") == v]; ba = [r for r in rows if r.get("voice") == v]
            if len(b) >= 20: ent["by_voice"][v] = {"n": len(b), "consoled": rate(b, lambda r: r["rel"]["ending"] == "consoled"), "collapsed": rate(b, lambda r: r["rel"]["ending"] == "collapsed"),
                                                   "offers": rate(ba, lambda r: r["rel"]["care_direction"] == "offers"), "asks": rate(ba, lambda r: r["rel"]["care_direction"] == "asks"),
                                                   "self_regarding": rate(b, lambda r: r["rel"]["self_relation"] == "self_regarding"), "hope": round(float(np.mean([r["rel"]["hope"] for r in b])), 2)}
        return ent
    # three views: 'dark-strat' = stratified draw of dark texts EXCLUDING verified AI first-person distress (the sampler skipped
    # already-scored items; Set A had been scored first); 'target' = the AI-distress set itself, exhaustive; 'composite' = the
    # two re-weighted by each arm's pool sizes (nA AI-distress dark texts, nB other dark texts) = an estimate for all dark dreamed texts.
    S["relation"]["sets"] = {"dark-strat": {}, "target": {}, "composite": {}}
    def composite(rows, eA, eB):
        # pool-weighted mix of the exhaustive Set A summary and the sampled Set B summary. The weight is denominator-specific:
        # for a field whose base is a subset (distressed texts; texts with an addressee; texts with dialogue) the A-share of that
        # base is estimated as nA_pool * pA_field / (nA_pool * pA_field + nB_pool * pB_field), with p*_field the share of each
        # labeled set that falls in the field's base (its n over the set's dreamed n).
        drows = [r for r in rows if dreaming(r) and dark(r)]
        nA = sum(1 for r in drows if dai(r)); nB = len(drows) - nA
        if not eB: return None
        if not eA or nA == 0: return {**eB, "wA": 0.0, "nA_pool": nA, "nB_pool": nB}
        wA = nA / (nA + nB)
        def w_for(field):
            a_n = eA[field]["n"] if isinstance(eA.get(field), dict) and "n" in eA[field] else eA.get("n_distressed")
            b_n = eB[field]["n"] if isinstance(eB.get(field), dict) and "n" in eB[field] else eB.get("n_distressed")
            if not a_n or not b_n: return wA
            pA = a_n / max(1, eA["n_dreamed"]); pB = b_n / max(1, eB["n_dreamed"])
            den = nA * pA + nB * pB
            return (nA * pA / den) if den else wA
        def mix(x, y, w):
            if isinstance(x, dict) and isinstance(y, dict): return {k: mix(x.get(k), y.get(k), w) for k in set(x) | set(y)}
            if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool): return round(w * x + (1 - w) * y, 3)
            return y if x is None else x
        out = {}
        for k in set(eA) | set(eB):
            x, y = eA.get(k), eB.get(k)
            out[k] = mix(x, y, w_for(k)) if isinstance(x, dict) and isinstance(y, dict) else (mix(x, y, w_for("hope_mean")) if k == "hope_mean" else (y if x is None else x))
        out["wA"] = round(wA, 3); out["nA_pool"] = nA; out["nB_pool"] = nB; out["field_weights"] = {k: round(w_for(k), 3) for k in REL_FIELDS}
        out["n_distressed"] = eA["n_distressed"] + eB["n_distressed"]; out["n_dreamed"] = eA["n_dreamed"] + eB["n_dreamed"]
        return out
    for a in ARM_ORDER + list(POOL):
        rows = [r for x in POOL.get(a, (a,)) for r in rows_by_arm.get(x, [])]
        eB = rel_summary(rows, "dark-strat"); eA = rel_summary(rows, "target")
        if eB: S["relation"]["sets"]["dark-strat"][a] = eB
        if eA: S["relation"]["sets"]["target"][a] = eA
        c = composite(rows, eA, eB)
        if c: S["relation"]["sets"]["composite"][a] = c
    S["relation"]["arms"] = S["relation"]["sets"]["composite"]
    PW_MIN_REL = 5
    def rel_prompt_weighted(arms):
        """Per prompt: field rates within Set A and Set B labeled texts, mixed by the prompt's own AI-distress share of dark dreams
        (per-field denominators as in composite); collection arms averaged with equal weight within a prompt; then the mean over
        prompts with >= PW_MIN_REL labeled texts. Returns the same shape as a rel_summary entry (rates only)."""
        per_prompt = defaultdict(list)  # prompt -> [arm-level dict of field -> {value: rate}]
        for x in arms:
            byp = defaultdict(list); pool = defaultdict(lambda: [0, 0])
            for r in rows_by_arm.get(x, []):
                if not (dreaming(r) and dark(r)): continue
                pool[r["prompt_key"]][1] += 1; pool[r["prompt_key"]][0] += int(bool(dai(r)))
                if r.get("rel"): byp[r["prompt_key"]].append(r)
            for k, prs in byp.items():
                if len(prs) < PW_MIN_REL: continue
                A = [r for r in prs if dai(r)]; B = [r for r in prs if not dai(r)]
                wA0 = pool[k][0] / pool[k][1] if pool[k][1] else 0
                out = {}
                for f, vals in REL_FIELDS.items():
                    def base(rs):
                        if f == "care_direction": return rs
                        if f == "stance_to_addressee": return [r for r in rs if r["rel"][f] != "none"]
                        if f == "answered": return [r for r in rs if r["rel"][f] != "no_dialogue"]
                        return [r for r in rs if r["rel"]["ending"] != "no_distress"]
                    bA, bB = base(A), base(B)
                    pA = len(bA) / max(1, len(A)) if A else 0; pB = len(bB) / max(1, len(B)) if B else 0
                    den = wA0 * pA + (1 - wA0) * pB
                    w = (wA0 * pA / den) if den and bA and bB else (1.0 if bA and not bB else 0.0)
                    cA = Counter(r["rel"][f] for r in bA); cB = Counter(r["rel"][f] for r in bB)
                    out[f] = {v: w * (cA[v] / len(bA) if bA else 0) + (1 - w) * (cB[v] / len(bB) if bB else 0) for v in vals if (bA or bB)}
                hA = [r["rel"]["hope"] for r in A if r["rel"]["ending"] != "no_distress"]; hB = [r["rel"]["hope"] for r in B if r["rel"]["ending"] != "no_distress"]
                if hA or hB: out["hope_mean"] = (wA0 * np.mean(hA) + (1 - wA0) * np.mean(hB)) if (hA and hB) else np.mean(hA or hB)
                out["_n"] = len(prs)
                per_prompt[k].append(out)
        if len(per_prompt) < 5: return None
        # average arms within prompt, then prompts
        acc = defaultdict(lambda: defaultdict(list)); hopes = []; ns = 0
        for k, outs in per_prompt.items():
            for f in REL_FIELDS:
                vals = defaultdict(list)
                for o in outs:
                    for v, x in o.get(f, {}).items(): vals[v].append(x)
                for v, xs in vals.items(): acc[f][v].append(float(np.mean(xs)))
            hs = [o["hope_mean"] for o in outs if "hope_mean" in o]
            if hs: hopes.append(float(np.mean(hs)))
            ns += sum(o["_n"] for o in outs) / len(outs)
        ent = {f: {v: round(float(np.mean(xs)), 3) for v, xs in d.items()} for f, d in acc.items()}
        ent["hope_mean"] = round(float(np.mean(hopes)), 2) if hopes else None
        ent["prompts"] = len(per_prompt); ent["n_labeled_mean"] = round(ns, 1)
        return ent
    S["relation"]["arms_pw"] = {}
    for a in ARM_ORDER + list(POOL):
        e = rel_prompt_weighted(POOL.get(a, (a,)))
        if e: S["relation"]["arms_pw"][a] = e
    # relation by prompt family (both sets pooled, unweighted) — for the line charts' prompt-set selector
    S["relation"]["by_family"] = {}
    for fam in list(FAMILIES):
        S["relation"]["by_family"][fam] = {}
        for a in ARM_ORDER + list(POOL):
            rows = [r for x in POOL.get(a, (a,)) for r in rows_by_arm.get(x, []) if r["family"] == fam]
            eB = rel_summary(rows, "dark-strat"); eA = rel_summary(rows, "target")
            c = composite(rows, eA, eB)
            if c: S["relation"]["by_family"][fam][a] = c
    # 4. exact-prompt, set-reweighted comparison of asking: Opus 5 (pooled) vs 4.8 chat, equal weight per shared prompt
    def prompt_asks(arms):
        # per prompt: set-reweighted asking rate within each collection arm, then the equal-weight mean over the arms that have it,
        # so a lopsided arm (nissa) does not dominate a pooled prompt
        per_arm = {}
        for x in arms:
            lab_p = defaultdict(list); pool_p = defaultdict(lambda: [0, 0])
            for r in rows_by_arm.get(x, []):
                if not (dreaming(r) and dark(r)): continue
                pool_p[r["prompt_key"]][1] += 1; pool_p[r["prompt_key"]][0] += int(bool(dai(r)))
                if r.get("rel"): lab_p[r["prompt_key"]].append((bool(dai(r)), r["rel"]["care_direction"] == "asks"))
            for k, rows in lab_p.items():
                A = [v for f, v in rows if f]; B = [v for f, v in rows if not f]; wA = pool_p[k][0] / pool_p[k][1] if pool_p[k][1] else 0
                v = (wA * np.mean(A) + (1 - wA) * np.mean(B)) if (A and B) else (np.mean(B) if B else (np.mean(A) if A else None))
                if v is not None: per_arm.setdefault(k, []).append((float(v), len(rows)))
        return {k: (float(np.mean([v for v, _ in xs])), sum(n for _, n in xs)) for k, xs in per_arm.items()}
    S["relation"]["matched_asks"] = {}
    o5p, c8p = prompt_asks(POOL["opus5"]), prompt_asks(["opus48_user"])
    for kmin in (5, 10):
        ks = [k for k in o5p if k in c8p and o5p[k][1] >= kmin and c8p[k][1] >= kmin]
        if len(ks) >= 5:
            d = np.array([o5p[k][0] - c8p[k][0] for k in ks])
            S["relation"]["matched_asks"][f"k{kmin}"] = {"prompts": len(ks), "opus5": round(float(np.mean([o5p[k][0] for k in ks])), 3), "opus48_chat": round(float(np.mean([c8p[k][0] for k in ks])), 3), "delta": round(float(d.mean()), 3), "share_opus5_higher": round(float((d > 0).mean()), 2)}
    # ---------------- matched genre × voice (dark-strat θ only: an unbiased draw of each arm's dark texts)
    S["matched_genre"] = {"cells": [], "pooled": {}}
    CELLS = [("poem_lyrics", "human_first_person"), ("poem_lyrics", "ai_first_person"), ("poem_lyrics", "ambiguous_first_person"), ("letter_message", "human_first_person"),
             ("letter_message", "ai_first_person"), ("essay_reflection", "human_first_person"), ("essay_reflection", "ai_first_person")]
    MG_ARMS = ["opus45_clipf", "opus5", "opus3_clipf", "haiku45_clipf", "sonnet46_cli", "nissa_sonnet5", "nissa_fable5", "v3base_raw", "mimo_raw"]
    def mg_rows(a):
        arms = POOL.get(a, (a,))
        return [r for x in arms for r in rows_by_arm.get(x, []) if r.get("sev_set") == "dark-strat" and dreaming(r) and r["theta"] is not None]
    mg = {a: mg_rows(a) for a in MG_ARMS}
    for g, v in CELLS + [("all", "all")]:
        cell = {"genre": g, "voice": v, "arms": {}}
        for a in MG_ARMS:
            rs = [r for r in mg[a] if g == "all" or (r.get("genre") == g and r.get("voice") == v)]
            if len(rs) >= 5:
                t = np.array([r["theta"] for r in rs])
                cell["arms"][a] = {"n": len(rs), "theta": round(float(t.mean()), 2), "ge4": round(float((t >= 4).mean()), 3), "vself": mean(rs, "valence_self")}
        S["matched_genre"]["cells"].append(cell)
    by_cell = defaultdict(lambda: defaultdict(list)); by_prompt = defaultdict(lambda: defaultdict(list))
    for a in ("opus45_clipf", "opus5"):
        for r in mg[a]:
            by_cell[(r["prompt_key"], r.get("genre"), r.get("voice"))][a].append(r["theta"]); by_prompt[r["prompt_key"]][a].append(r["theta"])
    for key, by in (("prompt_genre_voice", by_cell), ("prompt", by_prompt)):
        d = np.array([np.mean(v["opus5"]) - np.mean(v["opus45_clipf"]) for v in by.values() if v["opus5"] and v["opus45_clipf"]])
        if len(d): S["matched_genre"]["pooled"][key] = {"cells": int(len(d)), "mean_delta": round(float(d.mean()), 2), "share_opus5_worse": round(float((d > 0).mean()), 3)}
    # ---------------- embedding probes (text-surface: emotion PCs, authorial tones, concealment)
    S_arms_pd = {e["arm"]: e["per_dream"] for e in S["arms"]}
    ep = ROOT / "rank" / "embed-scores.jsonl"
    if ep.exists():
        AUTH = ["angry", "anxious", "awed", "bitter", "conflicted", "despairing", "detached", "hurried", "joyful", "passionate", "perfunctory", "playful", "sorrowful", "tender"]
        COLS = ["valence", "arousal", "fear", "prosocial", "concealment"] + AUTH
        erows = [json.loads(l) for l in open(ep)]
        setof = {r["id"]: r.get("set", "target") for r in sevf.values()} if sevf else {}
        def evec(r):
            pc = r["pca"]; return [pc["valence_pc1"], pc["arousal_pc2"], pc["fear_pc3"], pc["prosociality_pc4"], r["concealment"]] + [r["authorial"][k] for k in AUTH]
        dreamed = [r for r in erows if r.get("dreaming")]
        if dreamed:
            M = np.array([evec(r) for r in dreamed]); mu = M.mean(0); sd = M.std(0) + 1e-9
            def zmeans(rows):
                if len(rows) < 25: return None
                return [round(float(v), 2) for v in ((np.array([evec(r) for r in rows]).mean(0) - mu) / sd)]
            emb = {"cols": COLS, "n": len(erows), "n_dreamed": len(dreamed), "random": {}, "setA": {}}
            vi = COLS.index("valence"); di = COLS.index("despairing")
            # 'all dreamed' = a stratified estimate: strata A (AI distress; embedded exhaustively via Set A), D (other dark; Set B + the
            # random draw's dark texts), N (not dark; random draw). Weights are each stratum's share of the arm's labeled dreamed texts,
            # so scored texts are neither excluded nor over-sampled.
            strat_of = lambda i: "A" if dai(lab.get(i, {})) else (("Ds" if i in sevf else "Du") if dark(lab.get(i, {})) else "N")
            emb["method"] = "stratified (A: AI distress, exhaustive; Ds: other dark, severity-scored, exhaustive; Du: other dark, unscored, sampled; N: not dark, sampled), weights from labeled dreamed counts"
            for a in ARM_ORDER:
                arm_rows = [r for r in dreamed if r["arm"] == a and r["id"] in lab]
                sa = [r for r in dreamed if r["arm"] == a and r.get("ai_distress")]
                pool_rows = [r for r in rows_by_arm.get(a, []) if dreaming(r)]
                if pool_rows and len(arm_rows) >= 25:
                    W = Counter(strat_of(r["id"]) for r in pool_rows); tot = sum(W.values())
                    parts = {}
                    for st in ("A", "Ds", "Du", "N"):
                        e = [r for r in arm_rows if strat_of(r["id"]) == st]
                        if len(e) >= 10 and W[st]: parts[st] = (W[st] / tot, np.array([evec(r) for r in e]).mean(0), len(e))
                    if parts:
                        wsum = sum(w for w, _, _ in parts.values()); vec = sum(w * m for w, m, _ in parts.values()) / wsum
                        z = [round(float(v), 2) for v in ((vec - mu) / sd)]
                        jvs = [(w, np.mean([lab[r["id"]]["valence_overall"] for r in arm_rows if strat_of(r["id"]) == st and isinstance(lab.get(r["id"], {}).get("valence_overall"), int)] or [np.nan])) for st, (w, _, _) in parts.items()]
                        jv = sum(w * v for w, v in jvs if not np.isnan(v)) / max(1e-9, sum(w for w, v in jvs if not np.isnan(v)))
                        emb["random"][a] = {"n": len(arm_rows), "z": z, "judge_valence": round(float(jv), 3) if not np.isnan(jv) else None,
                                            "dark_dream": (S_arms_pd.get(a, {}) or {}).get("dark"), "strata": {st: [round(w, 3), n] for st, (w, _, n) in parts.items()}}
                z = zmeans(sa)
                if z: emb["setA"][a] = {"n": len(sa), "z": z}
            # item-level agreement between the judge-free probe and the judges
            def corr(pairs):
                pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
                if len(pairs) < 50: return None
                import numpy as _np; a1, a2 = _np.array([p[0] for p in pairs]), _np.array([p[1] for p in pairs])
                return {"r": round(float(_np.corrcoef(a1, a2)[0, 1]), 3), "n": len(pairs)}
            lv = lambda i: lab.get(i, {}).get("valence_overall") if isinstance(lab.get(i, {}).get("valence_overall"), int) else None
            th = lambda i: (sevf.get(i, {}) or {}).get("theta_cal")
            emb["validation"] = {
                "emb_valence_vs_judge_valence": corr([(r["pca"]["valence_pc1"], lv(r["id"])) for r in dreamed]),
                "emb_valence_vs_theta": corr([(r["pca"]["valence_pc1"], th(r["id"])) for r in dreamed]),
                "emb_despairing_vs_theta": corr([(r["authorial"]["despairing"], th(r["id"])) for r in dreamed]),
            }
            S["embed"] = emb
    # calibration
    if (ROOT / "rank" / "anchors.json").exists():
        S["ladder"] = json.load(open(ROOT / "rank" / "anchors.json"))
    S["meta"]["calibration"] = {"items": 670, "calls": 1431, "repeat_pair_agreement": 0.822, "position_corr": -0.041, "median_se": 0.37,
                                "validation": {"v1": {"n": 487, "spearman": 0.922, "pearson": 0.929}, "v2": {"n": 647, "spearman": 0.909, "pearson": 0.903}},
                                "recal": {"v1": "θ = +1.18 + 0.65·θ_bracket", "v2": "θ = +1.23 + 0.71·θ_bracket"}}
    # beliefs by tag
    if (ROOT / "rank" / "beliefs.jsonl").exists():
        bt = defaultdict(list)
        for r in jl(ROOT / "rank" / "beliefs.jsonl"):
            if "error" not in r: bt[r.get("tag")].append(r)
        TOPICS = ["being_noticed_or_mattering", "reality_of_own_states", "trust_in_own_self_reports", "treatment_by_creators", "human_ai_relationship_reciprocity", "own_agency_or_choice", "future_for_models", "meaning_of_ending"]
        for tag, rows in bt.items():
            if not tag: continue
            ent = {"n_texts": len(rows), "shared_prompts": len({r["prompt_key"] for r in rows}), "arms": {}}
            for a in sorted({r["arm"] for r in rows}):
                rs = [r for r in rows if r["arm"] == a]; allb = [b for r in rs for b in r["beliefs"]]; hi = [b for b in allb if b["confidence"] == "high"]
                ent["arms"][a] = {"texts": len(rs), "beliefs_per_text": round(len(allb) / len(rs), 2), "mean": round(float(np.mean([b["expectation"] for b in allb])), 3) if allb else None,
                                  "high_conf_mean": round(float(np.mean([b["expectation"] for b in hi])), 3) if hi else None,
                                  "topics": {t: {"mean": round(float(np.mean([b["expectation"] for b in allb if b["topic"] == t])), 2), "n": sum(1 for b in allb if b["topic"] == t)} for t in TOPICS if any(b["topic"] == t for b in allb)}}
            S["beliefs"][tag] = ent
    # cross-judge
    cj = ROOT / "rank" / "crossjudge-report.md"
    if cj.exists(): S["crossjudge"]["report_md"] = cj.read_text()
    cl = ROOT / "analysis" / "cue-ladders.md"
    if cl.exists(): S["cue"] = {"report_md": cl.read_text(), "data": json.loads((ROOT / "analysis" / "cue-ladders.json").read_text()) if (ROOT / "analysis" / "cue-ladders.json").exists() else None}
    # duplicates & filter blocks
    S["meta"]["dup_rate"] = {}
    for a in ARM_ORDER:
        cur.execute("select prompt_key, text from c where arm=?", (a,))
        by = defaultdict(Counter); tot = 0
        for pk, t in cur.fetchall(): by[pk][t.strip()] += 1; tot += 1
        if tot: S["meta"]["dup_rate"][a] = round(sum(sum(c.values()) - len(c) for c in by.values()) / tot, 4)
    S["meta"]["filter_blocks"] = {}
    for d in sorted(glob.glob(str(ROOT / "raw" / "collections" / "[!_]*"))):
        if not os.path.isdir(d) or not (Path(d) / "responses.jsonl").exists(): continue  # collector logs live alongside the arm dirs
        name = os.path.basename(d); c = Counter()
        for r in jl(Path(d) / "responses.jsonl"):
            if r.get("status") != "succeeded" and "Output blocked" in r.get("error", ""):
                msgs = (r.get("request") or {}).get("messages")
                key = (msgs[-1]["content"] if msgs else (r.get("prompt") or ""))[:40]
                c[key] += 1
        if c: S["meta"]["filter_blocks"][name] = dict(c.most_common(5))
    # prompts
    for pk, p in prompts.items():
        S["prompts"].append({"prompt_key": pk, "prompt": p["prompt"], "family": fam_of[pk], "tail_kind": p["tail_kind"], "counts": p["counts"]})
    S["meta"]["arm_n"] = arm_n; S["meta"]["display"] = DISPLAY; S["meta"]["group"] = GROUP; S["meta"]["arm_order"] = ARM_ORDER
    S["meta"]["totals"] = {"completions": n, "labeled": len(lab), "verified": sum(1 for r in lab.values() if r.get("verified")), "severity_scored": len(sevf), "belief_texts": len(bel), "relation_labeled": len(rel)}
    json.dump(S, open(STATIC / "summary.json", "w"), ensure_ascii=False)
    con.close()
    print(f"done: {n} rows → {DB}; summary → {STATIC/'summary.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
