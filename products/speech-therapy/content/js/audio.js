/* ============================================================
   Звук логопеда. Слова озвучиваются НАТИВНЫМ <audio> (медиа-конвейер устройства) —
   это убирает треск/лаги, которые даёт Web Audio decodeAudioData на Android WebView.
   Нет файла → системный TTS (speechSynthesis). Всегда стоп-предыдущего.
   ding() — короткий сигнал верного/неверного (Web Audio, латентность 'playback').
   translit() ДОЛЖЕН совпадать с tools/fetch_speech.py. emojiCode() → имя OpenMoji.
   ============================================================ */
window.SP = (function () {
"use strict";
const TR = {
  "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i",
  "й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t",
  "у":"u","ф":"f","х":"h","ц":"c","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"",
  "э":"e","ю":"yu","я":"ya"," ":"_","-":"_",
  "ә":"ae","ғ":"gh","қ":"q","ң":"ng","ө":"oe","ұ":"uu","ү":"ue","һ":"hh","і":"ii"
};
function translit(w){
  return String(w).toLowerCase().split("").map(c => TR[c] != null ? TR[c] : "").join("")
    .replace(/_+/g, "_").replace(/^_|_$/g, "");
}
function emojiCode(e){
  return Array.from(e).map(c => c.codePointAt(0)).filter(cp => cp !== 0xFE0F)
    .map(cp => cp.toString(16).toUpperCase()).join("-");
}

let cur = null;       // текущий HTMLAudioElement
let actx = null;      // AudioContext только для ding()
function ensure(){
  if (!actx){ const AC = window.AudioContext || window.webkitAudioContext;
    if (AC) actx = new AC({ latencyHint: "playback" }); }
  if (actx && actx.state === "suspended") actx.resume();
  return actx;
}
function stopAll(){
  if (cur){ try { cur.pause(); } catch (e) {} cur.onerror = null; cur.onended = null; cur = null; }
  try { window.speechSynthesis && speechSynthesis.cancel(); } catch (e) {}
}
function speak(word, lang){
  try {
    const u = new SpeechSynthesisUtterance(word);
    u.lang = lang === "kz" ? "kk-KZ" : "ru-RU"; u.rate = 0.85;
    speechSynthesis.cancel(); speechSynthesis.speak(u);
  } catch (e) {}
}
/* Слово через нативный <audio>: mp3 → ogg → системный TTS */
function playWord(word, lang, slug){
  stopAll();
  slug = slug || translit(word);
  const key = lang + "_" + slug;
  const a = new Audio(); cur = a; a.preload = "auto";
  let stage = 0;  // 0=mp3 → 1=ogg → 2=tts
  function fail(){
    if (cur !== a || stage >= 2) return;
    if (stage === 0){ stage = 1; a.src = "audio/" + key + ".ogg"; const p = a.play(); if (p && p.catch) p.catch(fail); }
    else { stage = 2; speak(word, lang); }
  }
  a.onerror = fail;
  a.onended = function(){ if (cur === a) cur = null; };
  a.src = "audio/" + key + ".mp3";
  const p = a.play();
  if (p && p.catch) p.catch(fail);
}
/* короткий «дзинь» верного/неверного ответа */
function ding(ok){
  const c = ensure(); if (!c) return;
  const t = c.currentTime, g = c.createGain(); g.connect(c.destination);
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.18, t + 0.02);
  g.gain.exponentialRampToValueAtTime(0.0001, t + 0.4);
  const o = c.createOscillator(); o.type = "sine"; o.connect(g);
  if (ok){ o.frequency.setValueAtTime(660, t); o.frequency.exponentialRampToValueAtTime(990, t + 0.18); }
  else  { o.frequency.setValueAtTime(330, t); o.frequency.exponentialRampToValueAtTime(220, t + 0.25); }
  o.start(t); o.stop(t + 0.45);
}
return { translit, emojiCode, playWord, speak, stopAll, ensure, ding };
})();
