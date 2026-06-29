/* Валидатор данных карты. Запуск: node tools/validate.js (из папки продукта).
   Проверяет события/эпохи/категории/территории на корректность и полноту. */
const fs = require("fs"), path = require("path"), vm = require("vm");
const dataDir = path.join(__dirname, "..", "content", "data");
const sandbox = { window: {} }; vm.createContext(sandbox);

const order = ["eras.js", "territories.js", "base_geo.js"]
  .concat(fs.readdirSync(dataDir).filter(f => f.startsWith("events_")).sort());
for (const f of order) vm.runInContext(fs.readFileSync(path.join(dataDir, f), "utf8"), sandbox, { filename:f });

const ERAS = sandbox.window.ERAS || [], CATS = sandbox.window.CATS || [];
const EVENTS = sandbox.window.EVENTS || [], TERR = sandbox.window.TERRITORIES || {};
const BASE = sandbox.window.BASE_GEO || { features:[] };
const catKeys = new Set(CATS.map(c => c.key)), terrKeys = new Set(ERAS.map(e => e.terr));
const periodOf = y => { let c = null; for (const e of ERAS) if (e.from <= y) c = e.key; return c; };

let errors = [], warnings = [], seen = new Map(), perPer = {}, perCat = {};
EVENTS.forEach((e, i) => {
  const w = `#${i}` + (e && e.id ? ` (${e.id})` : "");
  if (!e || typeof e !== "object") { errors.push(`${w}: не объект`); return; }
  if (!e.id) errors.push(`${w}: нет id`);
  else if (seen.has(e.id)) errors.push(`${w}: дубль id (#${seen.get(e.id)})`); else seen.set(e.id, i);
  if (typeof e.year !== "number") errors.push(`${w}: year не число`);
  else if (e.year < -1000 || e.year > 2100) warnings.push(`${w}: необычный год ${e.year}`);
  if (typeof e.lat !== "number" || e.lat < 40 || e.lat > 56) warnings.push(`${w}: lat вне Казахстана (${e.lat})`);
  if (typeof e.lng !== "number" || e.lng < 45 || e.lng > 90) warnings.push(`${w}: lng вне региона (${e.lng})`);
  if (!catKeys.has(e.cat)) errors.push(`${w}: неизвестная категория "${e.cat}"`);
  ["titleRu","titleKz","descRu","descKz"].forEach(f => { if (!e[f] || !String(e[f]).trim()) errors.push(`${w}: пустое ${f}`); });
  const p = (typeof e.year === "number") ? periodOf(e.year) : null;
  if (p) perPer[p] = (perPer[p]||0)+1;
  if (e && e.cat) perCat[e.cat] = (perCat[e.cat]||0)+1;
});
ERAS.forEach(e => { if (e.terr && !TERR[e.terr]) warnings.push(`для периода ${e.key} нет территории "${e.terr}"`); });
if (!(BASE.features||[]).some(f => f.properties && f.properties.name === "Kazakhstan"))
  errors.push("в BASE_GEO нет контура Kazakhstan");
ERAS.forEach(e => { ["nameRu","nameKz"].forEach(f => { if (!e[f]) errors.push(`период ${e.key}: нет ${f}`); }); });

const line = "─".repeat(54);
console.log(line);
console.log("СОБЫТИЙ:", EVENTS.length, "| периодов:", ERAS.length, "| категорий:", CATS.length);
console.log("По периодам (видно за раз на карте):"); ERAS.forEach(e => console.log("  " + (e.key+" ").padEnd(11,"·"), perPer[e.key]||0));
console.log("По категориям:"); CATS.forEach(c => console.log("  " + (c.key+" ").padEnd(10,"·"), perCat[c.key]||0));
console.log(line);
if (warnings.length){ console.log("⚠ ПРЕДУПРЕЖДЕНИЯ ("+warnings.length+"):"); warnings.slice(0,40).forEach(w=>console.log("  - "+w)); }
if (errors.length){ console.log("✗ ОШИБКИ ("+errors.length+"):"); errors.slice(0,60).forEach(e=>console.log("  ✗ "+e)); }
console.log(line);
if (errors.length){ console.log("РЕЗУЛЬТАТ: ЕСТЬ ОШИБКИ"); process.exit(1); }
console.log("РЕЗУЛЬТАТ: OK");
