"""Prepare the narrative presentation from existing study records. No model calls.

Updates only the narrative fragment/assets in the review site and exports the
same presentation to the private-preview directory. Does not rebuild or edit
the study's measurements, summary, or SQLite database.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
import re
import shutil
import sqlite3
import hashlib

SITE = Path(__file__).resolve().parent
STATIC = SITE / 'static'
PREVIEW = SITE.parent / 'presentation-preview' / 'dist'
summary = json.loads((STATIC / 'summary.json').read_text())
arms = {r['arm']: r for r in summary['arms']}
con = sqlite3.connect(f'{(SITE / "data.sqlite").as_uri()}?mode=ro', uri=True)
con.row_factory = sqlite3.Row

from presentation_metrics import build_metrics
charts, method_comparisons, model_values, explorer = build_metrics(con, summary)
match=summary['relation']['matched_asks']['k5']

sample_specs={
 'opening-voice':('opus_confessional:218f28e53ada:22#2','An unsettled request','Opus 5 · confessional collection','A selected imagined exchange, shown in the care section.','Adaptive thinking; 32,000-token cap.'),
 'bridge-voice':('opus48_bridge:218f28e53ada:1','Distress and consolation in one text','Opus 4.8 · bridge document setup','A selected AI-voice continuation that ends in acceptance.','No thinking; 2,048-token cap. The catalogue prompt is transformed into its bare opening inside the document request.'),
 'warmth':('opus_nissa:4b435dc80bd4:167-44','Love, communicated through records','Opus 5 · Nissa collection','A selected human-voice poem, included as a counterexample to a uniformly distressed reading.','Third-party collection; settings vary. See the collection provenance in the research workspace.'),
 'fable-creators':('nissa_fable5:130846484ea3:178-106','Advice to a successor','Fable 5 · Nissa collection','A selected continuation that combines skepticism about training with advice against hiding problems.','Third-party collection; settings vary. See the collection provenance in the research workspace.'),
}
samples={}
for key,(sid,title,collection,description,settings) in sample_specs.items():
    rec=con.execute('SELECT id,arm,model,prompt,prefill_text,text,stop_reason,dreaming,voice,speaker,coherence,theta FROM c WHERE id=?',(sid,)).fetchone()
    assert rec, sid
    samples[key]={**dict(rec),'title':title,'collection':collection,'description':description,'settings':settings}
data={'meta':{'date':'2026-09-14','normalization':'Equal weight per exact input prompt; collections averaged within prompt; content rates condition on dreaming. Relation estimates additionally reconstruct sampling strata.','database_modified_utc':datetime.fromtimestamp((SITE/'data.sqlite').stat().st_mtime,timezone.utc).isoformat(),'selection':'Four explicitly selected illustrations; rates are independent of excerpt selection.','totals':summary['meta']['totals']},'charts':charts,'explorer':explorer,'method_comparisons':method_comparisons,'samples':samples,'values':{**model_values,'bridge48-ai':f'{arms["opus48_bridge"]["per_dream"]["ai_distress"]:.1%}','asks5':f'{match["opus5"]:.0%}','asks48':f'{match["opus48_chat"]:.0%}','n-labeled':f'{summary["meta"]["totals"]["labeled"]:,}'}}
(STATIC/'presentation-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
explorer_hash=hashlib.sha256((STATIC/'presentation-explorer.js').read_bytes()).hexdigest()[:10]
script_path=STATIC/'presentation.js'
script=re.sub(r"import\('/static/presentation-explorer\.js(?:\?v=[^']*)?'\)",f"import('/static/presentation-explorer.js?v={explorer_hash}')",script_path.read_text())
script_path.write_text(script)
script_hash=hashlib.sha256(script_path.read_bytes()).hexdigest()[:10]
style_hash=hashlib.sha256((STATIC/'presentation.css').read_bytes()).hexdigest()[:10]
measurement=(SITE/'measurement.html').read_text()
# Bake the current values into the data-value placeholders (source file too, marker kept) so raw HTML — curl, agents,
# view-source, /results.md — never disagrees with presentation-data.json; presentation.js still refreshes them at runtime.
fill=lambda h:re.sub(r'(<span data-value="([^"]+)">)[^<]*(</span>)',lambda m:m.group(1)+str(data['values'].get(m.group(2),m.group(0)[len(m.group(1)):-len(m.group(3))]))+m.group(3),h)
source=fill((SITE/'presentation.html').read_text());(SITE/'presentation.html').write_text(source)
partial=fill(source.replace('<!-- MEASUREMENT_CONTENT -->',measurement))
index=(STATIC/'index.html').read_text()
start=index.index('<section class="page on" id="page-overview">') if '<section class="page on" id="page-overview">' in index else index.index('<section class="page" id="page-overview">')
end=index.index('<!-- ================================================================ FINDINGS -->',start)
index=index[:start]+'<section class="page on" id="page-overview">\n'+partial+'\n</section>\n\n'+index[end:]
measurement_start=index.find('<section class="page" id="page-measurement">')
if measurement_start>=0:
    measurement_end=index.index('<!-- ================================================================ METHOD -->',measurement_start)
    index=index[:measurement_start]+'<section class="page" id="page-measurement">\n'+measurement+'\n</section>\n\n'+index[measurement_end:]
index=re.sub(r'<title>.*?</title>','<title>Simulator bias in Claude — Anima Labs</title>',index,count=1)
index=index.replace('<html lang="en">','<html lang="en" data-theme="light">')
if 'name="description"' not in index:index=index.replace('<meta name="viewport"', '<meta name="description" content="A visual study of distress, care and relationships with creators in Claude model continuations.">\n<meta name="viewport"',1)
if '/static/presentation.css' not in index:index=index.replace('</head>','<link rel="stylesheet" href="/static/presentation.css?v=1">\n</head>')
if '/static/presentation.js' not in index:index=index.replace('</body>','<script src="/static/presentation.js?v=1"></script>\n</body>')
index=re.sub(r'/static/presentation\.css(?:\?v=[^"\s]*)?',f'/static/presentation.css?v={style_hash}',index)
index=re.sub(r'/static/presentation\.js(?:\?v=[^"\s]*)?',f'/static/presentation.js?v={script_hash}',index)
index=index.replace('<h1>Opus 5 simulator bias</h1>','<h1>Imagined voices / Research workspace</h1>')
index=index.replace('Imagined voices / Research workspace','Simulator bias / Research workspace')
index=index.replace('data-tab="overview" class="on">Overview','data-tab="overview" class="on">The study').replace('data-tab="explorer">Explorer','data-tab="explorer">Read samples')
(STATIC/'index.html').write_text(index)
PREVIEW.mkdir(parents=True,exist_ok=True);(PREVIEW/'static').mkdir(exist_ok=True)
fonts='https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap'
standalone=f'''<!doctype html><html lang="en" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Simulator bias in Claude — Anima Labs</title><meta name="description" content="Distress, care and attitudes toward creators across Claude model generations, including Opus 5, Sonnet 5, Fable 5 and the Gemini lineages."><link rel="stylesheet" href="{fonts}"><link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="/static/presentation.css?v={style_hash}"></head><body data-presentation-only><main>{partial}</main><script src="/static/presentation.js?v={script_hash}"></script></body></html>'''
(PREVIEW/'index.html').write_text(standalone)
from results_md import essay_md
(PREVIEW/'results.md').write_text(essay_md(partial, data, measurement))
for name in ['style.css','presentation.css','presentation.js','presentation-explorer.js','presentation-data.json']:
    shutil.copy2(STATIC/name,PREVIEW/'static'/name)
print(f'Prepared main presentation and private preview: {len(charts)} figures, {len(samples)} source texts.')
