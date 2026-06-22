/* ============================================================
   Звук и помощники. playWord: вшитый клип audio/<lang>_<slug>.(mp3|ogg)
   → если нет, говорит через системный TTS (speechSynthesis). Стоп-предыдущего.
   Анти-клик: короткий fade-in при старте и fade-out при остановке (убирает треск).
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

let ctx = null, current = null, curGain = null;
const buffers = {}, tried = {};
function ensure(){
  if (!ctx){ const AC = window.AudioContext || window.webkitAudioContext; if (AC) ctx = new AC(); }
  if (ctx && ctx.state === "suspended") ctx.resume();
  return ctx;
}
function stopAll(){
  try {
    if (current){
      current.onended = null;
      if (curGain && ctx){
        const t = ctx.currentTime;
        curGain.gain.cancelScheduledValues(t);
        curGain.gain.setValueAtTime(Math.max(curGain.gain.value || 0.0001, 0.0001), t);
        curGain.gain.exponentialRampToValueAtTime(0.0001, t + 0.05);  // fade-out (анти-клик)
        current.stop(t + 0.06);
      } else {
        current.stop(0);
      }
    }
  } catch (e) {}
  current = null; curGain = null;
  try { window.speechSynthesis && speechSynthesis.cancel(); } catch (e) {}
}
function speak(word, lang){
  try {
    const u = new SpeechSynthesisUtterance(word);
    u.lang = lang === "kz" ? "kk-KZ" : "ru-RU"; u.rate = 0.85;
    speechSynthesis.cancel(); speechSynthesis.speak(u);
  } catch (e) {}
}
function playBuf(ab){
  const c = ensure(); if (!c) return;
  const s = c.createBufferSource(); s.buffer = ab;
  const g = c.createGain();
  const t = c.currentTime;
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(1, t + 0.03);   // fade-in (анти-клик)
  s.connect(g); g.connect(c.destination);
  s.onended = () => { if (current === s){ current = null; curGain = null; } };
  s.start();
  current = s; curGain = g;
}
function playWord(word, lang, slug){
  stopAll();
  slug = slug || translit(word);
  const key = lang + "_" + slug;
  if (!ensure()){ speak(word, lang); return; }            // нет Web Audio → системный TTS
  if (buffers[key]){ playBuf(buffers[key]); return; }
  if (tried[key]){ speak(word, lang); return; }           // уже знаем, что файла нет
  tried[key] = true;
  const exts = ["mp3", "ogg"]; let i = 0;
  (function next(){
    if (i >= exts.length){ speak(word, lang); return; }   // файла нет → системный TTS
    fetch("audio/" + key + "." + exts[i++], { cache: "force-cache" })
      .then(r => r.ok ? r.arrayBuffer() : Promise.reject())
      .then(b => ctx.decodeAudioData(b))
      .then(ab => { buffers[key] = ab; playBuf(ab); })
      .catch(next);
  })();
}
/* короткий «дзинь» для верного/неверного ответа */
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
