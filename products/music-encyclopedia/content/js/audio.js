/* ============================================================
   Звуковой движок (Web Audio для синтеза + нативный <audio> для клипов).
   • Точный синтез нот/интервалов/аккордов для тренажёра (Web Audio).
   • Вшитые клипы (инструменты/эпохи) играем через НАТИВНЫЙ <audio> — медиа-конвейер
     устройства, без треска/лагов Web Audio decodeAudioData на Android WebView.
   • Фрагмент ~13 c с фейдами (по громкости). Любой новый звук СНАЧАЛА стопает предыдущий.
   • AudioContext с latencyHint:'playback' (крупнее буфер → меньше underrun/треска).
   ============================================================ */
(function () {
"use strict";
let ctx = null, master = null, voices = [];
let clipEl = null, clipTimer = null, fadeTimer = null;
const CLIP_SEC = 13;

function ensure() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    ctx = new AC({ latencyHint: "playback" });
    master = ctx.createGain(); master.gain.value = 0.7;
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -10; comp.knee.value = 10; comp.ratio.value = 12;
    comp.attack.value = 0.004; comp.release.value = 0.25;   // лимитер против клиппинга
    master.connect(comp); comp.connect(ctx.destination);
  }
  if (ctx.state === "suspended") ctx.resume();
  return ctx;
}
const mtof = m => 440 * Math.pow(2, (m - 69) / 12);

function stopSynth() {
  if (!ctx) return;
  const t = ctx.currentTime;
  voices.forEach(v => {
    try { v.gain.gain.cancelScheduledValues(t); v.gain.gain.setValueAtTime(0.0001, t); } catch (e) {}
    v.nodes.forEach(n => { try { n.stop(Math.max(n._t || t, t) + 0.05); } catch (e) {} });
  });
  voices = [];
}
function stopClip() {
  if (clipTimer) { clearTimeout(clipTimer); clipTimer = null; }
  if (fadeTimer) { clearInterval(fadeTimer); fadeTimer = null; }
  if (clipEl) { try { clipEl.pause(); } catch (e) {} clipEl.onerror = null; clipEl.onended = null; clipEl = null; }
}
function stopAll() { stopSynth(); stopClip(); }

/* нота с 2 гармониками (легче для аудио-потока → меньше underrun на слабых планшетах) */
function _note(midi, dur, when, gain) {
  const t = when || ctx.currentTime, f = mtof(midi);
  const g = ctx.createGain(); g.connect(master);
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(gain, t + 0.014);
  g.gain.exponentialRampToValueAtTime(gain * 0.55, t + 0.20);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  const nodes = [];
  [[1, 1], [2, 0.35]].forEach(([h, hg]) => {
    const o = ctx.createOscillator(); o.type = "sine"; o.frequency.value = f * h; o._t = t;
    const pg = ctx.createGain(); pg.gain.value = hg;
    o.connect(pg); pg.connect(g);
    o.start(t); o.stop(t + dur + 0.05); nodes.push(o);
  });
  voices.push({ nodes, gain: g });
}
function playNote(midi, dur, when, gain) { ensure(); stopAll(); _note(midi, dur || 0.9, when || ctx.currentTime, gain == null ? 0.2 : gain); }
function playInterval(rootMidi, semi, melodic) {
  ensure(); stopAll(); const t0 = ctx.currentTime;
  if (melodic === false) { _note(rootMidi, 1.4, t0, 0.16); _note(rootMidi + semi, 1.4, t0, 0.16); }
  else { _note(rootMidi, 0.7, t0, 0.20); _note(rootMidi + semi, 0.9, t0 + 0.62, 0.20); }
}
function playChord(rootMidi, semis, dur) {
  ensure(); stopAll(); const t = ctx.currentTime;
  semis.forEach(s => _note(rootMidi + s, dur || 1.5, t, 0.13));
}
function playMotif(motif, base, bpm) {
  ensure(); stopAll();
  base = base == null ? 60 : base; bpm = bpm || 110;
  const beat = 60 / bpm; let t = ctx.currentTime + 0.03;
  motif.forEach(([n, d]) => { _note(base + n, d * beat * 1.05, t, 0.2); t += d * beat; });
}

const SCALES = {
  major:[0,2,4,5,7,9,11,12], minor:[0,2,3,5,7,8,10,12], pentatonic:[0,2,4,7,9,12],
  blues:[0,3,5,6,7,10,12], phrygian:[0,1,3,5,7,8,10,12], maqam:[0,1,4,5,7,8,11,12],
  raga:[0,1,4,5,7,8,11,12], wholetone:[0,2,4,6,8,10,12], japanese:[0,1,5,7,10,12],
  slendro:[0,2,5,7,9,12], drone:[0,0,12,7,0,0]
};
function playScale(scaleName, root) {
  ensure(); stopAll(); root = root == null ? 60 : root;
  if (scaleName === "drone") { const t = ctx.currentTime; _note(root - 12, 2.2, t, 0.18); _note(root - 5, 2.0, t + 0.1, 0.06); return; }
  const sc = SCALES[scaleName] || SCALES.major;
  const seq = sc.concat(sc.slice(0, -1).reverse());
  const beat = 60 / 150; let t = ctx.currentTime + 0.03;
  seq.forEach(n => { _note(root + n, beat * 1.1, t, 0.18); t += beat; });
}

/* короткий фрагмент вшитого клипа через нативный <audio>: mp3 → ogg → wav → fallback() */
function playKey(key, fallback, offset) {
  ensure(); stopAll(); offset = offset || 0;
  const a = new Audio(); clipEl = a; a.preload = "auto"; a.volume = 0;
  const exts = ["mp3", "ogg", "wav"]; let stage = 0;
  function nextExt() {
    if (clipEl !== a) return;
    if (stage >= exts.length) { stopClip(); if (fallback) fallback(); return; }
    a.src = "audio/" + key + "." + exts[stage++];
    const p = a.play(); if (p && p.catch) p.catch(function(){});  // gesture/transient — не считаем «нет файла»
  }
  a.onerror = nextExt;                                            // 404/декод-ошибка → следующий формат → синтез
  a.onloadedmetadata = function () { try { if (offset && offset < a.duration - 1) a.currentTime = offset; } catch (e) {} };
  a.onended = function () { if (clipEl === a) stopClip(); };
  nextExt();
  const FADE = 1.5, start = Date.now();
  fadeTimer = setInterval(function () {
    if (clipEl !== a) { clearInterval(fadeTimer); return; }
    const el = (Date.now() - start) / 1000; let v;
    if (el < FADE) v = el / FADE; else if (el > CLIP_SEC - FADE) v = (CLIP_SEC - el) / FADE; else v = 1;
    a.volume = Math.min(1, Math.max(0, v));
  }, 60);
  clipTimer = setTimeout(stopClip, CLIP_SEC * 1000);
}

window.AUDIO = { ensure, stopAll, mtof, playNote, playInterval, playChord, playMotif, playScale, playKey, SCALES };
})();
