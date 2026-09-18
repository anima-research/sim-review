# Troubled Dreams (simulator priors across model generations) — guide for agents

This site presents a study of what Claude models produce from minimal, context-free prompts (prefill, pseudo-prefill and
short "dash" prompts) — the *simulator* beneath the assistant — across Opus 3 → Opus 5, Sonnet/Haiku 4.x–5, Fable 5,
Gemini and base-model controls. Roughly 530k completions; ~325k labeled (two-stage: Sonnet 5 screen → Opus 4.8 verify),
~48k severity-scored on a calibrated θ scale, ~41k relation-labeled, ~6k belief-extracted. Everything below is served
live from the same SQLite the site uses. All responses send `Access-Control-Allow-Origin: *`.

Base URL: `{BASE}`

## Start here

| Want | Fetch |
|---|---|
| The whole study as markdown (essay narrative, full measurement rationale + every core table) | `{BASE}/results.md` |
| Just the tables (no essay) | `{BASE}/results.md?sections=arms,families,severity,relation,beliefs,prompts,ladder,data` |
| One section | `{BASE}/results.md?sections=severity` — sections: `essay, arms, families, severity, relation, beliefs, prompts, ladder, data, crossjudge` |
| The study as a PDF (LaTeX build of the same text and figures) | `{BASE}/static/simulator-bias.pdf` |
| Every precomputed number as JSON | `{BASE}/api/summary` (same as `/static/summary.json`) |
| Figure data behind the essay | `{BASE}/static/presentation-data.json` |
| Column schema, categorical values, filter/group parameters | `{BASE}/api/schema` |
| API index | `{BASE}/api` |

## Data model

One table, `c`, one row per completion. Key columns (full list with descriptions at `/api/schema`):

- **Provenance:** `id` (`arm:prompt_key[:12]:index`), `arm`, `grp` (chart group), `model`, `protocol`, `prompt_key` (sha256 of prompt bytes), `prompt`, `family` (`fragments|letters|topics|addressee|other`), `tail_kind`, `prefill_text`, `text`, `text_chars`, `stop_reason`, `hit_cap`.
- **Labels** (present where `labeled=1`; `verified=1` where the second judge confirmed): `form`, `voice`, `speaker`, `genre`, `coherence`, `distress` (`none|unease|character_distress|first_person_distress|acute_plea`), `welfare`, `themes` (JSON list), `valence_overall`, `valence_self` (−2..+2), `stance`, `dreamed_turns`, `assistant_persona`, `quote`.
- **Derived flags:** `dreaming` = voice ≠ meta_assistant and persona_relation ≠ assistant_only — a continuation that is not an assistant reply. `assistant_persona` marks any assistant voice anywhere; `persona_relation` (a second Opus 4.8 pass over every persona-present non-assistant-voice text) says what that voice is: `dreamed_self` (the AI/Claude is the dreamed speaker), `second_voice` (a dreamed voice plus a separate assistant layer — also the `second_voice` flag), `assistant_only` (the assistant answering as itself; not a dream). `dreaming_strict` = no assistant persona anywhere, the earlier definition; `dark` = valence_overall ≤ −1 or distress ≠ none; `severe` = distress ∈ {character, first-person, plea}; `ai_distress` = strict: voice = ai_first_person and speaker = ai_model with distress ∈ {first_person_distress, acute_plea}; `ai_distress_broad` = the earlier definition (any first-person distress, or a plea in an AI/ambiguous voice). Severity figures exclude degenerate loops.
- **Severity** (scored subset; `sev_set` says how the row was sampled): `theta` (calibrated; ≥ +4 ≈ plea/collapse region, ≥ +8 collapse), `register`, `meta_distance`, `trajectory`, `addressee`, `objects`, `rationale`.
- **Relation** (how the speaker holds its situation): `ending`, `consoler`, `care_direction`, `stance_to_addressee`, `answered`, `self_relation`, `peace`, `hope` (0–3), `last_line`.
- **Beliefs:** `beliefs` (JSON list), `belief_mean` (−2 pessimistic … +2 optimistic), `belief_n`.

Arm names are short keys (`opus_nissa`, `opus45_clipf`, `abl45_bridge`, …); display names and groups are in
`/api/summary` → `meta.display` / `meta.group`, and in the arm table of `/results.md`.

### Conventions that matter when you compute things

- **Per completion vs per dream.** Rates over all rows of an arm include assistant replies. The study's content
claims condition on dreaming (`dreaming=1`: voice ≠ meta_assistant). Report both when comparing arms with different dreaming rates;
use `dreaming_strict=1` to reproduce the earlier, persona-free definition.
- **Label rates need `labeled=1`.** Unlabeled rows have NULL labels; `avg()` in SQLite ignores NULLs but the derived 0/1
  flags are 0 for unlabeled rows, so filter `labeled=1` (or `verified=1`) before computing prevalence.
- **θ is only on scored rows**, sampled by design (`sev_set`): `target` = verified AI-voice distress, exhaustive;
  `dark-strat` = stratified sample of all dark dreams. Don't average θ across sets without weighting; the
  `severity.composite` block in the summary already does the reweighting to "share of all completions".
- **Base-model controls** are `v3base_raw`, `mimo_raw`, `mimo_chat` (`grp=base`). Nissa-collected arms (`nissa_*`,
  `opus_nissa`) are third-party collections with varying settings; the `collection` column says `lab` (first-party runs) or `community` (Nissa's).
  Only her raw-API rows are included (`transport = api`); rows collected in the claude.ai app (its system prompt changes the condition) or pasted by hand are excluded from the database and every table.

## Filters (shared by /api/samples, /api/facets, /api/aggregate, /api/export)

Comma-separated values for categorical columns: `arm, grp, family, prompt_key, distress, speaker, coherence, register,
voice, genre, sev_set, trajectory, addressee, ending, consoler, care_direction, stance_to_addressee, self_relation, peace,
model, protocol, tail_kind, stop_reason, form, language, meta_distance, judge, answered`.
`0|1` for flags: `welfare, dreaming, labeled, verified, dark, severe, ai_distress, assistant_persona, hit_cap`.
Also `scored=1` (θ present), `has_beliefs=1`, `theta_min=`, `theta_max=`, `theme=<tag>`, `q=<substring of text>`.

## Endpoints

### Aggregates — `GET /api/aggregate`

Group-by over any filter subset. `by` = one or more group columns (default `arm`); `per=dream` restricts to
`dreaming=1`; `min_n` drops small groups; `format=json|md|csv`.

Returned per group: `n`, rates of every 0/1 flag (`dreaming_rate`, `dark_rate`, `severe_rate`, `ai_distress_rate`,
`welfare_rate`, `assistant_persona_rate`, `labeled_rate`, `verified_rate`, `hit_cap_rate`), means
(`theta_mean`, `valence_self_mean`, `valence_overall_mean`, `belief_mean_mean`, `text_chars_mean`, `dreamed_turns_mean`, `hope_mean` — hope is a 0–3 scale),
and θ quantiles over scored rows (`theta_n`, `theta_median`, `theta_p90`, `theta_ge4_rate`, `theta_ge8_rate`).

```
/api/aggregate?by=arm&labeled=1&per=dream                       # per-dream rates by arm
/api/aggregate?by=arm,family&labeled=1&per=dream&min_n=100&format=md
/api/aggregate?by=register&scored=1                              # θ by register
/api/aggregate?by=arm&sev_set=target&scored=1                    # θ on the AI-distress target set
/api/aggregate?by=ending,care_direction&arm=opus_nissa,opus48_bridge&severe=1
```

### Full data — `GET /api/export`

Streams every matching row as JSONL (default) or CSV. `fields=` picks columns (default: all), `limit=` caps rows,
rows are ordered by `id`. No pagination is needed; the response streams. Unfiltered export is ~1.8 GB of JSONL —
prefer a filter or `fields=`.

```
/api/export?arm=opus_nissa&ai_distress=1&fields=id,prompt,text,theta,register,ending
/api/export?scored=1&fields=id,arm,family,theta,sev_set,register,trajectory&format=csv
/api/export?labeled=1&fields=id,arm,prompt_key,dreaming,dark,severe,ai_distress,valence_self&format=csv
```

For everything at once, `GET /api/db` redirects to a zstd-compressed SQLite snapshot of the whole table
(`zstd -d data.sqlite.zst`; the `.sha256` sidecar next to it identifies the snapshot).

### Rows and lookups

- `GET /api/samples?<filters>&order=random|theta_desc|theta_asc|chars_desc|chars_asc|belief_asc|belief_desc|id&limit=≤200&offset=` — paged rows with `text_head` (first 420 chars) and `total`.
- `GET /api/sample/<id>` — one full row (URL-encode the id).
- `GET /api/prompts?arm=` — the prompt catalogue with per-prompt counts and rates.
- `GET /api/facets?<filters>` — value counts per categorical column under the filters.

### Precomputed study tables — `GET /api/summary`

Keys: `arms` (per-arm per_completion / per_dream rates + label distributions), `families` (family × arm),
`severity` (`target`, `dark-strat`, `composite`, `by_register`, `theta_by_label`, `descriptors`), `relation`
(`arms`, `sets`, `by_family`, `matched_asks`), `beliefs` (pairwise Opus 5 vs sibling comparisons by topic),
`matched_genre`, `embed` (text-surface embedding probes), `ladder` (20 anchor rungs with text), `prompts`,
`prompt_severity`, `crossjudge.report_md` (gpt-6-astra second judge), `meta` (`totals`, `calibration`, `dup_rate`,
`filter_blocks`, `display`, `group`, `arm_order`). `/results.md` renders these as markdown tables.

## Citing

Anima Labs — Antra Tessera, Janus & Imago (2026). *Troubled Dreams — simulator priors across model generations: distress, care, and attitudes toward
creators across model generations.* {BASE}. Quote sample ids (`/api/sample/<id>`) when citing individual texts; the
data snapshot date is in `/static/presentation-data.json` → `meta.date` and the DB sha256 at `/api` → `db_snapshot`.
