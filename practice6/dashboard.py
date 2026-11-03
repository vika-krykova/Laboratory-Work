import json
import os
from pathlib import Path

from audio import good_segments
from common import load_metas, read_json
from search import timestamp_url


def build_dashboard(cfg):
    out = Path(cfg.out_dir); out.mkdir(parents=True, exist_ok=True)
    topics = read_json(Path(cfg.data_dir) / "topics.json", {}) or {}
    assign = topics.get("assignment", {})
    videos = []
    for m in load_metas(cfg.data_dir):
        d = Path(cfg.data_dir) / m["id"]
        segs = good_segments(read_json(d / "transcript.json"), cfg.no_speech_max)
        ev = read_json(d / "events.json", [])
        videos.append({
            "id": m["id"], "title": m.get("title") or m["id"], "duration": m.get("duration") or 0,
            "src": os.path.relpath(Path(cfg.data_dir) / m["video_file"], out).replace("\\", "/"),
            "url": timestamp_url(m, 0) if m.get("webpage_url") else None,
            "cluster": assign.get(m["id"]),
            "segments": [{"s": s["start"], "e": s["end"], "t": s["text"]} for s in segs],
            "events": [{"k": e["kind"], "l": e["label"], "s": e["start"], "e": e["end"], "c": e["confidence"]} for e in ev]})
    data = {"videos": videos, "clusters": topics.get("clusters", [])}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (out / "dashboard.html").write_text(TEMPLATE.replace("__DATA__", payload), encoding="utf-8")
    return out / "dashboard.html"


TEMPLATE = r"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Анализ видео — поиск по событиям</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:system-ui,Arial,sans-serif;margin:0;background:#f6f7f9;color:#222}
header{background:#fff;padding:12px 20px;border-bottom:1px solid #ddd;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
header input{flex:1;min-width:220px;padding:8px 10px;font-size:15px}header button,header select{padding:8px 12px;font-size:14px}
main{display:grid;grid-template-columns:minmax(280px,360px) 1fr;gap:14px;padding:14px 20px}
@media(max-width:900px){main{grid-template-columns:1fr}}
.card{background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:12px;margin-bottom:14px}
h3{margin:0 0 8px;font-size:15px}.item{padding:6px 4px;border-bottom:1px solid #eee;cursor:pointer;font-size:13px}
.item:hover{background:#eef4ff}.pill{display:inline-block;background:#e8eefc;border-radius:10px;padding:0 7px;font-size:11px;margin-left:4px}
.meta{color:#777;font-size:12px}video{width:100%;max-height:420px;background:#000}
.ev{cursor:pointer}.ev:hover{stroke:#000;stroke-width:1}.bar{background:#54a24b;height:10px;border-radius:3px}
#timeline{overflow-x:auto}
</style></head><body>
<header><b>Поиск по видео</b>
<input id="q" placeholder="слово из речи или объект: ремонт, плитка, человек…">
<select id="cluster"><option value="">все темы</option></select><button id="go">Найти</button></header>
<main>
<div>
 <div class="card"><h3>Результаты поиска <span id="hcount" class="meta"></span></h3><div id="hits" class="meta">Введите запрос</div></div>
 <div class="card"><h3>Ролики</h3><div id="videos"></div></div>
 <div class="card"><h3>Темы (распределение роликов)</h3><div id="topics"></div></div>
</div>
<div>
 <div class="card"><h3 id="vtitle">Выберите ролик или результат поиска</h3>
  <video id="player" controls preload="metadata"></video><div id="vlink" class="meta"></div></div>
 <div class="card"><h3>Временная шкала событий <span class="meta">(клик — перейти к моменту)</span></h3><div id="timeline"></div></div>
</div>
</main>
<script>
const D = __DATA__;
const $ = s => document.querySelector(s);
const V = D.videos, vmap = Object.fromEntries(V.map(v => [v.id, v]));
const player = $('#player');
let cur = null, hits = [], TL = null;
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = t => { t = Math.floor(t); return String(Math.floor(t/60)).padStart(2,'0') + ':' + String(t%60).padStart(2,'0'); };
const words = s => (s.toLowerCase().replace(/ё/g,'е').match(/[\p{L}\p{N}]+/gu)) || [];
const stem = w => w.length > 5 ? w.slice(0,5) : w;          // как запасной стеммер в textutils.py
const matches = (text, qs) => { const ws = words(text); return qs.every(q => ws.some(w => w.startsWith(q))); };
const KIND = {loud_peak:['громкость','#f58518'], scene_change:['смена сцены','#8e6bbf']};
const PAL = ['#4c78a8','#54a24b','#e45756','#72b7b2','#b279a2','#9d755d'];

function openVideo(id, t) {
  const v = vmap[id]; if (!v) return;
  const go = () => { player.currentTime = t; player.play().catch(() => {}); };
  if (cur !== id) {
    cur = id; $('#vtitle').textContent = v.title;
    $('#vlink').innerHTML = v.url ? 'Оригинал: <a target="_blank" href="' + esc(v.url) + '">' + esc(v.url) + '</a>' : '';
    player.addEventListener('loadedmetadata', go, {once: true}); player.src = v.src; drawTimeline();
  } else go();
}

function doSearch() {
  const qs = words($('#q').value).map(stem).filter(x => x.length > 1), cl = $('#cluster').value;
  hits = [];
  for (const v of V) {
    if (!qs.length || (cl !== '' && String(v.cluster) !== cl)) continue;
    for (const s of v.segments) if (matches(s.t, qs)) hits.push({v:v.id, s:s.s, e:s.e, k:'речь', t:s.t});
    for (const e of v.events) if (e.k === 'object' && matches(e.l, qs)) hits.push({v:v.id, s:e.s, e:e.e, k:'объект', t:e.l + ' (уверенность ' + e.c + ')'});
  }
  $('#hcount').textContent = qs.length ? '— ' + hits.length : '';
  $('#hits').innerHTML = !qs.length ? 'Введите запрос' : hits.length ? hits.slice(0, 200).map((h, i) =>
    `<div class="item" data-i="${i}"><b>${esc(vmap[h.v].title)}</b><span class="pill">${h.k}</span><br>${fmt(h.s)}–${fmt(h.e)} · ${esc(h.t)}</div>`).join('') : 'Ничего не найдено';
  drawTimeline();
}

function lanesFor(v) {
  const lanes = [{name:'речь', color:'#9fb3c8', items: v.segments.map(s => ({s:s.s, e:s.e, tip:s.t}))}];
  for (const k in KIND) lanes.push({name:KIND[k][0], color:KIND[k][1],
    items: v.events.filter(e => e.k === k).map(e => ({s:e.s, e:e.e, tip:e.l + ' · ' + e.c}))});
  const dur = {};
  v.events.filter(e => e.k === 'object').forEach(e => dur[e.l] = (dur[e.l] || 0) + e.e - e.s);
  Object.keys(dur).sort((a,b) => dur[b]-dur[a]).slice(0, 6).forEach((l, i) => lanes.push({name:l, color:PAL[i % PAL.length],
    items: v.events.filter(e => e.k === 'object' && e.l === l).map(e => ({s:e.s, e:e.e, tip:l + ' · ' + e.c}))}));
  const mine = hits.filter(h => h.v === v.id);
  if (mine.length) lanes.push({name:'найдено', color:'#d62728', items: mine.map(h => ({s:h.s, e:h.e, tip:h.t}))});
  return lanes;
}

function drawTimeline() {
  const box = $('#timeline'), v = vmap[cur];
  if (!v) { box.innerHTML = ''; return; }
  const lanes = lanesFor(v), W = Math.max(box.clientWidth, 500), L = 110, H = 18, G = 6, R = 10;
  let dur = v.duration || 0;
  lanes.forEach(l => l.items.forEach(i => dur = Math.max(dur, i.e))); dur = dur || 1;
  const x = t => L + (W - L - R) * t / dur, Ht = lanes.length * (H + G) + 22;
  let svg = `<svg id="tl" width="${W}" height="${Ht}">`;
  lanes.forEach((ln, i) => {
    const y = i * (H + G);
    svg += `<text x="4" y="${y + 13}" font-size="12">${esc(ln.name)}</text><rect x="${L}" y="${y}" width="${W-L-R}" height="${H}" fill="#eee"/>`;
    ln.items.forEach(it => svg += `<rect class="ev" data-s="${it.s}" x="${x(it.s)}" y="${y}" width="${Math.max(2, x(it.e) - x(it.s))}" height="${H}" fill="${ln.color}"><title>${fmt(it.s)}–${fmt(it.e)} ${esc(it.tip)}</title></rect>`);
  });
  const step = dur > 1800 ? 300 : dur > 600 ? 60 : dur > 120 ? 30 : 10;
  for (let t = 0; t <= dur; t += step) svg += `<text x="${x(t)}" y="${Ht - 4}" font-size="10" text-anchor="middle" fill="#666">${fmt(t)}</text>`;
  svg += `<line id="ph" x1="${L}" x2="${L}" y1="0" y2="${Ht - 14}" stroke="red" stroke-width="1.5"/></svg>`;
  box.innerHTML = svg; TL = {L, W, R, dur, x};
  $('#tl').addEventListener('click', e => {
    if (e.target.dataset && e.target.dataset.s !== undefined) return openVideo(cur, parseFloat(e.target.dataset.s));
    const r = $('#tl').getBoundingClientRect(), t = (e.clientX - r.left - L) / (W - L - R) * dur;
    if (t >= 0 && t <= dur) openVideo(cur, t);
  });
}
player.addEventListener('timeupdate', () => { const ph = $('#ph'); if (ph && TL) { const px = TL.x(player.currentTime); ph.setAttribute('x1', px); ph.setAttribute('x2', px); } });
window.addEventListener('resize', drawTimeline);

function init() {
  const sel = $('#cluster'), cl = D.clusters;
  cl.forEach(c => sel.insertAdjacentHTML('beforeend', `<option value="${c.cluster}">тема ${c.cluster}: ${esc(c.top_terms.slice(0,3).join(', '))}</option>`));
  const mx = Math.max(1, ...cl.map(c => c.size));
  $('#topics').innerHTML = cl.map(c => `<div class="item" data-c="${c.cluster}"><b>${c.cluster === -1 ? 'вне тем' : 'тема ' + c.cluster}</b> · ${c.size} рол.
    <div class="bar" style="width:${100 * c.size / mx}%"></div><div class="meta">${esc(c.top_terms.join(', '))}</div></div>`).join('') || 'Темы не посчитаны';
  const drawList = () => { const f = sel.value;
    $('#videos').innerHTML = V.filter(v => f === '' || String(v.cluster) === f).map(v =>
      `<div class="item" data-v="${v.id}">${esc(v.title)}<span class="pill">тема ${v.cluster ?? '—'}</span><div class="meta">${fmt(v.duration)} · событий: ${v.events.length} · фраз: ${v.segments.length}</div></div>`).join('');
  };
  drawList();
  sel.addEventListener('change', () => { drawList(); doSearch(); });
  $('#go').addEventListener('click', doSearch);
  $('#q').addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
  $('#hits').addEventListener('click', e => { const it = e.target.closest('[data-i]'); if (it) { const h = hits[+it.dataset.i]; openVideo(h.v, h.s); } });
  $('#videos').addEventListener('click', e => { const it = e.target.closest('[data-v]'); if (it) openVideo(it.dataset.v, 0); });
  $('#topics').addEventListener('click', e => { const it = e.target.closest('[data-c]'); if (it) { sel.value = it.dataset.c; drawList(); doSearch(); } });
}
init();
</script></body></html>
"""
