/* ============================================================
   Карта истории Казахстана — логика (Leaflet)
   Данные: window.ERAS, CATS, EVENTS, TERRITORIES, BASE_GEO, I18N
   ============================================================ */
(function () {
"use strict";
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
function log(m){ try { window.core && window.core.log && window.core.log("[map] " + m); } catch (e) {} }

const ERAS = window.ERAS || [];
const CATS = window.CATS || [];
const EVENTS = window.EVENTS || [];
const TERR = window.TERRITORIES || {};
const BASE = window.BASE_GEO || { type:"FeatureCollection", features:[] };
const I18N = window.I18N || { ru:{}, kz:{} };

const state = {
  lang: localStorage.getItem("hm_lang") || "ru",
  year: 1465,
  cats: new Set(CATS.map(c => c.key))
};
const YMIN = -800, YMAX = 2025;

const t = k => (I18N[state.lang] && I18N[state.lang][k]) || (I18N.ru && I18N.ru[k]) || k;
const catOf = k => CATS.find(c => c.key === k) || { key:k, color:"#8a7350", nameRu:k, nameKz:k };
const catName = c => state.lang === "kz" ? c.nameKz : c.nameRu;
const eraName = e => state.lang === "kz" ? e.nameKz : e.nameRu;
const evTitle = e => state.lang === "kz" ? e.titleKz : e.titleRu;
const evDesc  = e => state.lang === "kz" ? e.descKz  : e.descRu;
function fmtYear(y){ return y < 0 ? (Math.abs(y) + " " + t("bce")) : ("" + y); }
function activeEra(y){ let cur = ERAS[0]; for (const e of ERAS) if (e.from <= y) cur = e; return cur; }
function eraUpper(era){ const nxt = ERAS.find(e => e.from > era.from); return nxt ? nxt.from : (YMAX + 1); }
function kzFeature(){ return (BASE.features || []).find(f => f.properties && f.properties.name === "Kazakhstan"); }

let map, terrLayer, markerLayer, markerById = {};

const WORLD_BOUNDS = [[-85, -180], [85, 180]];
function initMap(){
  map = L.map("map", { zoomControl:false, attributionControl:true, minZoom:2, maxZoom:6,
    worldCopyJump:false, maxBounds:WORLD_BOUNDS, maxBoundsViscosity:1.0 });
  L.control.zoom({ position:"topright" }).addTo(map);   // справа, чтобы не перекрывать подпись эпохи слева
  map.attributionControl.setPrefix("");
  // базовый слой — ВЕСЬ МИР; есть только тайлы z2–3, выше — апскейлим z3
  // (maxNativeZoom), поэтому пустых «голубых» краёв нет ни на каком масштабе
  L.tileLayer("tiles/{z}/{x}/{y}.jpg", { minZoom:2, maxZoom:6, maxNativeZoom:3, noWrap:true,
    bounds:[[-85,-180],[85,180]], attribution:"Esri — World Physical Map" }).addTo(map);
  // детальный слой — регион Казахстана в высоком разрешении (z4–6) поверх базового
  L.tileLayer("tiles/{z}/{x}/{y}.jpg", { minZoom:4, maxZoom:6, minNativeZoom:4, maxNativeZoom:6,
    noWrap:true, bounds:[[37,45],[58,90]] }).addTo(map);
  // тонкие современные границы для ориентира
  L.geoJSON(BASE, { interactive:false, style:()=>({ color:"#6b4f28", weight:1, opacity:.30, fill:false }) }).addTo(map);
  terrLayer = L.layerGroup().addTo(map);
  markerLayer = L.layerGroup().addTo(map);
  map.setView([48.0, 68.0], 4);
  capWorldZoom();              // нижний предел зума = когда мир заполняет экран целиком (без синих краёв)
  map.on("resize", capWorldZoom);
}

/* Не давать отдалять карту дальше, чем когда мир ещё закрывает весь экран:
   так при максимальном отдалении нет пустых «синих» полей по краям. */
function capWorldZoom(){
  if (!map) return;
  let z = map.getBoundsZoom(L.latLngBounds(WORLD_BOUNDS), true); // мин. зум, при котором вьюпорт внутри мира
  z = Math.max(2, Math.min(6, z));
  if (z !== map.getMinZoom()) map.setMinZoom(z);
  if (map.getZoom() < z) map.setZoom(z);
}

/* Сглаживание ломаных контуров в плавные кривые (алгоритм Чайкина) —
   чтобы «условные» территории выглядели органично, без острых углов. */
function chaikinRing(ring, iters){
  let pts = ring.slice();
  if (pts.length > 2 && pts[0][0] === pts[pts.length-1][0] && pts[0][1] === pts[pts.length-1][1])
    pts = pts.slice(0, -1);
  for (let k = 0; k < iters; k++){
    const out = [];
    for (let i = 0; i < pts.length; i++){
      const a = pts[i], b = pts[(i+1) % pts.length];
      out.push([a[0]*0.75 + b[0]*0.25, a[1]*0.75 + b[1]*0.25]);
      out.push([a[0]*0.25 + b[0]*0.75, a[1]*0.25 + b[1]*0.75]);
    }
    pts = out;
  }
  pts.push(pts[0].slice());
  return pts;
}
function smoothGeom(geom, iters){
  if (!geom) return geom;
  const sm = poly => poly.map(ring => chaikinRing(ring, iters));
  if (geom.type === "Polygon")      return { type:"Polygon",      coordinates: sm(geom.coordinates) };
  if (geom.type === "MultiPolygon") return { type:"MultiPolygon", coordinates: geom.coordinates.map(sm) };
  return geom;
}

function drawTerritory(){
  terrLayer.clearLayers();
  const note = document.getElementById("approxNote");
  const era = activeEra(state.year), col = era.color;
  const terr = era.terr ? TERR[era.terr] : null;   // terr=null → казахского государства нет, территорию не рисуем
  if (!terr || !terr.geometry){ if (note) note.style.display = "none"; return; }
  if (note) note.style.display = "";
  let geom = terr.geometry, approx = terr.approx;
  // современный Казахстан — берём точную границу из base_geo (совпадает с линией границы)
  if (era.terr === "modern"){ const kz = kzFeature(); if (kz && kz.geometry){ geom = kz.geometry; approx = false; } }
  // условные (кочевые) территории — сглаживаем в мягкие органичные контуры
  if (approx) geom = smoothGeom(geom, 3);
  const layer = L.geoJSON(geom, { interactive:false, smoothFactor: approx ? 1 : 1.3,
    style:()=>({ color:col, weight: approx ? 1.5 : 2, opacity:.5, fillColor:col,
      fillOpacity: approx ? .14 : .24, dashArray: approx ? "1 6" : null,
      lineJoin:"round", lineCap:"round" }) });
  terrLayer.addLayer(layer);
}

function drawMarkers(){
  markerLayer.clearLayers(); markerById = {};
  const era = activeEra(state.year);
  // показываем события этого периода ПО МЕРЕ прохождения года ползунком (year ≤ выбранного)
  const vis = EVENTS.filter(e => e.year >= era.from && e.year <= state.year && state.cats.has(e.cat));
  const latest = vis.reduce((m, e) => e.year > m ? e.year : m, -Infinity);
  vis.forEach(e => {
    const c = catOf(e.cat), fresh = e.year === latest;
    const m = L.circleMarker([e.lat, e.lng], { radius: fresh ? 9 : 7, color:"#3a2c1a",
      weight: fresh ? 2.5 : 1.5, fillColor:c.color, fillOpacity:.95,
      className: fresh ? "mk-fresh" : "" });
    m.bindPopup(popupHtml(e), { maxWidth:300, className:"hist-popup" });
    m.addTo(markerLayer); markerById[e.id] = m;
  });
}
function popupHtml(e){
  const c = catOf(e.cat);
  return `<span class="pop-yr" style="background:${c.color}">${esc(fmtYear(e.year))}</span>` +
    `<div class="pop-tt">${esc(evTitle(e))}</div>` +
    `<div class="pop-ds">${esc(evDesc(e))}</div>` +
    `<div class="pop-foot"><span class="pop-cat" style="color:${c.color}">${esc(catName(c))}</span>` +
    `<button class="pop-more" data-detail="${esc(e.id)}" style="--cat:${c.color}">${esc(t("readMore"))} ›</button></div>`;
}

/* ── Полноэкранная страница-статья события ───────────────────────────── */
function evDetail(e){
  // detail может быть только на одном языке — мягкий откат на ru
  if (!e.detail) return null;
  return e.detail[state.lang] || e.detail.ru || e.detail.kz || null;
}
function detailHtml(e){
  const c = catOf(e.cat), era = activeEra(e.year), d = evDetail(e);
  const lead = (d && d.lead) || evDesc(e);
  let html = "";
  // верхняя панель
  html += `<div class="d-bar">` +
    `<button class="d-back" id="dBack"><span class="d-ar">‹</span>${esc(t("back"))}</button>` +
    `<span class="d-bar-cat"><span class="d-dot" style="background:${c.color}"></span>${esc(catName(c))}</span>` +
    `</div>`;
  // центрированная «страница»
  html += `<div class="d-page" style="--cat:${c.color}">`;
  // «шапка» статьи
  html += `<header class="d-hero">` +
    `<div class="d-era">${esc(eraName(era))}</div>` +
    `<div class="d-yearbig">${esc(fmtYear(e.year))}</div>` +
    `<h1 class="d-title">${esc(evTitle(e))}</h1>` +
    `</header>`;
  html += `<div class="d-rule"><span>✦</span></div>`;
  // основной столбец
  html += `<div class="d-body">`;
  html += `<p class="d-lead">${esc(lead)}</p>`;
  // ключевые факты
  const facts = (d && d.facts) || [];
  if (facts.length){
    html += `<aside class="d-facts"><div class="d-facts-h">${esc(t("keyFacts"))}</div><dl>`;
    facts.forEach(f => { html += `<div class="d-fact"><dt>${esc(f.k)}</dt><dd>${esc(f.v)}</dd></div>`; });
    html += `</dl></aside>`;
  }
  // разделы
  const secs = (d && d.sections) || [];
  if (secs.length){
    secs.forEach(s => {
      if (s.h) html += `<h2 class="d-h2">${esc(s.h)}</h2>`;
      (s.p || []).forEach(p => { html += `<p class="d-p">${esc(p)}</p>`; });
    });
  } else if (!d){
    html += `<p class="d-note">${esc(t("detailComing"))}</p>`;
  }
  // источники
  const src = (d && d.sources) || [];
  if (src.length){
    html += `<div class="d-sources"><div class="d-sources-h">${esc(t("sources"))}</div><ul>`;
    src.forEach(s => { html += `<li>${esc(s)}</li>`; });
    html += `</ul></div>`;
  }
  // действия
  html += `<div class="d-actions"><button class="d-map" id="dMap">📍 ${esc(t("showOnMap"))}</button></div>`;
  html += `</div>`; // .d-body
  html += `</div>`; // .d-page
  return html;
}
function openDetail(e){
  state.detailId = e.id;
  const scroll = $("#detailScroll");
  scroll.innerHTML = detailHtml(e);
  const ov = $("#detail");
  ov.classList.add("open"); ov.setAttribute("aria-hidden", "false");
  document.body.classList.add("detail-open");
  scroll.scrollTop = 0;
  // закрыть popup на карте, чтобы не оставался под оверлеем
  if (map) map.closePopup();
  $("#dBack").addEventListener("click", closeDetail);
  const dm = $("#dMap");
  if (dm) dm.addEventListener("click", () => showOnMap(e));
  try { scroll.focus(); } catch (err) {}
  log("detail open: " + e.id);
}
function closeDetail(){
  state.detailId = null;
  const ov = $("#detail");
  ov.classList.remove("open"); ov.setAttribute("aria-hidden", "true");
  document.body.classList.remove("detail-open");
}
function showOnMap(e){
  closeDetail();
  if (e.year > state.year) setYear(e.year);   // перемотка к году → метка появится
  const m = markerById[e.id];
  if (m && map){ map.flyTo([e.lat, e.lng], Math.max(map.getZoom(), 6), { duration:.6 }); setTimeout(() => m.openPopup(), 380); }
}

/* категории-фильтр */
function renderCats(){
  const wrap = $("#cats"); wrap.innerHTML = "";
  CATS.forEach(c => {
    const b = document.createElement("button");
    b.className = "cat-chip" + (state.cats.has(c.key) ? "" : " off");
    b.dataset.cat = c.key;
    b.innerHTML = `<span class="dot" style="background:${c.color}"></span>${esc(catName(c))}`;
    wrap.appendChild(b);
  });
}

/* список событий текущего периода */
function renderEvents(){
  const era = activeEra(state.year), up = eraUpper(era);
  const list = EVENTS.filter(e => e.year >= era.from && e.year < up && state.cats.has(e.cat))
                     .sort((a,b)=>a.year-b.year);
  $("#evCount").textContent = list.length + " " + t("eventsCount");
  const box = $("#events"); box.innerHTML = "";
  if (!list.length){ box.innerHTML = `<div class="empty">${t("noEvents")}</div>`; return; }
  list.forEach(e => {
    const c = catOf(e.cat);
    const el = document.createElement("button");
    el.className = "ev" + (e.year > state.year ? " future" : "");  // ещё не наступило → приглушено
    el.dataset.id = e.id; el.style.setProperty("--cat", c.color);
    el.innerHTML = `<span class="yr">${esc(fmtYear(e.year))}</span><span class="tt">${esc(evTitle(e))}</span>`;
    box.appendChild(el);
  });
}

function updateTime(){
  const era = activeEra(state.year);
  $("#yearVal").textContent = fmtYear(state.year);
  $("#eraVal").textContent = eraName(era);
  $("#eraBadge").innerHTML = `<div class="en">${esc(eraName(era))}</div><div class="ey">${esc(fmtYear(era.from))} — ${esc(fmtYear(eraUpper(era)-1))}</div>`;
  drawTerritory();
  drawMarkers();
  renderEvents();
}

function setYear(y){
  state.year = Math.max(YMIN, Math.min(YMAX, Math.round(y)));
  $("#year").value = state.year;
  updateTime();
}
function jumpEra(dir){
  const era = activeEra(state.year);
  if (dir > 0){ const nxt = ERAS.find(e => e.from > era.from); if (nxt) setYear(nxt.from); }
  else { const prevs = ERAS.filter(e => e.from < era.from); if (prevs.length){ setYear(prevs[prevs.length-1].from); }
         else setYear(era.from); }
}

function applyStatic(){
  $$("[data-i18n]").forEach(el => el.textContent = t(el.dataset.i18n));
  document.documentElement.lang = state.lang;
  $("#approxNote").textContent = t("approxNote");
  $("#prevEra").title = t("prevEra"); $("#nextEra").title = t("nextEra");
}
function setLang(l){
  state.lang = l; localStorage.setItem("hm_lang", l);
  $$(".lang button").forEach(b => b.classList.toggle("active", b.dataset.lang === l));
  applyStatic(); renderCats(); updateTime();
  // если открыта страница-статья — перерисовать её на новом языке
  if (state.detailId){ const ev = EVENTS.find(x => x.id === state.detailId); if (ev) openDetail(ev); }
}

function bind(){
  $$(".lang button").forEach(b => b.addEventListener("click", () => setLang(b.dataset.lang)));
  $("#year").addEventListener("input", e => setYear(+e.target.value));
  $("#prevEra").addEventListener("click", () => jumpEra(-1));
  $("#nextEra").addEventListener("click", () => jumpEra(1));
  $("#cats").addEventListener("click", e => {
    const b = e.target.closest("[data-cat]"); if (!b) return;
    const k = b.dataset.cat;
    if (state.cats.has(k)) state.cats.delete(k); else state.cats.add(k);
    renderCats(); drawMarkers(); renderEvents();
  });
  $("#events").addEventListener("click", e => {
    const el = e.target.closest("[data-id]"); if (!el) return;
    const ev = EVENTS.find(x => x.id === el.dataset.id); if (!ev) return;
    if (ev.year > state.year) setYear(ev.year);      // перемотка к событию → метка появляется
    const m = markerById[ev.id];
    if (m){ map.flyTo([ev.lat, ev.lng], Math.max(map.getZoom(), 6), { duration:.6 }); setTimeout(()=>m.openPopup(), 350); }
  });
  // «Подробнее» в popup (контент попапа Leaflet в DOM — делегируем клик с document)
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-detail]"); if (!b) return;
    const ev = EVENTS.find(x => x.id === b.dataset.detail); if (ev) openDetail(ev);
  });
  // закрытие страницы-статьи: клик по фону и Esc
  $("#detail").addEventListener("click", e => { if (e.target.id === "detail") closeDetail(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && state.detailId) closeDetail(); });
}

function initCore(){
  try {
    if (typeof qt !== "undefined" && qt.webChannelTransport && typeof QWebChannel !== "undefined")
      new QWebChannel(qt.webChannelTransport, ch => { window.core = ch.objects.core; log("ready"); });
    else if (typeof core !== "undefined") window.core = core;
  } catch (e) {}
}

function boot(){
  if (!EVENTS.length || typeof L === "undefined"){
    document.body.innerHTML = '<div style="display:grid;place-items:center;height:100vh;font-family:sans-serif;color:#6b5638;text-align:center"><div><div style="font-size:3rem">🗺️</div><p>Карта не загрузилась (проверьте lib/leaflet и data/).</p></div></div>';
    return;
  }
  initMap();
  $$(".lang button").forEach(b => b.classList.toggle("active", b.dataset.lang === state.lang));
  applyStatic();
  renderCats();
  $("#year").value = state.year;
  updateTime();
  bind();
  initCore();
  log("booted: " + EVENTS.length + " событий");
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
})();
