/* ============================================================
   Музыкальная энциклопедия — оркестратор: язык, навигация, запуск.
   Разделы: js/map.js (MMap), js/timeline.js (MTimeline), js/ear.js (MEar).
   ============================================================ */
(function () {
"use strict";
const I18N = window.I18N || { ru:{}, kz:{} };

const APP = window.APP = {
  lang: localStorage.getItem("me_lang") || "ru",
  _cbs: [],
  t(k){ return (I18N[this.lang] && I18N[this.lang][k]) || (I18N.ru && I18N.ru[k]) || k; },
  L(o){ if(!o) return ""; return this.lang === "kz" ? (o.kz != null ? o.kz : o.ru) : (o.ru != null ? o.ru : o.kz); },
  pick(obj, field){ return obj[field + (this.lang === "kz" ? "Kz" : "Ru")] != null
      ? obj[field + (this.lang === "kz" ? "Kz" : "Ru")] : obj[field + "Ru"]; },
  onLang(cb){ this._cbs.push(cb); },
  setLang(l){
    this.lang = l; localStorage.setItem("me_lang", l);
    document.documentElement.lang = l;
    document.querySelectorAll(".lang button").forEach(b => b.classList.toggle("active", b.dataset.lang === l));
    applyStatic();
    this._cbs.forEach(cb => { try { cb(); } catch(e){} });
  }
};
const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));

function applyStatic(){ $$("[data-i18n]").forEach(el => el.textContent = APP.t(el.dataset.i18n)); }

let mapInited = false;
function showView(name){
  $$(".view").forEach(v => v.classList.toggle("active", v.id === "view-" + name));
  $$(".nav button").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  if (name === "map" && !mapInited){ mapInited = true; if (window.MMap) MMap.init(); }
  else if (name === "map" && window.MMap && MMap.refresh) MMap.refresh();
}

function renderCredits(){
  const C = window.CREDITS || { items:[] };
  const note = APP.lang === "kz" ? C.noteKz : C.noteRu;
  const items = (C.items||[]).map(it =>
    `<li><b>${(APP.lang==="kz"?it.titleKz:it.titleRu)||it.key}</b> — ${it.source||""} <span class="lic">${it.license||""}</span></li>`).join("");
  $("#creditsBody").innerHTML = `<p class="cr-note">${note||""}</p>` + (items ? `<ul class="cr-list">${items}</ul>` : "");
}
function bind(){
  $$(".lang button").forEach(b => b.addEventListener("click", () => APP.setLang(b.dataset.lang)));
  $$(".nav button").forEach(b => b.addEventListener("click", () => showView(b.dataset.view)));
  $("#creditsBtn").addEventListener("click", () => { renderCredits(); $("#creditsModal").hidden = false; });
  $("#creditsClose").addEventListener("click", () => { $("#creditsModal").hidden = true; });
  $("#creditsModal").addEventListener("click", e => { if (e.target.id === "creditsModal") e.currentTarget.hidden = true; });
  // первый жест → разблокировать аудио (политика автоплея)
  const unlock = () => { if (window.AUDIO) AUDIO.ensure(); window.removeEventListener("pointerdown", unlock); };
  window.addEventListener("pointerdown", unlock, { once:true });
  // эквалайзер в шапке реагирует на воспроизведение
  document.addEventListener("click", e => { if (e.target.closest(".listen,#earPlay,#earReplay")) pulseEq(); });
}
function pulseEq(){
  const eq = $("#eq"); if (!eq) return;
  eq.classList.add("playing"); clearTimeout(pulseEq._t);
  pulseEq._t = setTimeout(() => eq.classList.remove("playing"), 2600);
}

function initCore(){
  try {
    if (typeof qt !== "undefined" && qt.webChannelTransport && typeof QWebChannel !== "undefined")
      new QWebChannel(qt.webChannelTransport, ch => { window.core = ch.objects.core; });
    else if (typeof core !== "undefined") window.core = core;
  } catch (e) {}
}

function boot(){
  document.documentElement.lang = APP.lang;
  $$(".lang button").forEach(b => b.classList.toggle("active", b.dataset.lang === APP.lang));
  applyStatic();
  bind();
  if (window.MTimeline) MTimeline.init();
  if (window.MEar) MEar.init();
  showView("map");           // карта по умолчанию (инициализируется лениво)
  initCore();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
})();
