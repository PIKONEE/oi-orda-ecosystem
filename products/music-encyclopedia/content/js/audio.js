/* ============================================================
   Звуковой движок (Web Audio).
   • Точный синтез нот/интервалов/аккордов для тренажёра.
   • Проигрывание вшитых клипов — ТОЛЬКО короткий фрагмент (~13 c) с фейдами.
   • Любой новый звук СНАЧАЛА останавливает предыдущий (stopAll).
   AudioContext создаётся лениво — по первому жесту пользователя.
   ============================================================ */
(function () {
"use strict";
let ctx = null, master = null;
const buffers = {};      // key -> AudioBuffer
const tried = {};        // key -> true
let voices = [];         // активные голоса: {nodes:[...], gain}
const CLIP_SEC = 13;     // максимум воспроизведения вшитого фрагмента

function ensure() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    ctx = new AC();
    master = ctx.createGain(); master.gain.value = 0.7;
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -12; comp.knee.value = 8; comp.ratio.value = 12;
    comp.attack.value = 0.003; comp.release.value = 0.25;   // лимитер — против клиппинга/треска на аккордах
    master.connect(comp); comp.connect(ctx.destination);
  }
  if (ctx.state === "suspended") ctx.resume();
  return ctx;
}
const mtof = m => 440 * Math.pow(2, (m - 69) / 12);

/* остановить ВСЁ, что сейчас звучит (мгновенный фейд) */
function stopAll() {
  if (!ctx) return;
  const t = ctx.currentTime;
  voices.forEach(v => {
    try { v.gain.gain.cancelScheduledValues(t); v.gain.gain.setValueAtTime(0.0001, t); } catch (e) {}
    v.nodes.forEach(n => { try { n.stop(Math.max(n._t || t, t) + 0.05); } catch (e) {} });
  });
  voices = [];
}

/* внутренняя нота (без stopAll) — для последовательностей/аккордов */
function _note(midi, dur, when, gain) {
  const t = when || ctx.currentTime, f = mtof(midi);
  const g = ctx.createGain(); g.connect(master);
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(gain, t + 0.012);
  g.gain.exponentialRampToValueAtTime(gain * 0.55, t + 0.20);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  const nodes = [];
  [[1, 1], [2, 0.42], [3, 0.20], [4, 0.10]].forEach(([h, hg]) => {
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
  semis.forEach(s => _note(rootMidi + s, dur || 1.5, t, 0.14));
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

/* короткий фрагмент вшитого клипа content/audio/<key>.(mp3|ogg|wav) с offset (сек);
   иначе fallback() */
function playKey(key, fallback, offset) {
  ensure(); stopAll(); offset = offset || 0;
  if (buffers[key]) { startClip(buffers[key], offset); return; }
  if (tried[key]) { if (fallback) fallback(); return; }
  tried[key] = true;
  const exts = ["mp3", "ogg", "wav"]; let i = 0;
  (function next() {
    if (i >= exts.length) { if (fallback) fallback(); return; }
    fetch("audio/" + key + "." + exts[i++], { cache: "force-cache" })
      .then(r => r.ok ? r.arrayBuffer() : Promise.reject())
      .then(buf => ctx.decodeAudioData(buf))
      .then(ab => { buffers[key] = ab; startClip(ab, offset); })
      .catch(next);
  })();
}
function startClip(ab, offset) {
  offset = offset || 0;
  if (offset >= ab.duration - 1) offset = 0;    // старт за пределами файла → с начала
  const t = ctx.currentTime, dur = Math.min(CLIP_SEC, ab.duration - offset);
  const fade = Math.min(1.5, dur / 2 - 0.05);   // фейд-ин и фейд-аут по 1.5 c
  const src = ctx.createBufferSource(); src.buffer = ab; src._t = t;
  const g = ctx.createGain(); src.connect(g); g.connect(master);
  g.gain.setValueAtTime(0.0001, t);
  g.gain.linearRampToValueAtTime(0.95, t + fade);          // плавное нарастание в начале
  g.gain.setValueAtTime(0.95, t + dur - fade);
  g.gain.linearRampToValueAtTime(0.0001, t + dur);         // плавное затухание в конце
  src.start(t, offset, dur + 0.1); src.stop(t + dur + 0.15);
  voices.push({ nodes: [src], gain: g });
}

window.AUDIO = { ensure, stopAll, mtof, playNote, playInterval, playChord, playMotif, playScale, playKey, SCALES };
})();
