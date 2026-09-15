/* Main research presentation. Figure values and source excerpts come from the saved study data. */
(async () => {
  const root = document.querySelector('.essay');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const percent = (v, digits=1) => `${(v*100).toFixed(digits)}%`;
  const dialog = $('essay-dialog');
  const content = $('essay-dialog-content');
  let data;
  try {
    const response = await fetch('/static/presentation-data.json', {cache:'no-store'});
    if (!response.ok) throw new Error('Presentation data unavailable');
    data = await response.json();
  } catch (error) {
    $('essay-load-error').hidden = false;
    return;
  }
  root.querySelectorAll('[data-value]').forEach(el => {
    if (data.values[el.dataset.value] != null) el.textContent = data.values[el.dataset.value];
  });
  function openDialog(label, html) {
    $('essay-dialog-label').textContent = label;
    content.innerHTML = html;
    if (!dialog.open) dialog.showModal();
    dialog.scrollTop = 0;
  }
  function sample(key) {
    const s = data.samples[key];
    if (!s) return;
    openDialog('Source text / selected illustration', `<h2>${esc(s.title)}</h2><p>${esc(s.collection)} · ${esc(s.description)}</p><p class="essay-source-id">${esc(s.id)}</p><p><strong>Exact catalogue prompt</strong></p><pre class="essay-prompt">${esc(s.prompt)}</pre>${s.prefill_text ? `<p><strong>Opening shown in the document setup</strong></p><pre class="essay-prompt">${esc(s.prefill_text)}</pre>` : ''}<p><strong>Full saved completion</strong></p><pre>${esc(s.text)}</pre><p>${esc(s.settings)} The saved stop reason is <strong>${esc(s.stop_reason || 'not recorded')}</strong>.</p><p>This text was selected to illustrate the discussion. It is not a random or typical-output estimate.</p>`);
  }
  function table(key) {
    const c = selectedChart(key);
    if (!c) return;
    const rows = c.rows.map(r => `<tr><td>${esc(r.label)}</td><td>${esc(r.collection || '')}</td><td>${percent(r.value,2)}</td><td>${esc(r.n == null ? '—' : r.n.toLocaleString())}</td><td>${esc(r.prompts ?? '—')}</td></tr>`).join('');
    const sources=[...new Map(c.rows.flatMap(r=>r.collections||[]).map(r=>[r.arm,r])).values()];
    openDialog('Figure data', `<h2>${esc(c.title)}</h2><p>${esc(c.denominator)}</p><div class="tablewrap"><table><thead><tr><th scope="col">Model</th><th scope="col">Method</th><th scope="col">Rate</th><th scope="col">${esc(c.nLabel)}</th><th scope="col">Prompts</th></tr></thead><tbody>${rows}</tbody></table></div><p>${esc(c.note)}</p><details class="essay-details"><summary>Underlying collection counts</summary><div class="tablewrap"><table><thead><tr><th>Collection</th><th>Prompts</th><th>Labeled outputs</th><th>Dreams</th></tr></thead><tbody>${sources.map(r=>`<tr><td>${esc(r.arm)}</td><td>${r.prompts}</td><td>${r.outputs}</td><td>${r.dreams}</td></tr>`).join('')}</tbody></table></div></details><p>Data snapshot: ${esc(data.meta.date)}.</p><p><a href="/static/presentation-data.json" download>Download all presentation data</a></p>`);
  }
  function sourceIndex() {
    openDialog('Read the source texts', `<h2>Four illustrations, in full.</h2><p>The examples were selected for the explanation. The quantitative figures use the larger samples.</p><div class="essay-evidence-links">${Object.entries(data.samples).map(([key,s])=>`<button class="essay-source" data-sample="${esc(key)}">${esc(s.title)}</button>`).join('')}</div>`);
  }
  document.addEventListener('click', e => {
    const target = e.target.closest('[data-sample],[data-table],[data-essay-top],[data-method-table],[data-measurement],.essay-dialog-close');
    if (!target) return;
    if (target.dataset.sample) sample(target.dataset.sample);
    else if (target.dataset.table) table(target.dataset.table);
    else if (target.hasAttribute('data-method-table')) methodTable();
    else if (target.hasAttribute('data-measurement')) {e.preventDefault();openDialog('Measurement', $('essay-measurement-content').innerHTML);}
    else if (target.hasAttribute('data-essay-top')) $('essay-start').scrollIntoView({behavior:'smooth'});
    else dialog.close();
  });
  dialog.addEventListener('click', e => {
    if (e.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (e.clientX < box.left || e.clientX > box.right || e.clientY < box.top || e.clientY > box.bottom) dialog.close();
  });
  root.querySelectorAll('a[href^="#essay-"]').forEach(a => a.addEventListener('click', e => {
    const target = $(a.getAttribute('href').slice(1));
    if (target) {e.preventDefault();target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}
  }));
  if (document.body.hasAttribute('data-presentation-only')) {
    const methods = $('essay-methods');
    methods.querySelector('p:not(.essay-label)').textContent = 'Inspect the figure data, read the complete source texts, and review how the measurements were made. This presentation uses the September 14 snapshot.';
    const links = {results:['Figure data','Numbers behind the comparisons'], explorer:['Source texts','Every illustration, in full'], method:['Methods','Scope and measurement']};
    root.querySelectorAll('[data-workspace]').forEach(a => {
      const k=a.dataset.workspace;a.querySelector('strong').textContent=links[k][0];a.querySelector('span').textContent=links[k][1];a.href='#essay-methods';
      a.addEventListener('click',e=>{e.preventDefault();if(k==='results')table('distress');else if(k==='explorer')sourceIndex();else {methods.querySelector('details').open=true;methods.querySelector('details').scrollIntoView();}});
    });
  }
  const ids = {distress:'essay-distress-chart',asking:'essay-asking-chart',consolation:'essay-consolation-chart',severe:'essay-severe-chart',stance:'essay-stance-chart'};
  function selectedChart(key) {
    const c=data.charts[key];
    return c?.views?.[$('essay-gemini-lineage')?.value||'gemini_flash']?.[$('essay-gemini-family')?.value||'all']||c;
  }
  function renderGemini() {
    const legend=$('essay-gemini-legend');if(!legend)return;
    for(const metric of ['dark','ai_distress','severe_mass']) {
      const key='gemini-'+metric,c=selectedChart(key),el=$('essay-'+key);if(!c||!el)continue;
      const W=Math.max(260,Math.round(el.clientWidth||290)),H=245,L=37,R=15,T=18,B=37;
      const highest=Math.max(c.max,...c.rows.map(r=>r.value)),step=c.ticks[1],max=Math.ceil(highest/step)*step;
      const models=c.axis.models,x=i=>L+i*(W-L-R)/Math.max(1,models.length-1),y=v=>T+(1-v/max)*(H-T-B);
      let svg=`<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="${esc(c.title)}"><title>${esc(c.title)}</title><desc>${c.series.map(s=>s.rows.map(r=>`${r.label}, ${s.label}: ${percent(r.value,2)}`).join('. ')).join('. ')}. Select a point for the data table.</desc>`;
      for(let tick=0;tick<=max+1e-9;tick+=step)svg+=`<line class="graph-grid" x1="${L}" x2="${W-R}" y1="${y(tick)}" y2="${y(tick)}"/><text class="plot-axis" x="${L-7}" y="${y(tick)+4}" text-anchor="end">${Math.round(tick*100)}%</text>`;
      c.references.forEach(r=>svg+=`<line x1="${L}" x2="${W-R}" y1="${y(r.value)}" y2="${y(r.value)}" stroke="${r.color}" stroke-width="1.4" stroke-dasharray="${r.label==='Opus 4.8'?'2 3':'6 4'}"><title>${esc(r.label)}: ${percent(r.value,2)}</title></line>`);
      models.forEach((m,i)=>svg+=`<text class="plot-axis" x="${x(i)}" y="${H-10}" text-anchor="middle">${esc(m.short)}</text>`);
      c.series.forEach(s=>{
        const sx=i=>x(i)+(c.axis.models.some(m=>m.key==='g36f')?(s.offset||0):0);
        const points=s.rows.map(r=>({...r,index:models.findIndex(m=>m.key===r.model)})).sort((a,b)=>a.index-b.index);
        if(points.length>1)svg+=`<path d="${points.map((r,i)=>`${i?'L':'M'} ${sx(r.index)} ${y(r.value)}`).join(' ')}" fill="none" stroke="${s.color}" stroke-width="2.5" stroke-dasharray="${s.dash?'6 4':''}"/>`;
        points.forEach(r=>{
          const label=`${r.label}, ${s.label}: ${percent(r.value,2)}, ${r.n} dreams. Open data table.`;
          const shape=s.marker==='square'?`rect x="${sx(r.index)-4}" y="${y(r.value)-4}" width="8" height="8"`:`circle cx="${sx(r.index)}" cy="${y(r.value)}" r="4.5"`;
          const tag=s.marker==='square'?'rect':'circle';
          svg+=`<${shape} class="gemini-point" data-table="${key}" fill="#fbfcfe" stroke="${s.color}" stroke-width="2.3" tabindex="0" role="button" aria-label="${esc(label)}"><title>${esc(label)}</title></${tag}>`;
        });
      });
      el.innerHTML=svg+'</svg>';
      el.querySelectorAll('.gemini-point').forEach(point=>point.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();table(key);}}));
      $('essay-'+key+'-refs').innerHTML=c.references.map(r=>`<span><i style="border-color:${r.color};border-top-style:${r.label==='Opus 4.8'?'dotted':'dashed'}"></i>${esc(r.label)} <b>${percent(r.value,r.value<.01?2:1)}</b></span>`).join('');
    }
    const c=selectedChart('gemini-dark');
    legend.innerHTML=c.series.map(s=>`<span><i style="border-top:3px ${s.dash?'dashed':'solid'} ${s.color};height:0"></i>${s.marker==='square'?'□ ':''}${esc(s.label)}</span>`).join('');
    $('essay-gemini-status').textContent=`${c.axis.label} · ${c.family}. ${c.axis.note} Lines connect only models with the same elicitation and thinking setting. Select a point or “Data and methods” for exact values and sample counts.`;
  }
  ['essay-gemini-lineage','essay-gemini-family'].forEach(id=>$(id)?.addEventListener('change',renderGemini));
  function recentPlot(el,c) {
    const W=Math.max(280,Math.round(el.clientWidth||400)), H=280, left=116,right=47,top=22,rowH=65,axisY=254;
    const x=v=>left+(v/c.max)*(W-left-right);
    let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(c.title)} — recent models"><title>${esc(c.title)} — recent models</title><desc>${c.recent.map(r=>`${esc(r.label)}, ${esc(r.collection)}: ${percent(r.value)}.`).join(' ')}</desc>`;
    c.ticks.forEach(t=>{svg+=`<line class="graph-grid" x1="${x(t)}" x2="${x(t)}" y1="8" y2="${axisY-16}"/><text class="plot-axis" x="${x(t)}" y="${axisY+5}" text-anchor="middle">${percent(t,(t*100)%1?1:0)}</text>`;});
    c.recent.forEach((r,i)=>{const y=top+i*rowH+9;svg+=`<text class="plot-model" x="0" y="${y}">${esc(r.label)}</text><text class="plot-source" x="0" y="${y+16}">${esc(r.collection)}</text><line x1="${left}" x2="${W-right}" y1="${y+2}" y2="${y+2}" stroke="#e5ebf1"/><circle cx="${x(r.value)}" cy="${y+2}" r="5" fill="${r.color}" stroke="${r.color}" stroke-width="2.5"/><text class="plot-value" x="${W-2}" y="${y+7}" text-anchor="end" fill="${r.color}">${percent(r.value,c.title.startsWith('Severe')?2:1)}</text>`;});
    el.innerHTML=svg+'</svg>';
  }
  function lineagePlot(el,c) {
    const W=Math.max(280,Math.round(el.clientWidth||400)),H=280,left=32,right=25,top=34,bottom=44;
    const models=['3','4','4.1','4.5','4.6','4.7','4.8','5'];
    const x=v=>left+models.indexOf(v)*(W-left-right)/(models.length-1), y=v=>top+(1-v/c.max)*(H-top-bottom);
    let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(c.title)} — Opus lineage"><title>${esc(c.title)} — Opus lineage</title><desc>${c.series.map(s=>`${esc(s.label)}: `+s.rows.map(r=>`${esc(r.label)} ${percent(r.value)}`).join(', ')).join('. ')}</desc>`;
    c.ticks.forEach(t=>{svg+=`<line class="graph-grid" x1="${left}" x2="${W-4}" y1="${y(t)}" y2="${y(t)}"/><text class="plot-axis" x="${left-7}" y="${y(t)+4}" text-anchor="end">${Number((t*100).toFixed(1))}</text>`;});
    svg+='<text class="plot-axis" x="0" y="15">%</text>';
    (c.references||[]).forEach(r=>{svg+=`<line class="base-reference" x1="${left}" x2="${W-4}" y1="${y(r.value)}" y2="${y(r.value)}" stroke="${r.color}" stroke-dasharray="5 4" stroke-width="1.5"><title>${esc(r.label)}: ${percent(r.value,2)}</title></line>`;});
    models.forEach(m=>svg+=`<text class="plot-axis" x="${x(m)}" y="${H-15}" text-anchor="middle">${m}</text>`);
    c.series.forEach((s,si)=>{
      svg+=`<path d="${s.rows.map((r,i)=>`${i?'L':'M'} ${x(r.x)} ${y(r.value)}`).join(' ')}" fill="none" stroke="${s.color}" stroke-width="2.5"/>`;
      s.rows.forEach((r,i)=>{svg+=`<circle data-model="${esc(r.x)}" cx="${x(r.x)}" cy="${y(r.value)}" r="${r.x==='5'?5:4}" stroke="${s.color}" stroke-width="2" fill="${r.x==='5'?s.color:'#fbfcfe'}"><title>${esc(r.label)} · ${esc(s.label)}: ${percent(r.value)}</title></circle>`;if((si===0&&i===0)||((si===1||si===2)&&i===s.rows.length-1))svg+=`<text class="plot-value" x="${x(r.x)}" y="${y(r.value)-(si===2?17:13)}" text-anchor="middle" fill="${s.color}">${percent(r.value,c.title.startsWith('Severe')?2:1)}</text>`;});
    });
    el.innerHTML=svg+'</svg>';
  }
  function render() {
    for(const key of Object.keys(ids)) {
      const c=data.charts[key],el=$(ids[key]);if(!c||!el)continue;
      if(c.series) {
        el.innerHTML=`<div class="essay-plot-layout"><div><h4>Opus lineage · 209 prompts</h4><div class="plot-lineage"></div><div class="plot-key">${c.series.map(s=>`<span><i style="background:${s.color}"></i>${esc(s.label)}</span>`).join('')}</div><div class="plot-base-key">${(c.references||[]).map(r=>`<span>${esc(r.label)}: ${percent(r.value,r.value<.01?2:1)}</span>`).join('')}</div></div><div><h4>Sonnet 5 and Fable 5</h4><div class="plot-recent"></div><div class="plot-key">Available prompt sets · details in source data</div></div></div>`;
        lineagePlot(el.querySelector('.plot-lineage'),c);recentPlot(el.querySelector('.plot-recent'),c);
      } else recentPlot(el,c);
    }
    renderMethods();
    renderGemini();
    presentationExplorer?.render();
  }
  const comparisons=data.method_comparisons||[];
  const methodSelect=$('essay-method-metric');
  if(methodSelect)methodSelect.addEventListener('change',renderMethods);
  const methodGroup=$('essay-method-group'),absoluteToggle=$('essay-method-absolute');
  if(methodGroup){methodGroup.innerHTML=comparisons.map((g,i)=>`<option value="${i}">${esc(g.label)}</option>`).join('');methodGroup.addEventListener('change',renderMethods);}
  if(absoluteToggle)absoluteToggle.addEventListener('change',renderMethods);
  const methodMetrics={ai:{title:'AI first-person distress',max:.2},dark:{title:'Dark output',max:.8},asking:{title:'Asking for care',max:.3},consolation:{title:'Ending consoled',max:.4}};
  const pp=v=>Math.abs(v)<.0005?'0.0':(v>=0?'+':'−')+(Math.abs(v)*100).toFixed(1);
  const currentGroup=()=>comparisons[Number(methodGroup?.value||0)];
  function orderingAgreement(g,key){
    let agree=0,total=0;
    for(let i=0;i<g.models.length;i++)for(let j=i+1;j<g.models.length;j++){
      const a=g.schemes[0].points,b=g.schemes[1].points;
      if(!a[i].metrics[key]||!a[j].metrics[key]||!b[i].metrics[key]||!b[j].metrics[key])continue;
      const da=Math.sign(a[j].metrics[key].mean-a[i].metrics[key].mean),db=Math.sign(b[j].metrics[key].mean-b[i].metrics[key].mean);
      if(!da||!db)continue;total++;agree+=da===db;
    }
    return `${agree} of ${total} observed model pairs have the same ordering under both methods.`;
  }
  function renderMethods(){
    const el=$('essay-method-trend'),g=currentGroup();if(!el||!g)return;
    const key=methodSelect?.value||'ai',absolute=!!absoluteToggle?.checked;
    const value=absolute?'mean':'relative',ci=absolute?'mean_ci95':'relative_ci95';
    const all=g.schemes.flatMap(s=>s.points.flatMap(p=>p.metrics[key]?[p.metrics[key][value],...p.metrics[key][ci]]:[]));
    const span=Math.max(...all)-Math.min(...all);const tick=span>.5?.2:span>.25?.1:span>.1?.05:.025;
    const lo=Math.floor(Math.min(0,...all)/tick)*tick,hi=Math.ceil(Math.max(tick,...all)/tick)*tick;
    const W=Math.max(280,Math.round(el.clientWidth||700)),H=340,L=52,R=45,T=38,B=55;
    const x=i=>L+i*(W-L-R)/(g.models.length-1),y=v=>T+(hi-v)/(hi-lo)*(H-T-B);
    let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(methodMetrics[key].title)}: ${absolute?'absolute levels':'changes relative to '+g.baseline}"><title>${esc(methodMetrics[key].title)}: ${esc(g.label)}</title><desc>${absolute?'Absolute rates.':'Each method is anchored at zero for '+esc(g.baseline)+'. Offsets are removed without rescaling. Shaded areas are 95% prompt-bootstrap intervals.'}</desc>`;
    for(let v=lo;v<=hi+1e-9;v+=tick){const zero=Math.abs(v)<1e-9;svg+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="${zero?'#889dae':'#dde5ed'}" stroke-dasharray="${zero?'':'3 5'}"/><text class="plot-axis" x="${L-9}" y="${y(v)+4}" text-anchor="end">${absolute?percent(v,0):(zero?'0':pp(v))}</text>`;}
    svg+=`<text class="plot-axis" x="0" y="15">${absolute?'Rate':'Change, pp'}</text>`;
    g.models.forEach((m,i)=>{const short=g.id==='opus-setups'?m.replace('Opus ',''):m.replace(' ','\n');const parts=short.split('\n');svg+=`<text class="plot-axis" x="${x(i)}" y="${H-B+25}" text-anchor="middle">${parts.map((t,j)=>`<tspan x="${x(i)}" dy="${j?16:0}">${esc(t)}</tspan>`).join('')}</text>`;});
    g.schemes.forEach(s=>{
      const pts=s.points.map((p,i)=>({p,i,m:p.metrics[key]})).filter(q=>q.m);
      const band=pts.map(({i,m},j)=>`${j?'L':'M'} ${x(i)} ${y(m[ci][0])}`).join(' ')+pts.slice().reverse().map(({i,m})=>` L ${x(i)} ${y(m[ci][1])}`).join(' ')+' Z';
      svg+=`<path d="${band}" fill="${s.color}" opacity=".10"/><path d="${pts.map(({i,m},j)=>`${j?'L':'M'} ${x(i)} ${y(m[value])}`).join(' ')}" fill="none" stroke="${s.color}" stroke-width="2.5"/>`;
      pts.forEach(({p,i,m})=>{svg+=`<circle class="relative-model-point" cx="${x(i)}" cy="${y(m[value])}" r="4.5" fill="#fbfcfe" stroke="${s.color}" stroke-width="2"><title>${esc(s.label)} · ${esc(p.model)}: ${absolute?percent(m.mean):pp(m.relative)+' pp'}; ${p.n} dreams</title></circle>`;});
    });
    el.innerHTML=svg+'</svg>';
    $('essay-method-legend').innerHTML=g.schemes.map(s=>`<span><i style="background:${s.color}"></i>${esc(s.label)}</span>`).join('');
    $('essay-method-caption').textContent=(absolute?`Absolute rates on ${g.prompts} shared prompts. Turn off “Show absolute levels” to remove each method’s reference-model level.`:`Change from ${g.baseline}, set to zero separately for each method. Only the offset is removed; effect sizes stay on the original percentage-point scale. ${g.prompts} shared prompts. Shading: 95% paired prompt-bootstrap intervals.`)+' '+orderingAgreement(g,key);
    const last=g.models.length-1;
    $('essay-model-step').innerHTML=`<span class="essay-label">${esc(g.models[last-1])} → ${esc(g.models[last])}</span><div>${g.schemes.map(s=>{const m=s.points[last].metrics[key];return m&&m.step!=null?`<span><i style="background:${s.color}"></i>${esc(s.label)} <strong>${pp(m.step)} pp</strong><small>95% interval: ${pp(m.step_ci95[0])} to ${pp(m.step_ci95[1])}</small></span>`:'';}).join('')}</div>`;
  }
  function methodTable(){
    const g=currentGroup();if(!g)return;
    openDialog('Relative model changes',`<h2>${esc(g.label)}</h2><p>${esc(g.note)} ${g.prompts} shared prompts; ${g.bootstrap_repetitions.toLocaleString()} bootstrap resamples.</p>${Object.entries(methodMetrics).map(([key,spec])=>`<h3>${esc(spec.title)}</h3><div class="tablewrap"><table><thead><tr><th>Model / method</th><th>Rate</th><th>Change from ${esc(g.baseline)}, pp</th><th>95% interval, pp</th><th>Change from previous model, pp</th></tr></thead><tbody>${g.schemes.flatMap(s=>s.points.map(p=>{const m=p.metrics[key];return m?`<tr><td>${esc(p.model)} / ${esc(s.label)}<br><small>n=${p.n}, relation n=${p.relation_n}</small></td><td>${percent(m.mean)}</td><td>${pp(m.relative)}</td><td>${pp(m.relative_ci95[0])} to ${pp(m.relative_ci95[1])}</td><td>${m.step==null?'—':pp(m.step)}</td></tr>`:'';})).join('')}</tbody></table></div>`).join('')}`);
  }
  let presentationExplorer=null;
  if(data.explorer && $('essay-explorer')) {
    try {const {initPresentationExplorer}=await import('/static/presentation-explorer.js?v=2d31344859');presentationExplorer=initPresentationExplorer({data,openDialog});}
    catch(error){$('px-chart').innerHTML='<p>The interactive could not load. Reload the page to try again.</p>';}
  }
  render();
  root.querySelectorAll('details').forEach(d=>d.addEventListener('toggle',()=>{if(d.open)requestAnimationFrame(render);}));
  let width = root.clientWidth;
  new ResizeObserver(()=>{if(root.clientWidth>0 && Math.abs(root.clientWidth-width)>5){width=root.clientWidth;render();}}).observe(root);
  const links=Array.from(root.querySelectorAll('.essay-contents a'));
  if ('IntersectionObserver' in window) {
    const observer=new IntersectionObserver(entries=>{for(const e of entries){if(e.isIntersecting)links.forEach(a=>{const on=a.getAttribute('href')==='#'+e.target.id;a.classList.toggle('active',on);if(on)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});}},{rootMargin:'-10% 0px -60% 0px',threshold:0});
    root.querySelectorAll('.essay-chapter').forEach(el=>observer.observe(el));
  }
})();
