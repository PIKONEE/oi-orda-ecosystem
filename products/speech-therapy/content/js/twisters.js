/* ============================================================
   Скороговорки с подсветкой целевого звука. Чтение вслух; кнопка ▶ — образец (TTS).
   ============================================================ */
window.Twisters = (function () {
"use strict";
const $ = s => document.querySelector(s);
const esc = c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c] || c);
const data = () => (APP.lang === "kz" ? window.TW_KZ : window.TW_RU) || [];
let idx = 0;

function init(){
  $("#twPlay").addEventListener("click", () => { const t = data()[idx]; if (t && window.SP) SP.speak(t.text, APP.lang); });
  render();
}
function highlight(text, sounds){
  const set = new Set(sounds.map(s => s.toLowerCase()));
  let out = "";
  for (const ch of text){
    if (set.has(ch.toLowerCase())) out += `<span class="hl">${esc(ch)}</span>`;
    else out += esc(ch);
  }
  return out;
}
function render(){
  const d = data(); if (!d.length) return; if (idx >= d.length) idx = 0;
  $("#twList").innerHTML = d.map((t, i) =>
    `<button class="chip ${i===idx?"active":""}" data-i="${i}">${i+1}</button>`).join("");
  $("#twList").onclick = e => { const b = e.target.closest("[data-i]"); if (!b) return; idx = +b.dataset.i; render(); };
  const t = d[idx];
  $("#twText").innerHTML = highlight(t.text, t.sounds);
  $("#twPlay").textContent = APP.t("listen");
}
function relang(){ idx = 0; render(); }
window.APP && window.APP.onLang(() => { if (document.querySelector("#view-twisters.active")) relang(); });
return { init, relang };
})();
