# Troubled Dreams — review site

Simulator bias across model generations: distress, care, and attitudes toward creators.

Source of the study site at **https://sim-review-production.up.railway.app** (Anima Labs): the essay, the results tables,
the sample explorer, and the agent API (`/agents.md`, `/results.md`, `/api`). The 1.8 GB SQLite of all completions is not
in this repo; it is published separately and fetched by the container (see `DEPLOY.md`).

## Annotating the text (collaborators)

Review happens on the standing pull request **“Review: essay and results”**. It adds `ESSAY.md` (the narrative) and
`RESULTS.md` (every core table) with **one sentence per line**, so a comment anchors to a sentence:

1. Open the PR → **Files changed**.
2. Hover a line → click the blue **+** → write the comment (or select a range: click the first line's +, shift-click the last).
3. Use **Start a review** to batch comments, then **Submit review**.
4. General remarks go in the PR conversation or in an Issue.

When the text is regenerated, the branch is updated and the PR keeps every thread (comments on changed lines are marked
“outdated”, not lost). Don't edit `ESSAY.md` / `RESULTS.md` directly — they are generated from `presentation.html`,
`static/summary.json` and `static/presentation-data.json`; the same content is served live at `/results.md`.

## Layout

| Path | What |
|---|---|
| `presentation.html` | The essay (HTML fragment; live numbers are `data-value` spans, baked in by `prepare_presentation.py`) |
| `static/` | Site assets: `index.html` (workspace), `app.js`, `presentation*.js/css`, `summary.json` (all precomputed tables), `presentation-data.json` (figure data) |
| `serve.py` | Stdlib HTTP server: static + `/api/*` + `/results.md` + `/agents.md` |
| `results_md.py`, `export_md.py` | Markdown rendering of the study (live route, and the review files) |
| `export_pdf.py`, `paper-header.tex`, `neurips_2025.sty` | LaTeX/PDF build (NeurIPS preprint layout): matplotlib figures from `presentation-data.json`, pandoc → `paper/simulator-bias.tex`, tectonic → `static/simulator-bias.pdf`. The `.tex` is generated; edit the sources, not the LaTeX. |
| `build.py`, `prepare_presentation.py`, `presentation_*.py` | Build pipeline: labels/severity/beliefs → `data.sqlite` + `summary.json` → presentation export (needs the private data checkout) |
| `Dockerfile`, `entrypoint.sh`, `publish_db.py`, `DEPLOY.md` | Railway deployment and the incremental DB publish |
| `AGENTS.md` | Guide for agents using the API |

## Regenerating

```
python3 build.py                  # data.sqlite + static/summary.json          (private data)
python3 prepare_presentation.py   # essay values, presentation-data.json, index.html
python3 export_md.py              # ESSAY.md + RESULTS.md for the review branch
python3 export_pdf.py             # paper/simulator-bias.tex + static/simulator-bias.pdf (pandoc, tectonic, matplotlib)
```
