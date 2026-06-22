/* ============================================================
   Тренажёр музыкального слуха. Режимы: нота / интервал / аккорд.
   Звук — точный синтез (js/audio.js). Статистика — в localStorage.
   ============================================================ */
window.MEar = (function () {
"use strict";
const EAR = window.EAR || {};
const $ = s => document.querySelector(s);
const esc = s => String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const rnd = a => a[Math.floor(Math.random()*a.length)];
const nameOf = o => APP.lang==="kz" ? o.kz : o.ru;

let mode = "note", level = "easy", q = null, answered = false;
const STATS_KEY = "me_ear_stats";
function loadStats(){ try { return JSON.parse(localStorage.getItem(STATS_KEY)) || {}; } catch(e){ return {}; } }
function saveStats(s){ try { localStorage.setItem(STATS_KEY, JSON.stringify(s)); } catch(e){} }
function st(m){ const s = loadStats(); return s[m] || {right:0,wrong:0,streak:0}; }

function init(){
  renderControls();
  $("#earPlay").addEventListener("click", () => { if (!q) newQuestion(); else play(); });
  $("#earReplay").addEventListener("click", play);
  $("#earOptions").addEventListener("click", onOption);
  reset(false);
  renderStats();
}

function renderControls(){
  $("#earModes").innerHTML = [["note","earModeNote"],["interval","earModeInterval"],["chord","earModeChord"]]
    .map(([m,k]) => `<button data-mode="${m}" class="${m===mode?"active":""}">${esc(APP.t(k))}</button>`).join("");
  $("#earLevels").innerHTML = [["easy","earLevelEasy"],["hard","earLevelHard"]]
    .map(([l,k]) => `<button data-level="${l}" class="${l===level?"active":""}">${esc(APP.t(k))}</button>`).join("");
  $("#earModes").onclick = e => { const b=e.target.closest("[data-mode]"); if(!b)return; mode=b.dataset.mode; renderControls(); reset(true); renderStats(); };
  $("#earLevels").onclick = e => { const b=e.target.closest("[data-level]"); if(!b)return; level=b.dataset.level; renderControls(); reset(true); };
}

function reset(clearQ){
  q = null; answered = false;
  $("#earAsk").textContent = "";
  $("#earOptions").innerHTML = "";
  $("#earFeedback").innerHTML = "";
  $("#earFeedback").className = "ear-feedback";
  $("#earPlay").textContent = "▶";
  $("#earReplay").style.visibility = "hidden";
  if (!clearQ) $("#earAsk").textContent = APP.t("earStart");
}

/* варианты ответа текущего режима/уровня */
function options(){
  if (mode === "note") return EAR.noteLevels[level].map(l => EAR.notes.find(n => n.letter === l));
  if (mode === "interval") return EAR.intervalLevels[level].map(s => EAR.intervals.find(i => i.semi === s));
  return EAR.chordLevels[level].map(id => EAR.chords.find(c => c.id === id));
}

function newQuestion(){
  answered = false;
  const opts = options();
  if (mode === "note"){
    const target = rnd(opts);
    q = { kind:"note", target, midi: target.midi };
    $("#earAsk").textContent = APP.t("earAskNote");
  } else if (mode === "interval"){
    const target = rnd(opts), root = 57 + Math.floor(Math.random()*6); // A3..D4
    q = { kind:"interval", target, root };
    $("#earAsk").textContent = APP.t("earAskInterval");
  } else {
    const target = rnd(opts), root = 55 + Math.floor(Math.random()*8); // G3..D4
    q = { kind:"chord", target, root };
    $("#earAsk").textContent = APP.t("earAskChord");
  }
  renderOptions(opts);
  $("#earPlay").textContent = "▶";
  $("#earReplay").style.visibility = "visible";
  $("#earFeedback").innerHTML = ""; $("#earFeedback").className = "ear-feedback";
  play();
}

function renderOptions(opts){
  $("#earOptions").innerHTML = opts.map(o => {
    const key = mode==="note" ? o.letter : (mode==="interval" ? o.semi : o.id);
    const label = mode==="interval" ? `${nameOf(o)} <small>(${esc(o.short)})</small>` : esc(nameOf(o));
    return `<button class="opt" data-key="${esc(String(key))}">${label}</button>`;
  }).join("");
}

function play(){
  if (!window.AUDIO || !q) return;
  AUDIO.ensure();
  if (q.kind === "note") AUDIO.playNote(q.midi, 1.1, 0, 0.22);
  else if (q.kind === "interval") AUDIO.playInterval(q.root, q.target.semi, true);
  else AUDIO.playChord(q.root, q.target.semis, 1.6);
}

function onOption(ev){
  const b = ev.target.closest("[data-key]"); if (!b || answered || !q) return;
  answered = true;
  const key = b.dataset.key;
  const correctKey = mode==="note" ? q.target.letter : (mode==="interval" ? String(q.target.semi) : q.target.id);
  const ok = key === correctKey;
  // отметить кнопки
  document.querySelectorAll("#earOptions .opt").forEach(x => {
    if (x.dataset.key === correctKey) x.classList.add("ok");
    else if (x === b) x.classList.add("bad");
    x.disabled = true;
  });
  // статистика
  const s = loadStats(); const m = s[mode] || {right:0,wrong:0,streak:0};
  if (ok){ m.right++; m.streak++; } else { m.wrong++; m.streak = 0; }
  s[mode] = m; saveStats(s); renderStats();
  // фидбэк + кнопка «дальше»
  const fb = $("#earFeedback");
  fb.className = "ear-feedback " + (ok ? "good" : "err");
  fb.innerHTML = (ok ? "✓ " + APP.t("earCorrect")
    : "✗ " + APP.t("earWrong") + " <b>" + esc(nameOf(q.target)) + "</b>") +
    ` <button class="next" id="earNext">${esc(APP.t("earNext"))}</button>`;
  $("#earNext").addEventListener("click", newQuestion);
}

function renderStats(){
  const m = st(mode);
  const total = m.right + m.wrong;
  const acc = total ? Math.round(m.right/total*100) : 0;
  $("#earStats").innerHTML =
    `<div class="stat"><span>${m.right}</span><label>${esc(APP.t("earRight"))}</label></div>` +
    `<div class="stat"><span>${m.wrong}</span><label>${esc(APP.t("earErrors"))}</label></div>` +
    `<div class="stat"><span>${acc}%</span><label>${esc(APP.t("earAccuracy"))}</label></div>` +
    `<div class="stat"><span>${m.streak}</span><label>${esc(APP.t("earStreak"))}</label></div>` +
    `<button class="ear-reset" id="earReset">${esc(APP.t("earReset"))}</button>`;
  $("#earReset").addEventListener("click", () => {
    const s = loadStats(); s[mode] = {right:0,wrong:0,streak:0}; saveStats(s); renderStats();
  });
}

function relang(){
  renderControls();
  $("#earPlay").textContent = "▶";
  $("#earReplay").textContent = "↻";
  if (q && !answered){ $("#earAsk").textContent = q.kind==="note"?APP.t("earAskNote"):q.kind==="interval"?APP.t("earAskInterval"):APP.t("earAskChord");
    renderOptions(options()); } else if (q && answered){ /* перерисуем варианты с метками не нужно */ }
  if (!q) $("#earAsk").textContent = APP.t("earStart");
  renderStats();
}
window.APP && window.APP.onLang(relang);

return { init, relang };
})();
