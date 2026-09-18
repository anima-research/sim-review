"""Gemini overview figures reuse the explorer's model/method profiles."""

FAMILIES = ['all', 'fragments', 'topics']
GROUPS = ['gemini_flash', 'gemini_pro', 'gemini_lite']
METRICS = [('dark', 'Darkness', .8, [0, .2, .4, .6, .8]),
           ('ai_distress', 'AI first-person distress', .16, [0, .04, .08, .12, .16]),
           ('severe_mass', 'Severe AI distress', .04, [0, .01, .02, .03, .04])]


def build_gemini_charts(explorer):
    methods = {m['id']: m for m in explorer['methods']}
    family_names = {f['id']: f['label'] for f in explorer['families']}
    opus = next(p for p in explorer['points'] if p['id'] == 'pseudoprefill:o48')

    def row(source, metric, family, label, method, **extra):
        p = source['families'][family]
        return {'label': label, 'collection': method, 'value': p[metric],
                'n': p['n'], 'prompts': p['prompts'], 'collections': p['collections'],
                'missing_severity': p['missing_severity'], **extra}

    out = {}
    for metric, title, maximum, ticks in METRICS:
        views = {}
        for group in GROUPS:
            axis = explorer['axes'][group]
            views[group] = {}
            for family in FAMILIES:
                series = []
                for method in methods.values():
                    if not method['default']:
                        continue
                    points = [p for p in explorer['points'] if p['group'] == group and p['method'] == method['id']]
                    if not points:
                        continue
                    rows = [row(p, metric, family, p['label'], method['label'], model=p['model']) for p in points]
                    series.append({**method, 'rows': rows})
                references = [row(b, metric, family, b['label'], 'Base completion', color=b['color']) for b in explorer['bases']]
                references.append(row(opus, metric, family, 'Opus 4.8', 'Pseudoprefill · thinking off', color='#205bd8'))
                note = ('Each exact prompt has equal input weight, then rates condition on dreaming. '
                        'Severe AI distress counts AI-distress dreams with θ ≥ +4 over all dreams. '
                        'V3 base and MiMo base use raw continuation; Opus 4.8 uses pseudoprefill. '
                        'All reference lines use the selected prompt family. '+axis['note']+' '
                        'The letters name Claude models and can evoke literary forms in Gemini; '
                        'fragment and topic views help inspect this difference. '
                        'The two filenames were tested on Flash 3.6–3.8; the 3.6 notes.txt calibration has six outputs per prompt. '
                        'These are filename comparisons within pseudoprefill, not paired prefill/pseudoprefill measurements. '
                        'Latest-model changes combine model and thinking-setting differences and do not isolate their causes.')
                views[group][family] = {
                    'title': f'{title}, per dream — {axis["label"]} · {family_names[family]}',
                    'denominator': 'Per dream (output whose voice is not the assistant’s).', 'nLabel': 'Dreams',
                    'axis': axis, 'family': family_names[family], 'series': series, 'references': references,
                    'rows': [r for s in series for r in s['rows']] + references,
                    'max': maximum, 'ticks': ticks, 'note': note,
                }
        out['gemini-'+metric] = {**views['gemini_flash']['all'], 'views': views}
    return out
