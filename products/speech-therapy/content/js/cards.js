/* ============================================================
   Карточки звуков. Группы по звуку, листание (свайп/стрелки), авто-озвучка.
   Картинка — OpenMoji (images/<code>.svg), фолбэк — сам эмодзи.
   ============================================================ */
window.Cards = (function () {
"use strict";
const $ = s => document.querySelector(s);
const esc = s => String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let gi = 0, ci = 0;
const data = () => (APP.lang === "kz" ? window.SOUNDS_KZ : window.SOUNDS_RU) || [];

function init(){
  $("#cardPrev").addEventListener("click", () => step(-1));
  $("#cardNext").addEventListener("click", () => step(1));
  // свайп
  const stage = $("#cardStage"); let x0 = null;
  stage.addEventListener("pointerdown", e => { x0 = e.clientX; });
  stage.addEventListener("pointerup", e => {
    if (x0 == null) return; const dx = e.clientX - x0; x0 = null;
    if (Math.abs(dx) > 45) step(dx < 0 ? 1 : -1);
  });
  render();
}
function renderChips(){
  const d = data();
  $("#cardChips").innerHTML = d.map((g, i) =>
    `<button class="chip ${i===gi?"active":""}" data-g="${i}" style="--c:${g.color}">${esc(g.sound)}</button>`).join("");
  $("#cardChips").onclick = e => { const b = e.target.closest("[data-g]"); if (!b) return; gi = +b.dataset.g; ci = 0; render(); };
}
function render(){
  const d = data(); if (!d.length) return;
  if (gi >= d.length) gi = 0;
  const g = d[gi], card = g.cards[ci];
  renderChips();
  const code = window.SP ? SP.emojiCode(card.emoji) : "";
  const posLbl = APP.t("pos" + card.pos.toUpperCase());
  $("#cardMain").style.setProperty("--c", g.color);
  $("#cardMain").innerHTML =
    `<div class="card-letter" style="background:${g.color}">${esc(g.sound)}</div>` +
    `<div class="card-pic"><img src="images/${code}.svg" alt="" ` +
      `onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'emoji-fallback',textContent:'${card.emoji}'}))"></div>` +
    `<div class="card-word">${esc(card.word)}</div>` +
    `<div class="card-pos">${esc(posLbl)}</div>` +
    `<button class="big-listen" id="cardPlay">${esc(APP.t("listen"))}</button>`;
  $("#cardPlay").addEventListener("click", () => SP.playWord(card.word, APP.lang));
  // точки-индикатор
  $("#cardDots").innerHTML = g.cards.map((_, i) => `<span class="${i===ci?"on":""}"></span>`).join("");
  if (window.SP) SP.playWord(card.word, APP.lang);   // авто-озвучка при показе
}
function step(dir){
  const g = data()[gi]; if (!g) return;
  ci = (ci + dir + g.cards.length) % g.cards.length;
  render();
}
function relang(){ gi = 0; ci = 0; render(); }
window.APP && window.APP.onLang(() => { if (document.querySelector("#view-cards.active")) relang(); });
return { init, relang };
})();
