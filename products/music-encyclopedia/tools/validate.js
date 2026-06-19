/* Валидатор данных музыкальной энциклопедии. Запуск: node tools/validate.js
   Проверяет regions / eras / eartrainer / i18n; считает покрытие аудио. */
const fs = require("fs"), path = require("path"), vm = require("vm");
const dataDir = path.join(__dirname, "..", "content", "data");
const locDir = path.join(__dirname, "..", "content", "locales");
const audioDir = path.join(__dirname, "..", "content", "audio");
const sandbox = { window: {} }; vm.createContext(sandbox);
for (const f of ["regions.js", "eras_music.js", "eartrainer.js", "credits.js"])
  vm.runInContext(fs.readFileSync(path.join(dataDir, f), "utf8"), sandbox, { filename:f });
vm.runInContext(fs.readFileSync(path.join(locDir, "i18n.js"), "utf8"), sandbox, { filename:"i18n.js" });

const REGIONS = sandbox.window.REGIONS || [], ERAS = sandbox.window.MUSIC_ERAS || [];
const EAR = sandbox.window.EAR || {}, I18N = sandbox.window.I18N || {};
const SCALES = ["major","minor","pentatonic","blues","phrygian","maqam","raga","wholetone","japanese","slendro","drone"];
let errors = [], warns = [], seen = new Set();
const audioRef = new Set();
const need = (cond, msg) => { if (!cond) errors.push(msg); };

REGIONS.forEach((r, i) => {
  const w = `region #${i}` + (r && r.id ? ` (${r.id})` : "");
  if (!r || typeof r !== "object") return errors.push(`${w}: не объект`);
  need(r.id, `${w}: нет id`);
  if (r.id){ if (seen.has("r:"+r.id)) errors.push(`${w}: дубль id`); seen.add("r:"+r.id); }
  need(typeof r.lat === "number" && r.lat>=-60 && r.lat<=75, `${w}: lat вне диапазона (${r.lat})`);
  need(typeof r.lng === "number" && r.lng>=-180 && r.lng<=180, `${w}: lng вне диапазона (${r.lng})`);
  ["nameRu","nameKz","rhythmRu","rhythmKz","descRu","descKz"].forEach(f => need(r[f] && String(r[f]).trim(), `${w}: пустое ${f}`));
  need(Array.isArray(r.instrRu) && r.instrRu.length, `${w}: пустой instrRu`);
  need(Array.isArray(r.instrKz) && r.instrKz.length, `${w}: пустой instrKz`);
  if (r.scale && !SCALES.includes(r.scale)) warns.push(`${w}: неизвестный scale "${r.scale}"`);
  if (r.audio) audioRef.add(r.audio);
  (r.extra||[]).forEach((e,j) => ["titleRu","titleKz","textRu","textKz"].forEach(f =>
    need(e[f] && String(e[f]).trim(), `${w}.extra[${j}]: пустое ${f}`)));
});

ERAS.forEach((e, i) => {
  const w = `era #${i}` + (e && e.id ? ` (${e.id})` : "");
  if (!e || typeof e !== "object") return errors.push(`${w}: не объект`);
  if (e.id){ if (seen.has("e:"+e.id)) errors.push(`${w}: дубль id`); seen.add("e:"+e.id); }
  ["from","to"].forEach(f => need(typeof e[f] === "number", `${w}: ${f} не число`));
  ["nameRu","nameKz","descRu","descKz"].forEach(f => need(e[f] && String(e[f]).trim(), `${w}: пустое ${f}`));
  need(Array.isArray(e.instrRu) && e.instrRu.length, `${w}: пустой instrRu`);
  need(Array.isArray(e.traits) && e.traits.length, `${w}: пустой traits`);
  (e.traits||[]).forEach((t,j) => need(t.ru && t.kz, `${w}.traits[${j}]: нет ru/kz`));
  need(Array.isArray(e.composers) && e.composers.length, `${w}: пустой composers`);
  need(Array.isArray(e.motif) && e.motif.length, `${w}: пустой motif`);
  if (e.audio) audioRef.add(e.audio);
});

// тренажёр
["notes","intervals","chords","noteLevels","intervalLevels","chordLevels"].forEach(k =>
  need(EAR[k], `EAR: нет ${k}`));
if (EAR.notes) need(EAR.notes.length === 12, `EAR.notes: ожидалось 12, есть ${EAR.notes.length}`);

// i18n: одинаковый набор ключей ru/kz
if (I18N.ru && I18N.kz){
  const rk = Object.keys(I18N.ru), kk = new Set(Object.keys(I18N.kz));
  rk.forEach(k => { if (!kk.has(k)) errors.push(`i18n: ключ "${k}" есть в ru, нет в kz`); });
  Object.keys(I18N.kz).forEach(k => { if (!I18N.ru[k] && I18N.ru[k] !== "") warns.push(`i18n: ключ "${k}" есть в kz, нет в ru`); });
}

// покрытие аудио (отсутствие = синт-фолбэк, это норма)
let present = 0;
audioRef.forEach(k => { if (["mp3","ogg","wav"].some(e => fs.existsSync(path.join(audioDir, k + "." + e)))) present++; });

const line = "─".repeat(56);
console.log(line);
console.log("РЕГИОНОВ:", REGIONS.length, "| ЭПОХ:", ERAS.length,
  "| режимов тренажёра: 3 (нота/интервал/аккорд)");
console.log(`Аудио: вшито ${present} из ${audioRef.size} (остальное — синтез-фолбэк, это нормально)`);
console.log(line);
if (warns.length){ console.log("⚠ ПРЕДУПРЕЖДЕНИЯ ("+warns.length+"):"); warns.slice(0,40).forEach(w=>console.log("  - "+w)); }
if (errors.length){ console.log("✗ ОШИБКИ ("+errors.length+"):"); errors.slice(0,60).forEach(e=>console.log("  ✗ "+e)); console.log(line); console.log("РЕЗУЛЬТАТ: ЕСТЬ ОШИБКИ"); process.exit(1); }
console.log(line); console.log("РЕЗУЛЬТАТ: OK");
