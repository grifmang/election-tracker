const $ = s => document.querySelector(s);
const fmt = v => (v === null || v === undefined) ? '<span class="na">n/a</span>' : Number(v).toLocaleString();
const pcls = p => /^Democ|^D$/.test(p||'') ? 'D' : /^Repub|^R$/.test(p||'') ? 'R' : 'O';
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ELECTION = new Date('2026-11-03T00:00:00-05:00');
const D = {};
const isUrl = u => typeof u === 'string' && /^https?:\/\//i.test(u);
const ext = (u, t, title) => isUrl(u) ? `<a href="${esc(u)}" target="_blank" rel="noopener"${title?` title="${esc(title)}"`:''}>${t}</a>` : '';
// Source cell: state's official source (link only when it's a real absolute URL, else plain-text agency name) + UF state page
function srcCell(s){
  const parts = [];
  if (isUrl(s.source_link)) parts.push(ext(s.source_link, 'state source', s.source_link));
  else if (s.source_label) parts.push(`<span class="muted agency" title="${esc(s.source_label)}">${esc(s.source_label.replace(/^Data (file )?provided (by )?/i,'').replace(/Secretary of (the )?State/,'SOS'))}</span>`);
  if (isUrl(s.uf_state_url)) parts.push(ext(s.uf_state_url, 'UF page', 'UF Election Lab ' + s.name + ' page'));
  return parts.join(' · ');
}

async function load(n){ try { const r = await fetch('data/'+n+'.json',{cache:'no-store'}); return r.ok ? r.json() : null; } catch(e){ return null; } }

document.querySelectorAll('nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('nav button,.tab').forEach(x => x.classList.remove('active'));
  b.classList.add('active'); $('#'+b.dataset.tab).classList.add('active'); location.hash = b.dataset.tab; });
if (location.hash) { const b = document.querySelector(`nav button[data-tab="${location.hash.slice(1)}"]`); b && b.click(); }

function sortable(tbl){ tbl.querySelectorAll('th').forEach((th,i) => th.onclick = () => {
  const rows=[...tbl.querySelectorAll('tbody tr')], asc = th.dataset.asc !== '1'; th.dataset.asc = asc?'1':'0';
  const val = r => { const t=r.children[i]?.dataset.v ?? r.children[i]?.textContent ?? ''; const n=parseFloat(t); return isNaN(n)?t:n; };
  rows.sort((a,b)=>{const x=val(a),y=val(b);return (x>y?1:x<y?-1:0)*(asc?1:-1)}); const tb=tbl.querySelector('tbody'); rows.forEach(r=>tb.appendChild(r)); }); }
function table(el, heads, rows){ el.innerHTML = '<thead><tr>'+heads.map(h=>`<th class="${h.n?'n':''}">${h.t}</th>`).join('')+'</tr></thead><tbody>'+rows.join('')+'</tbody>'; sortable(el); }
const cands = cs => (cs||[]).map(c=>`<span class="${pcls(c.party)}">${esc(c.name)}</span> <span class="muted">(${esc(c.party||'?')})</span>`).join('<br>');

function overview(){
  const ev = D.ev, t = ev?.national_totals || {};
  const rep = ev ? ev.states.filter(s=>s.reporting).length : 0;
  $('#natcards').innerHTML = [
    ['Ballots cast so far', fmt(t.voted_all), `UF Election Lab · ${rep} states reporting`],
    ['Mail ballots returned', fmt(t.accept_all), ''],['In-person early votes', fmt(t.inperson_all), ''],
    ['Mail ballots requested/sent', fmt(t.request_all), ''],
    ['Senate races', D.sen?.count ?? 'n/a', '33 regular + 2 special'],['House races', D.house?.count ?? 'n/a', 'all 435 seats'],
    ['Live results', D.resH?.live ? 'LIVE' : 'Not yet', 'Feed goes live Nov 3 after polls close']
  ].map(([l,v,s])=>`<div class="card"><div class="l">${l}</div><div class="v">${v}</div><div class="muted">${s}</div></div>`).join('');
  const days = Math.ceil((ELECTION - new Date())/864e5);
  $('#countdown').textContent = (days>0?`${days} days until Election Day. `:'')+`Early-vote data generated ${ev?.generated ?? 'n/a'} (UTC). Totals only include states the UF tracker covers; ${ev?.states_not_in_tracker?.join(', ') || 'none'} not in tracker.`;
  const top = (ev?.states||[]).filter(s=>s.voted_all).sort((a,b)=>b.voted_all-a.voted_all).slice(0,12);
  table($('#topstates'), [{t:'State'},{t:'Ballots cast',n:1},{t:'% of 2022 turnout',n:1},{t:'Updated'}],
    top.map(s=>`<tr><td>${s.name}</td><td class="n" data-v="${s.voted_all}">${fmt(s.voted_all)}</td><td class="n">${s.turnout_2022?(100*s.voted_all/s.turnout_2022).toFixed(1)+'%':'n/a'}</td><td>${s.last_update}</td></tr>`));
  const dset = new Set(D.evd?.states_with_district_data||[]);
  table($('#coverage'), [{t:'Item'},{t:'Status'}], [
    ['Senate race list + candidates', `${D.sen?.count} races (Wikipedia rev ${D.sen?.wikipedia_revid})`],
    ['House race list + candidates', `${D.house?.count} districts (Wikipedia rev ${D.house?.wikipedia_revid})`],
    ['Early vote, state level', `${rep} of 51 jurisdictions with data`],
    ['Early vote, district level', `${dset.size} states: ${[...dset].join(', ')}`],
    ['Live results feed', `Open America: ~22 states with readable official feeds; others need another source`]].map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`));
}

function senate(){
  const f = ($('#senfilter').value||'').toLowerCase();
  const rows = (D.sen?.races||[]).slice().sort((a,b)=>a.state_name.localeCompare(b.state_name)||a.special-b.special).filter(r => !f || JSON.stringify(r).toLowerCase().includes(f)).map(r=>{
    const rt = r.ratings||{}, pick = k => Object.entries(rt).find(([n])=>n.startsWith(k))?.[1] || '—';
    const ev = D.ev?.states.find(s=>s.state===r.state);
    return `<tr><td>${esc(r.state_name)}${r.special?'<span class="tag">special</span>':''}</td><td>${esc(r.pvi)}</td>
    <td class="${pcls(r.incumbent.party)}">${esc(r.incumbent.name)}</td><td>${esc(r.status)}</td><td>${cands(r.candidates)}</td>
    <td>${pick('Cook')} / ${pick('Sabato')} / ${pick('IE')}</td><td class="n" data-v="${ev?.voted_all||0}">${ev?.voted_all ? fmt(ev.voted_all) : '<span class="na">no data yet</span>'}</td><td>${esc(r.calendar?.poll_close_et||'')}</td></tr>`; });
  table($('#sentable'), [{t:'State'},{t:'PVI'},{t:'Incumbent'},{t:'Status'},{t:'Candidates'},{t:'Cook / Sabato / IE'},{t:'State early ballots',n:1},{t:'Polls close (ET)'}], rows);
}

function houseInit(){
  const sts = [...new Set((D.house?.races||[]).map(r=>r.state))];
  $('#housestate').innerHTML = '<option value="">All states</option>'+sts.map(s=>`<option>${s}</option>`).join('');
  $('#housestate').onchange = house; $('#compOnly').onchange = house;
}
function house(){
  const st = $('#housestate').value, comp = $('#compOnly').checked;
  const compset = new Set((D.comp?.districts||[]).map(d=>d.key));
  const evd = Object.fromEntries((D.evd?.districts||[]).map(d=>[d.key,d]));
  const rows = (D.house?.races||[]).filter(r=>(!st||r.state===st)&&(!comp||compset.has(r.key))).map(r=>{
    const e = evd[r.key];
    return `<tr><td data-v="${r.key}">${r.key}${compset.has(r.key)?'<span class="tag comp">competitive</span>':''}</td><td>${esc(r.pvi)}</td>
    <td>${r.incumbents.map(i=>`<span class="${pcls(i.party)}">${esc(i.name)}</span>`).join('<br>')}</td><td class="muted">${r.status.map(esc).join('<br>')}</td>
    <td>${cands(r.candidates)}</td><td class="n" data-v="${e?.voted_all ?? e?.accept_all ?? -1}">${e ? fmt(e.voted_all ?? e.accept_all) + (e.voted_all==null?' <span class="muted">(mail only)</span>':'') : '<span class="na">not published</span>'}</td>
    <td class="na" title="Wired on election night">awaiting results</td></tr>`; });
  table($('#housetable'), [{t:'District'},{t:'PVI'},{t:'Incumbent(s)'},{t:'Status'},{t:'Candidates'},{t:'Early ballots (district)',n:1},{t:'Result'}], rows);
}

function early(){
  const z = v => v ? fmt(v) : '<span class="na" title="0 or not reported by state">—</span>';
  const rows = (D.ev?.states||[]).slice().sort((a,b)=>a.name.localeCompare(b.name)).map(s=>{
    if (!s.not_in_tracker && !s.reporting) return `<tr><td>${s.name}</td><td colspan="6" class="na">No 2026 general-election data posted yet</td><td>${s.last_update||''}</td><td>${srcCell(s)}</td></tr>`;
    if (s.not_in_tracker) return `<tr><td>${s.name}</td><td colspan="6" class="na">Not listed in the UF Election Lab tracker</td><td></td><td>${srcCell(s)}</td></tr>`;
    const p = s.has_party_breakdown, tv = (s.voted_dem||0)+(s.voted_rep||0)+(s.voted_none||0);
    const bar = p&&tv ? `<span class="bar"><span style="width:${100*s.voted_dem/tv}%;background:var(--d)"></span><span style="width:${100*s.voted_none/tv}%;background:#b7bec8"></span><span style="width:${100*s.voted_rep/tv}%;background:var(--r)"></span></span>
      <span class="muted">D ${(100*s.voted_dem/tv).toFixed(1)}% · R ${(100*s.voted_rep/tv).toFixed(1)}% · Oth ${(100*s.voted_none/tv).toFixed(1)}%</span>` : '<span class="na">no party registration data</span>';
    return `<tr><td>${s.name}</td><td class="n" data-v="${s.voted_all}">${s.reporting?fmt(s.voted_all):'<span class="na">no data yet</span>'}</td><td class="n" data-v="${s.accept_all}">${z(s.accept_all)}</td>
      <td class="n" data-v="${s.inperson_all}">${z(s.inperson_all)}</td><td class="n" data-v="${s.request_all}">${z(s.request_all)}</td>
      <td class="n">${s.turnout_2022&&s.voted_all?(100*s.voted_all/s.turnout_2022).toFixed(1)+'%':'—'}</td><td>${bar}</td>
      <td>${s.last_update||''}${s.notes?` <span title="${esc(s.notes)}">ⓘ</span>`:''}</td><td>${srcCell(s)}</td></tr>`; });
  table($('#evtable'), [{t:'State'},{t:'Ballots cast',n:1},{t:'Mail returned',n:1},{t:'In-person early',n:1},{t:'Mail req./sent',n:1},{t:'% of 2022',n:1},{t:'Cast by party reg.'},{t:'Updated'},{t:'Source'}], rows);
  const sts = D.evd?.states_with_district_data||[];
  $('#evdhead').textContent = `By congressional district (${sts.length} states publish usable district data)`;
  $('#evdstate').innerHTML = sts.map(s=>`<option>${s}</option>`).join(''); $('#evdstate').onchange = earlyD; earlyD();
}
function earlyD(){
  const st = $('#evdstate').value, so = D.ev?.states.find(x=>x.state===st);
  $('#evdsrc').innerHTML = so ? 'Source: ' + (srcCell(so) || '<span class="muted">UF Election Lab district file</span>') : '';
  const rows = (D.evd?.districts||[]).filter(d=>d.state===st).map(d=>`<tr><td>${d.key}</td><td class="n" data-v="${d.voted_all??-1}">${fmt(d.voted_all)}</td><td class="n">${fmt(d.accept_all)}</td><td class="n">${fmt(d.inperson_all)}</td><td class="n">${fmt(d.request_all)}</td>
    <td class="n">${fmt(d.accept_dem)}</td><td class="n">${fmt(d.accept_rep)}</td><td class="n">${fmt(d.accept_none)}</td></tr>`);
  table($('#evdtable'), [{t:'District'},{t:'Ballots cast',n:1},{t:'Mail returned',n:1},{t:'In-person',n:1},{t:'Requested',n:1},{t:'Mail ret. Dem reg',n:1},{t:'Mail ret. Rep reg',n:1},{t:'Mail ret. other',n:1}], rows);
}

function resTable(el, data, kind){
  const races = data?.races || {};
  const keys = kind==='S' ? (D.sen?.races||[]).map(r=>r.state) : (D.house?.races||[]).map(r=>r.key);
  const seen = new Set(), rows = [];
  for (const k of keys){ if (seen.has(k)) continue; seen.add(k); const r = races[k];
    rows.push(`<tr><td>${k}</td>` + (r ? `<td class="n">${r.pct_in ?? '—'}%</td><td>${r.candidates.slice(0,3).map(c=>`<span class="${pcls(c.party)}">${esc(c.name)}</span> ${fmt(c.votes)} (${c.pct}%)`).join('<br>')}</td><td>${r.called?'Called: '+esc(r.winner):'Not called'}</td>`
      : `<td colspan="3" class="na">${data?.live?'No feed for this race in current source':'Awaiting results (polls close Nov 3)'}</td>`) + '</tr>'); }
  table(el, [{t:kind==='S'?'State':'District'},{t:'% in',n:1},{t:'Leading candidates (votes)'},{t:'Call'}], rows);
}
function results(){
  const demo = $('#demo2024').checked, S = demo ? D.resS24 : D.resS, H = demo ? D.resH24 : D.resH;
  $('#resnotice').innerHTML = demo ? '<b>TEST MODE — 2024 certified-results replay, not 2026.</b> Used only to verify the results wiring.' :
    `Source: ${esc(H?.source||'n/a')}. Status: <b>${H?.live?'LIVE':'not live yet'}</b>${H?.as_of?' · as of '+H.as_of:''}. 2026 races in feed: House ${Object.keys(H?.races||{}).length}, Senate ${Object.keys(S?.races||{}).length}. This feed passes through official state counts and makes no race calls; it covers about 22 states. Races outside it need AP/DDHQ or per-state feeds.`;
  resTable($('#ressen'), S, 'S'); resTable($('#reshouse'), H, 'H');
}
function sources(){
  $('#srclist').innerHTML = `<ul>
  <li>Race lists, candidates, Senate ratings & poll-closing times: ${ext(D.house?.source, esc(D.house?.source))}, ${ext(D.sen?.source, esc(D.sen?.source))} (CC BY-SA 4.0). Generated ${D.house?.generated}.</li>
  <li>Early vote: ${ext(D.ev?.source, "UF Election Lab 2026 Early Voting")} — ${esc(D.ev?.attribution)}. Data file: ${ext(D.ev?.data_url, esc(D.ev?.data_url))}. ${D.ev?.caveats?.map(esc).join(' ')}</li>
  <li>District early vote: ${esc(D.evd?.note)}</li>
  <li>Competitive-district flags: ${esc(D.comp?.note)} ${ext(D.comp?.source, "csv")}</li>
  <li>Results: <a href="https://openamerica.io/elections/api/">Open America results feed</a> — official state counts, no projections.</li></ul>`;
}

(async () => {
  [D.house, D.sen, D.ev, D.evd, D.comp, D.resH, D.resS, D.resH24, D.resS24] = await Promise.all(
    ['races_house','races_senate','early_vote_states','early_vote_districts','house_competitive','results_house','results_senate','results_test2024_house','results_test2024_senate'].map(load));
  overview(); senate(); $('#senfilter').oninput = senate; houseInit(); house(); early(); results(); $('#demo2024').onchange = results; sources();
  setInterval(async()=>{ const h=await load('results_house'); if(h?.live){ D.resH=h; D.resS=await load('results_senate'); results(); } }, 60000);
})();
