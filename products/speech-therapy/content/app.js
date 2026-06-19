/* ============================================================
   Кабинет логопеда — оркестратор: язык, домашний экран, навигация.
   Модули: js/cards.js (Cards), js/game.js (Game), js/twisters.js (Twisters).
   ============================================================ */
(function () {
"use strict";
const I18N = window.I18N || { ru:{}, kz:{} };
const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));

const APP = window.APP = {
  lang: localStorage.getItem("sp_lang") || "ru",
  _cbs: [],
  t(k){ return (I18N[this.lang] && I18N[this.lang][k]) || (I18N.ru && I18N.ru[k]) || k; },
  onLang(cb){ this._cbs.push(cb); },
  setLang(l){
    this.lang = l; localStorage.setItem("sp_lang", l);
    document.documentElement.lang = l;
    $$(".lang button").forEach(b => b.classList.toggle("active", b.dataset.lang === l));
    applyStatic();
    this._cbs.forEach(cb => { try { cb(); } catch(e){} });
  }
};
function applyStatic(){ $$("[data-i18n]").forEach(el => el.textContent = APP.t(el.dataset.i18n)); }

const inited = {};
function showView(name){
  $$(".view").forEach(v => v.classList.toggle("active", v.id === "view-" + name));
  $("#backBtn").style.visibility = (name === "home") ? "hidden" : "visible";
  if (name !== "home"){
    const mod = name === "cards" ? window.Cards : name === "game" ? window.Game : window.Twisters;
    if (mod){
      if (!inited[name]){ inited[name] = true; mod.init(); }   // первый раз — init (рендерит текущий язык)
      else mod.relang();                                       // потом — перерисовать под текущий язык
    }
  }
  if (window.SP) SP.stopAll();
}

function renderCredits(){
  const C = window.CREDITS || {}; const note = APP.lang === "kz" ? C.noteKz : C.noteRu;
  $("#creditsBody").innerHTML = "<p>" + (note || "") + "</p>";
}

function bind(){
  $$(".lang button").forEach(b => b.addEventListener("click", () => APP.setLang(b.dataset.lang)));
  $$("[data-go]").forEach(b => b.addEventListener("click", () => showView(b.dataset.go)));
  $("#backBtn").addEventListener("click", () => showView("home"));
  $("#creditsBtn").addEventListener("click", () => { renderCredits(); $("#creditsModal").hidden = false; });
  $("#creditsClose").addEventListener("click", () => { $("#creditsModal").hidden = true; });
  $("#creditsModal").addEventListener("click", e => { if (e.target.id === "creditsModal") e.currentTarget.hidden = true; });
  const unlock = () => { if (window.SP) SP.ensure(); window.removeEventListener("pointerdown", unlock); };
  window.addEventListener("pointerdown", unlock, { once:true });
}

function boot(){
  document.documentElement.lang = APP.lang;
  $$(".lang button").forEach(b => b.classList.toggle("active", b.dataset.lang === APP.lang));
  applyStatic();
  bind();
  showView("home");
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
})();
