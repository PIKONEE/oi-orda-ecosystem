/* ============================================================
   Игра «Определи звук». Звучит слово → выбрать, какой из двух звуков в нём.
   Статистика в localStorage (sp_game_stats).
   ============================================================ */
window.Game = (function () {
"use strict";
const $ = s => document.querySelector(s);
const esc = s => String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const rnd = a => a[Math.floor(Math.random()*a.length)];
const data = () => (APP.lang === "kz" ? window.GAME_KZ : window.GAME_RU) || [];
let pi = 0, q = null, answered = false;
const KEY = "sp_game_stats";
const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {right:0,wrong:0,streak:0}; } catch(e){ return {right:0,wrong:0,streak:0}; } };
const save = s => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch(e){} };

function init(){
  $("#gamePlay").addEventListener("click", () => { if (q) SP.playWord(q.word, APP.lang); });
  renderPairs(); renderStats(); newQuestion();
}
function renderPairs(){
  const d = data();
  $("#gamePairs").innerHTML = d.map((p, i) =>
    `<button class="chip ${i===pi?"active":""}" data-p="${i}">${esc(p.a)} / ${esc(p.b)}</button>`).join("");
  $("#gamePairs").onclick = e => { const b = e.target.closest("[data-p]"); if (!b) return; pi = +b.dataset.p; renderPairs(); newQuestion(); };
}
function newQuestion(){
  const d = data(); if (!d.length) return; if (pi >= d.length) pi = 0;
  const pair = d[pi]; q = rnd(pair.items); answered = false;
  $("#gameAsk").textContent = APP.t("gameAsk");
  $("#gameFb").textContent = ""; $("#gameFb").className = "game-fb";
  $("#gameOptions").innerHTML = [pair.a, pair.b].map(s =>
    `<button class="opt-sound" data-s="${esc(s)}">${esc(s)}</button>`).join("");
  $("#gameOptions").onclick = onAnswer;
  $("#gamePlay").textContent = "▶";
  if (window.SP) SP.playWord(q.word, APP.lang);
}
function onAnswer(e){
  const b = e.target.closest("[data-s]"); if (!b || answered || !q) return;
  answered = true;
  const ok = b.dataset.s === q.ans;
  document.querySelectorAll("#gameOptions .opt-sound").forEach(x => {
    if (x.dataset.s === q.ans) x.classList.add("ok"); else if (x === b) x.classList.add("bad");
    x.disabled = true;
  });
  const s = load(); if (ok){ s.right++; s.streak++; } else { s.wrong++; s.streak = 0; } save(s); renderStats();
  if (window.SP) SP.ding(ok);
  const fb = $("#gameFb"); fb.className = "game-fb " + (ok ? "good" : "err");
  fb.innerHTML = (ok ? "⭐ " + APP.t("correct") : "🙂 " + APP.t("wrong") + " <b>" + esc(q.ans) + "</b>") +
    ` <button class="next-btn" id="gameNext">${esc(APP.t("next"))}</button>`;
  $("#gameNext").addEventListener("click", newQuestion);
}
function renderStats(){
  const s = load();
  $("#gameStats").innerHTML =
    `<div class="st"><span>${s.right}</span><label>${esc(APP.t("right"))}</label></div>` +
    `<div class="st"><span>${s.wrong}</span><label>${esc(APP.t("errors"))}</label></div>` +
    `<div class="st"><span>${s.streak}</span><label>${esc(APP.t("streak"))}</label></div>` +
    `<button class="reset-btn" id="gameReset">${esc(APP.t("reset"))}</button>`;
  $("#gameReset").addEventListener("click", () => { save({right:0,wrong:0,streak:0}); renderStats(); });
}
function relang(){ pi = 0; renderPairs(); renderStats(); newQuestion(); }
window.APP && window.APP.onLang(() => { if (document.querySelector("#view-game.active")) relang(); });
return { init, relang };
})();
