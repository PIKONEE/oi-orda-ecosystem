/* ============================================================
   Карта музыкальных традиций (Leaflet, локальные тайлы, офлайн).
   Клик по региону → боковая карточка. Демо звука: вшитый клип → синт-фолбэк.
   ============================================================ */
window.MMap = (function () {
"use strict";
const REGIONS = window.REGIONS || [];
const WORLD = [[-85,-180],[85,180]];
let map, markersById = {}, current = null;
const $ = s => document.querySelector(s);
const esc = s => String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const lang = () => window.APP.lang;
const instr = r => (lang()==="kz" ? r.instrKz : r.instrRu) || r.instrRu || [];

function capWorldZoom(){
  if (!map) return;
  let z = map.getBoundsZoom(L.latLngBounds(WORLD), true);
  z = Math.max(2, Math.min(6, z));
  if (z !== map.getMinZoom()) map.setMinZoom(z);
  if (map.getZoom() < z) map.setZoom(z);
}

function init(){
  if (typeof L === "undefined") return;
  map = L.map("mmap", { zoomControl:false, attributionControl:true, minZoom:2, maxZoom:6,
    worldCopyJump:false, maxBounds:WORLD, maxBoundsViscosity:1.0 });
  L.control.zoom({ position:"topright" }).addTo(map);
  map.attributionControl.setPrefix("");
  // базовый слой — весь мир (выше z3 апскейл z3 → нет пустых краёв)
  L.tileLayer("tiles/{z}/{x}/{y}.jpg", { minZoom:2, maxZoom:6, maxNativeZoom:3, noWrap:true,
    bounds:WORLD, attribution:"Esri — World Physical Map" }).addTo(map);
  map.setView([25, 25], 2);
  capWorldZoom(); map.on("resize", capWorldZoom);

  REGIONS.forEach(r => {
    const m = L.circleMarker([r.lat, r.lng], {
      radius: r.kazakh ? 11 : 8, color:"#1d1b2e", weight:2,
      fillColor: r.kazakh ? "#f1d18a" : "#d9b25f", fillOpacity:.96, className: r.kazakh ? "mk-kz" : ""
    });
    m.bindTooltip(() => esc(APP.pick(r,"name")), { direction:"top", className:"mk-tip" });
    m.on("click", () => select(r));
    m.addTo(map); markersById[r.id] = m;
  });
  // подсказка по умолчанию
  $("#regionCard").innerHTML = `<div class="card-empty">${esc(APP.t("mapHint"))}</div>`;
}

function refresh(){ if (map) setTimeout(() => map.invalidateSize(), 60); }

function select(r){
  current = r;
  const box = $("#regionCard");
  let html = `<div class="rc-head"><h2>${esc(APP.pick(r,"name"))}</h2>` +
    `<button class="listen" id="rcListen">${esc(APP.t("listen"))}</button></div>`;
  html += `<div class="rc-sec"><div class="rc-lbl">${esc(APP.t("mapInstruments"))}</div>` +
    `<div class="chips">${instr(r).map(i=>`<span class="chip">${esc(i)}</span>`).join("")}</div></div>`;
  html += `<div class="rc-sec"><div class="rc-lbl">${esc(APP.t("mapRhythm"))}</div>` +
    `<p>${esc(APP.pick(r,"rhythm"))}</p></div>`;
  html += `<div class="rc-sec"><div class="rc-lbl">${esc(APP.t("mapTradition"))}</div>` +
    `<p>${esc(APP.pick(r,"desc"))}</p></div>`;
  if (r.extra && r.extra.length){
    html += `<div class="rc-extra">` + r.extra.map(e =>
      `<div class="rc-x"><h4>${esc(APP.pick(e,"title"))}</h4><p>${esc(APP.pick(e,"text"))}</p></div>`).join("") + `</div>`;
  }
  box.innerHTML = html;
  box.scrollTop = 0;
  $("#rcListen").addEventListener("click", () => playDemo(r));
  Object.keys(markersById).forEach(id => {
    const el = markersById[id].getElement(); if (el) el.classList.toggle("mk-active", id === r.id);
  });
}

function playDemo(r){
  if (!window.AUDIO) return;
  AUDIO.ensure();
  AUDIO.playKey(r.audio, () => AUDIO.playScale(r.scale || "major", 60), r.audioStart || 0);
}

function relang(){
  document.querySelectorAll("#mmap .leaflet-tooltip").forEach(t => t.remove());
  if (current) select(current);
  else { const b = $("#regionCard"); if (b) b.innerHTML = `<div class="card-empty">${esc(APP.t("mapHint"))}</div>`; }
}
window.APP && window.APP.onLang(relang);

return { init, refresh, relang };
})();
