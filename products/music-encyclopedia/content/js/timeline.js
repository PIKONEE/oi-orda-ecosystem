/* ============================================================
   Лента музыкальной истории. Клик по эпохе → карточка + фрагмент.
   ============================================================ */
window.MTimeline = (function () {
"use strict";
const ERAS = window.MUSIC_ERAS || [];
let current = null;
const $ = s => document.querySelector(s);
const esc = s => String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const instr = e => (APP.lang==="kz" ? e.instrKz : e.instrRu) || e.instrRu || [];

function init(){
  const band = $("#tlBand");
  band.innerHTML = ERAS.map(e =>
    `<button class="tl-era" data-id="${e.id}"><span class="tl-name">${esc(APP.pick(e,"name"))}</span>` +
    `<span class="tl-years">${e.from}–${e.to}</span></button>`).join("");
  band.addEventListener("click", ev => {
    const b = ev.target.closest("[data-id]"); if (!b) return;
    select(ERAS.find(e => e.id === b.dataset.id));
  });
  $("#tlCard").innerHTML = `<div class="card-empty">${esc(APP.t("tlHint"))}</div>`;
}

function select(e){
  current = e;
  document.querySelectorAll(".tl-era").forEach(b => b.classList.toggle("active", b.dataset.id === e.id));
  const traits = (e.traits||[]).map(t => `<li>${esc(APP.L(t))}</li>`).join("");
  const insts = instr(e).map(i => `<span class="chip">${esc(i)}</span>`).join("");
  const comps = (e.composers||[]).map(c => `<span class="chip chip-c">${esc(c)}</span>`).join("");
  let html = `<div class="rc-head"><h2>${esc(APP.pick(e,"name"))} <small>${e.from}–${e.to}</small></h2>` +
    `<button class="listen" id="tlListen">${esc(APP.t("listen"))}</button></div>`;
  html += `<p class="tl-desc">${esc(APP.pick(e,"desc"))}</p>`;
  html += `<div class="rc-sec"><div class="rc-lbl">${esc(APP.t("tlTraits"))}</div><ul class="traits">${traits}</ul></div>`;
  html += `<div class="rc-sec"><div class="rc-lbl">${esc(APP.t("tlComposers"))}</div><div class="chips">${comps}</div></div>`;
  html += `<div class="rc-sec"><div class="rc-lbl">${esc(APP.t("tlInstruments"))}</div><div class="chips">${insts}</div></div>`;
  if (e.works && e.works.length){
    const works = e.works.map(wk => `<span class="chip chip-c">${esc(wk)}</span>`).join("");
    html += `<div class="rc-sec"><div class="rc-lbl">${esc(APP.t("tlWorks"))}</div><div class="chips">${works}</div></div>`;
  }
  const kz = APP.pick(e, "kazakh");
  if (kz) html += `<div class="rc-sec kz-note"><div class="rc-lbl">★ ${esc(APP.t("tlKazakh"))}</div><p>${esc(kz)}</p></div>`;
  const box = $("#tlCard"); box.innerHTML = html; box.scrollTop = 0;
  $("#tlListen").addEventListener("click", () => playDemo(e));
}

function playDemo(e){
  if (!window.AUDIO) return;
  AUDIO.ensure();
  AUDIO.playKey(e.audio, () => AUDIO.playMotif(e.motif || [[0,1]], 60, 112), e.audioStart || 0);
}

function relang(){
  const band = $("#tlBand");
  if (band) document.querySelectorAll(".tl-era").forEach(b => {
    const e = ERAS.find(x => x.id === b.dataset.id);
    b.querySelector(".tl-name").textContent = APP.pick(e, "name");
  });
  if (current) select(current);
  else { const c = $("#tlCard"); if (c) c.innerHTML = `<div class="card-empty">${esc(APP.t("tlHint"))}</div>`; }
}
window.APP && window.APP.onLang(relang);

return { init, relang };
})();
