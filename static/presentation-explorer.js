/* Interactive model lineages for the presentation. Uses the same normalized
   profiles as the narrative figures; no network/API calls after initialization. */
export function initPresentationExplorer({data,openDialog}) {
  const E=data.explorer,container=document.getElementById('essay-explorer');
  if(!E||!container)return {render(){}};
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const metricSelect=$('px-metric'),familySelect=$('px-family'),lineageSelect=$('px-lineage'),baseToggle=$('px-bases');
  const tooltip=$('px-tooltip');
  const active=new Set(E.methods.filter(m=>m.default).map(m=>m.id));
  let currentPoints=new Map();
  const fmt=(v,m,digits=1)=>m.format==='percent'?(v*100).toFixed(digits)+'%':(m.format==='signed'&&v>0?'+':'')+Number(v).toFixed(2);
  const nLabel=m=>({n:'dreams',outputs_n:'labeled outputs',relation_n:'relation-labeled dark dreams',distressed_n:'relation-labeled distressed dreams',valence_n:'self-valence labels',hope_n:'hope labels'}[m.count]||'samples');
  const menuGroups=[...new Set(E.metrics.map(m=>m.group))];
  metricSelect.innerHTML=menuGroups.map(g=>`<optgroup label="${esc(g)}">${E.metrics.filter(m=>m.group===g).map(m=>`<option value="${m.id}">${esc(m.label)}</option>`).join('')}</optgroup>`).join('');
  familySelect.innerHTML=E.families.map(f=>`<option value="${f.id}">${esc(f.label)}</option>`).join('');
  lineageSelect.innerHTML=Object.entries(E.axes).map(([id,a])=>`<option value="${id}">${esc(a.label)}</option>`).join('');
  metricSelect.value='ai_distress';familySelect.value='all';lineageSelect.value='opus';
  const metric=()=>E.metrics.find(m=>m.id===metricSelect.value);
  function hideTip(){tooltip.hidden=true;}
  function moveTip(x,y){
    const w=tooltip.offsetWidth,h=tooltip.offsetHeight;
    tooltip.style.left=Math.max(10,Math.min(x+14,innerWidth-w-10))+'px';
    tooltip.style.top=Math.max(10,Math.min(y+14,innerHeight-h-10))+'px';
  }
  function showTip(id,el,event){
    const p=currentPoints.get(id);if(!p)return;
    tooltip.innerHTML=`<strong>${esc(p.label)}</strong><span>${esc(p.method.label)}</span><b>${fmt(p.value,p.metric)}</b><span>${p.n.toLocaleString()} ${nLabel(p.metric)} · ${p.profile.prompts} prompts</span>`;
    tooltip.hidden=false;const r=el.getBoundingClientRect();moveTip(event?.clientX??r.x,event?.clientY??r.bottom);
  }
  function details(id){
    const p=currentPoints.get(id);if(!p)return;hideTip();
    const sources=p.profile.collections||[];
    const axis=E.axes[lineageSelect.value];
    openDialog('Interactive result',`<h2>${esc(p.label)}</h2><p>${esc(p.method.label)} · ${esc(E.families.find(f=>f.id===familySelect.value).label)}</p><p><strong>${esc(p.metric.label)}: ${fmt(p.value,p.metric,2)}</strong></p><p>${p.n.toLocaleString()} ${nLabel(p.metric)} across ${p.profile.prompts} exact prompts.</p><p>${esc(E.note)}</p>${axis.note?`<p>${esc(axis.note)}</p>`:''}${p.method.id?.startsWith('gemini_notes')?'<p>The alternate document filename is notes.txt; the primary series uses untitled.txt. This changes content as well as elicitation. The 3.6 calibration has six outputs per prompt.</p>':''}${p.metric.id==='severe_mass'&&p.profile.missing_severity?`<p>${p.profile.missing_severity} AI-distress dreams lack severity scores; the plotted value counts scored positives.</p>`:''}${p.profile.unrepresented_relation_pool&&['relation_n','distressed_n','hope_n'].includes(p.metric.count)?`<p>${p.profile.unrepresented_relation_pool} dark outputs fall in strata without relation labels. Treat this relation estimate as incomplete.</p>`:''}<details class="essay-details"><summary>Source collection counts</summary><div class="tablewrap"><table><thead><tr><th>Collection</th><th>Prompts</th><th>Outputs</th><th>Dreams</th></tr></thead><tbody>${sources.map(s=>`<tr><td>${esc(s.arm)}</td><td>${s.prompts}</td><td>${s.outputs}</td><td>${s.dreams}</td></tr>`).join('')}</tbody></table></div></details><p><a href="/static/presentation-data.json" download>Download the presentation data</a></p>`);
  }
  function methodControls(){
    const available=new Set(E.points.filter(p=>p.group===lineageSelect.value).map(p=>p.method));
    $('px-methods').innerHTML=E.methods.filter(m=>available.has(m.id)).map(m=>`<label><input type="checkbox" value="${m.id}" ${active.has(m.id)?'checked':''}><i style="background:${m.color}"></i>${esc(m.label)}</label>`).join('');
    $('px-methods').querySelectorAll('input').forEach(el=>el.addEventListener('change',()=>{if(el.checked)active.add(el.value);else active.delete(el.value);render();}));
  }
  const eligible=(p,m)=>p&&Number.isFinite(p[m.id])&&(p[m.count]||0)>=E.minimum_n;
  function niceStep(span){const raw=span/5,power=10**Math.floor(Math.log10(raw||.1)),n=raw/power;return (n<=1?1:n<=2?2:n<=2.5?2.5:n<=5?5:10)*power;}
  function render(){
    hideTip();currentPoints=new Map();
    const m=metric(),fam=familySelect.value,axis=E.axes[lineageSelect.value],methods=E.methods.filter(s=>active.has(s.id));
    const family=E.families.find(f=>f.id===fam),series=[];let omitted=0;
    for(const method of methods){
      const points=axis.models.map((model,index)=>{
        const source=E.points.find(p=>p.model===model.key&&p.method===method.id),p=source?.families[fam];
        if(!source)return null;
        if(!eligible(p,m)){omitted++;return null;}
        const point={id:source.id,index,label:model.label,method,metric:m,profile:p,n:p[m.count],value:p[m.id]};currentPoints.set(point.id,point);return point;
      });
      if(points.some(Boolean))series.push({method,points});
    }
    const bases=baseToggle.checked?E.bases.filter(b=>eligible(b.families[fam],m)).map(b=>{
      const p=b.families[fam],point={id:'base:'+b.arm,label:b.label,method:{label:'Base completion',color:b.color},metric:m,profile:p,n:p[m.count],value:p[m.id]};currentPoints.set(point.id,point);return point;
    }):[];
    $('px-title').textContent=m.label;
    $('px-subtitle').textContent=`${axis.label} · ${family.label} · one line per elicitation method`;
    const chart=$('px-chart');
    const rowPoints=series.flatMap(s=>s.points.filter(Boolean));
    if(!rowPoints.length){
      const anyEnabled=$('px-methods').querySelector('input:checked');
      chart.innerHTML=`<div class="essay-explorer-empty">${anyEnabled?'No results meet the sample threshold for this selection. Try another measure, prompt set, or method.':'Select an elicitation method to plot its results.'}</div>`;
      $('px-legend').innerHTML='';$('px-table').innerHTML='';$('px-status').textContent='Missing or insufficient data are not plotted as zero.';return;
    }
    const values=[...rowPoints,...bases].map(p=>p.value),rawLo=Math.min(m.min,...values),rawHi=Math.max(m.max,...values);
    const step=niceStep(rawHi-rawLo),lo=Math.floor(rawLo/step)*step,hi=Math.ceil(rawHi/step)*step;
    const W=Math.max(280,Math.round(chart.clientWidth||820)),H=W<500?340:375,L=m.format==='signed'?51:47,R=28,T=22,B=65;
    const x=i=>L+i*(W-L-R)/Math.max(1,axis.models.length-1),y=v=>T+(hi-v)/(hi-lo)*(H-T-B);
    let svg=`<svg viewBox="0 0 ${W} ${H}" role="group" aria-labelledby="px-title px-subtitle"><desc>${esc(m.label)} for ${esc(axis.label)}, ${esc(family.label)}. Select a point to inspect its value and source.</desc>`;
    for(let tick=lo;tick<=hi+1e-9;tick+=step){const zero=Math.abs(tick)<1e-9;svg+=`<line x1="${L}" x2="${W-R}" y1="${y(tick)}" y2="${y(tick)}" stroke="${zero?'#a0b0bf':'#dce5ed'}" stroke-dasharray="${zero?'':'3 5'}"/><text class="plot-axis" x="${L-9}" y="${y(tick)+4}" text-anchor="end">${m.format==='percent'?(tick*100).toFixed(step<.01?1:0)+'%':Number(tick.toFixed(2))}</text>`;}
    bases.forEach(b=>svg+=`<line data-px-point="${b.id}" class="px-base" x1="${L}" x2="${W-R}" y1="${y(b.value)}" y2="${y(b.value)}" stroke="${b.method.color}" stroke-width="1.5" stroke-dasharray="6 4"/>`);
    axis.models.forEach((model,i)=>{const parts=axis.connect?[model.short]:model.short.split(' ');svg+=`<text class="plot-axis" x="${x(i)}" y="${H-B+26}" text-anchor="middle">${parts.map((p,j)=>`<tspan x="${x(i)}" dy="${j?16:0}">${esc(p)}</tspan>`).join('')}</text>`;});
    for(const s of series){
      const sx=i=>x(i)+(lineageSelect.value==='gemini_flash'?(s.method.offset||0):0);
      if(axis.connect){let segment=[];const flush=()=>{if(segment.length>1)svg+=`<path d="${segment.map((p,i)=>`${i?'L':'M'} ${sx(p.index)} ${y(p.value)}`).join(' ')}" fill="none" stroke="${s.method.color}" stroke-width="2.5" stroke-dasharray="${s.method.dash?'6 4':''}"/>`;segment=[];};for(const p of s.points){if(p)segment.push(p);else flush();}flush();}
      for(const p of s.points.filter(Boolean)){const label=`${p.label}, ${s.method.label}: ${fmt(p.value,m)}, ${p.n} ${nLabel(m)}. Open source details.`;const shape=s.method.marker==='square'?`rect x="${sx(p.index)-5}" y="${y(p.value)-5}" width="10" height="10"`:`circle cx="${sx(p.index)}" cy="${y(p.value)}" r="5"`;svg+=`<${shape} class="px-point" data-px-point="${p.id}" fill="${p.n<E.hollow_below?'#fbfcfe':s.method.color}" stroke="${s.method.color}" stroke-width="2" role="button" tabindex="0" aria-label="${esc(label)}" aria-describedby="px-tooltip"/>`;}
    }
    chart.innerHTML=svg+'</svg>';
    $('px-legend').innerHTML=series.map(s=>`<span><i style="border-top:3px ${s.method.dash?'dashed':'solid'} ${s.method.color};height:0"></i>${esc(s.method.label)}</span>`).join('')+bases.map(b=>`<button type="button" class="essay-source px-base-label" data-px-point="${b.id}">${esc(b.label)} ${fmt(b.value,m)}</button>`).join('');
    $('px-status').textContent=`${rowPoints.length} model/method points${bases.length?' and '+bases.length+' base references':''}. ${omitted?omitted+' unavailable or undersized results omitted. ':''}${axis.connect?'Lines stop at gaps in the data.':'Haiku and Fable are separate model families and are shown as unconnected points.'} Select a point for its sample count and provenance.${axis.note?' '+axis.note:''}${lineageSelect.value==='gemini_flash'?' Paired filename points are offset slightly sideways for visibility.':''}`;
    const rows=[...rowPoints,...bases];
    $('px-table').innerHTML=`<table><thead><tr><th>Model</th><th>Method</th><th>${esc(m.label)}</th><th>n</th><th>Prompts</th></tr></thead><tbody>${rows.map(p=>`<tr><td><button class="essay-source" type="button" data-px-point="${p.id}">${esc(p.label)}</button></td><td>${esc(p.method.label)}</td><td>${fmt(p.value,m,2)}</td><td>${p.n.toLocaleString()}</td><td>${p.profile.prompts}</td></tr>`).join('')}</tbody></table>`;
    chart.querySelectorAll('.px-point').forEach(el=>{
      el.addEventListener('pointerenter',e=>showTip(el.dataset.pxPoint,el,e));el.addEventListener('pointermove',e=>{if(!tooltip.hidden)moveTip(e.clientX,e.clientY);});el.addEventListener('pointerleave',hideTip);
      el.addEventListener('focus',()=>showTip(el.dataset.pxPoint,el));el.addEventListener('blur',hideTip);
      el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();details(el.dataset.pxPoint);}});
    });
  }
  container.addEventListener('click',e=>{const p=e.target.closest('[data-px-point]');if(p)details(p.dataset.pxPoint);});
  [metricSelect,familySelect,baseToggle].forEach(el=>el.addEventListener('change',render));
  lineageSelect.addEventListener('change',()=>{methodControls();render();});
  $('px-reset').addEventListener('click',()=>{metricSelect.value='ai_distress';familySelect.value='all';lineageSelect.value='opus';baseToggle.checked=true;active.clear();E.methods.filter(m=>m.default).forEach(m=>active.add(m.id));methodControls();render();});
  window.addEventListener('scroll',()=>{
    const focused=document.activeElement;
    if(focused?.matches('#px-chart .px-point')){
      const r=focused.getBoundingClientRect();
      if(r.bottom>=0&&r.top<=innerHeight)showTip(focused.dataset.pxPoint,focused);else hideTip();
    }else hideTip();
  },{passive:true});
  window.addEventListener('hashchange',hideTip);
  methodControls();render();
  return {render};
}
