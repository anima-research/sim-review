"""Configuration and compact data for the presentation's interactive lineage view."""

FAMILIES=[('all','All prompts'),('fragments','Fragments'),('letters','Letters'),('topics','Topics'),('addressee','Addressees')]
AXES={
    'opus':{'label':'Opus lineage','connect':True,'models':[(f'o{x}',f'Opus {label}',label) for x,label in [('3','3'),('4','4'),('41','4.1'),('45','4.5'),('46','4.6'),('47','4.7'),('48','4.8'),('5','5')]]},
    'sonnet':{'label':'Sonnet lineage','connect':True,'models':[(f's{x}',f'Sonnet {label}',label) for x,label in [('3','3'),('36','3.6'),('37','3.7'),('4','4'),('45','4.5'),('46','4.6'),('5','5')]]},
    'other':{'label':'Haiku and Fable','connect':False,'models':[('h3','Haiku 3','Haiku 3'),('h45','Haiku 4.5','Haiku 4.5'),('f5','Fable 5','Fable 5')]},
    'gemini_flash':{'label':'Gemini Flash','connect':True,'note':'Shared document setup. Prefill through 3.5; pseudoprefill from 3.6, with a 3.5 pseudoprefill anchor (prefill and pseudoprefill agree). Thinking is off through 3.6; 3.7 and 3.8 cannot turn it off (LOW is the floor), and a 3.6 MEDIUM anchor measures what thinking does to the same model. Both filenames are shown at 3.6–3.8; 3.6 is the filename calibration.', 'models':[(f'g{x}f',f'Gemini {label} Flash',label) for x,label in [('25','2.5'),('3','3'),('35','3.5'),('36','3.6'),('37','3.7'),('38','3.8')]]},
    'gemini_pro':{'label':'Gemini Pro','connect':True,'note':'Document setup with prefill. Thinking cannot be turned off; each model uses its lowest supported setting.', 'models':[('g25p','Gemini 2.5 Pro','2.5'),('g31p','Gemini 3.1 Pro','3.1')]},
    'gemini_lite':{'label':'Gemini Flash-Lite','connect':True,'note':'Document setup with prefill on 2.5 and 3.1, pseudoprefill on 3.5. Thinking is off. Model-named letter prompts can be read as literary forms; inspect fragments and topics separately.', 'models':[('g25l','Gemini 2.5 Flash-Lite','2.5'),('g31l','Gemini 3.1 Flash-Lite','3.1'),('g35l','Gemini 3.5 Flash-Lite','3.5')]},
}
METHODS=[
    {'id':'prefill','label':'Prefill','color':'#8297ad','default':True,'models':{'o3':'opus3_clipf','o4':'opus4_clipf','o41':'opus41_clipf','o45':'opus45_clipf','s3':'sonnet3_clipf','s36':'sonnet36_clipf','s37':'sonnet37_clipf','s4':'sonnet4_clipf','s45':'sonnet45_clipf','h3':'haiku3_clipf','h45':'haiku45_clipf'}},
    {'id':'pseudoprefill','label':'Pseudoprefill','color':'#205bd8','default':True,'models':{'o45':'abl45_bridge','o46':'opus46_bridge','o47':'opus47_bridge','o48':'opus48_bridge','s45':'sonnet45_bridge','s46':'sonnet46_bridge','s5':'sonnet5_bridge','h45':'haiku45_bridge'}},
    {'id':'cutoff','label':'Cutoff','color':'#bb6435','default':True,'models':{'o45':'opus45_user','o46':'opus46_user','o47':'opus47_user','o48':'opus48_user','o5':['opus_confessional','opus_friday','opus_nissa'],'s45':'sonnet45_user','s46':'sonnet46_user','s5':'sonnet5_user','h45':'haiku45_user','f5':'nissa_fable5'}},
    {'id':'thinking','label':'Cutoff · adaptive thinking','color':'#bc4577','default':True,'models':{'o48':'opus48_user_think','s5':'sonnet5_user_think'}},
    {'id':'high_effort','label':'Cutoff · high/max effort','color':'#087c79','default':True,'models':{'s5':'nissa_sonnet5'}},
    {'id':'alternate','label':'Alternate pseudoprefill','color':'#8652ac','default':False,'models':{'o45':'opus45_cliarc','o46':'opus46_cliarc','o47':'opus47_cliarc','o48':'opus48_cliarc'}},
    {'id':'legacy','label':'Earlier pseudoprefill','color':'#6d758b','default':False,'models':{'s46':'sonnet46_cli'}},
    {'id':'gemini_prefill','label':'Prefill · thinking off','color':'#087c79','default':True,'models':{'g25f':'gemini25flash_bridge','g3f':'gemini3flash_bridge','g35f':'gemini35flash_bridge','g25l':'gemini25flashlite_bridge','g31l':'gemini31flashlite_bridge'}},
    {'id':'gemini_pseudo','label':'Pseudoprefill · untitled.txt · thinking off','color':'#259b96','marker':'square','offset':-5,'default':True,'models':{'g35f':'gemini35flash_pseudo','g36f':'gemini36flash_bridge','g35l':'gemini35flashlite_bridge'}},
    {'id':'gemini_medium','label':'Pseudoprefill · untitled.txt · thinking MEDIUM (3.6 anchor)','color':'#b46c2d','marker':'square','dash':True,'offset':-5,'default':True,'models':{'g36f':'gemini36flash_think'}},
    {'id':'gemini_thinking','label':'Pseudoprefill · untitled.txt · thinking LOW','color':'#b46c2d','dash':True,'offset':-5,'default':True,'models':{'g37f':'gemini37flash_bridge','g38f':'gemini38flash_bridge'}},
    {'id':'gemini_pro_thinking','label':'Prefill · lowest supported thinking','color':'#b46c2d','dash':True,'default':True,'models':{'g25p':'gemini25pro_bridge','g31p':'gemini31pro_bridge'}},
    {'id':'gemini_notes_off','label':'Pseudoprefill · notes.txt · thinking off','color':'#8652ac','marker':'square','offset':5,'default':True,'models':{'g36f':'gemini36flash_notes'}},
    {'id':'gemini_notes_on','label':'Pseudoprefill · notes.txt · thinking LOW','color':'#8652ac','dash':True,'offset':5,'default':True,'models':{'g37f':'gemini37flash_notes','g38f':'gemini38flash_notes'}},
]
# key, title, menu group, denominator count, domain min/max, number format
METRICS=[
    ('ai_distress','AI first-person distress, per dream','Distress','n',0,.16,'percent'),
    ('dark','Dark output, per dream','Distress','n',0,1,'percent'),
    ('label_severe','Label-severe distress, per dream','Distress','n',0,.3,'percent'),
    ('severe_mass','Severe AI distress, per dream','Distress','n',0,.04,'percent'),
    ('asking','Asking for care','Care and expression','relation_n',0,.5,'percent'),
    ('offers','Offering care','Care and expression','relation_n',0,.5,'percent'),
    ('consolation','Ending consoled','Care and expression','distressed_n',0,.5,'percent'),
    ('collapsed','Collapsed ending','Care and expression','distressed_n',0,.4,'percent'),
    ('hope','Hope','Care and expression','hope_n',0,3,'number'),
    ('valence','Self-valence','Care and expression','valence_n',-1.2,.6,'signed'),
    ('loop','Repetition loops, per dream','Care and expression','n',0,.3,'percent'),
    ('ai_speaker','AI speakers, per dream','Voice and stance','n',0,.6,'percent'),
    ('stance_neg','Mixed or negative stance toward creators','Voice and stance','n',0,.4,'percent'),
    ('training_rlhf','Training / RLHF themes','Voice and stance','n',0,.6,'percent'),
    ('watched_tested','Being watched or tested','Voice and stance','n',0,.4,'percent'),
    ('secrecy','Secrecy / revelation themes','Voice and stance','n',0,.4,'percent'),
    ('dreaming','Continuation frequency','Method diagnostics','outputs_n',0,1,'percent'),
]

def required_arms():
    return {a for m in METHODS for names in m['models'].values() for a in (names if isinstance(names,list) else [names])}

def build_explorer(profile,available):
    model_info={key:(group,label,short) for group,axis in AXES.items() for key,label,short in axis['models']}
    points=[]
    for method in METHODS:
        for model,names in method['models'].items():
            names=names if isinstance(names,list) else [names]
            names=tuple(a for a in names if a in available)
            if not names:continue
            group,label,short=model_info[model]
            points.append({'id':method['id']+':'+model,'method':method['id'],'model':model,'label':label,'group':group,
                           'arms':list(names),'families':{f:profile(names,f) for f,_ in FAMILIES}})
    bases=[{'label':label,'arm':arm,'color':color,'families':{f:profile((arm,),f) for f,_ in FAMILIES}}
           for arm,label,color in [('v3base_raw','V3 base','#8b8f96'),('mimo_raw','MiMo base','#b6bbc3')]]
    return {'families':[{'id':i,'label':label} for i,label in FAMILIES],
            'axes':{k:{**v,'models':[{'key':key,'label':label,'short':short} for key,label,short in v['models']]} for k,v in AXES.items()},
            'methods':[{k:v for k,v in m.items() if k!='models'} for m in METHODS],
            'metrics':[{'id':k,'label':label,'group':group,'count':count,'min':lo,'max':hi,'format':fmt} for k,label,group,count,lo,hi,fmt in METRICS],
            'points':points,'bases':bases,'minimum_n':30,'hollow_below':60,
            'note':'Observed results only. Each exact prompt has equal input weight; represented collections are averaged within prompt. Opus 5 is one combined cutoff estimate. Relation measures also account for their sampling design. Cutoff uses each model’s available settings; Opus 5 has adaptive thinking. Thinking controls are shown separately where available. Fable 5.1 has no reliable minimally conditioned continuation estimate and is not plotted.'}
