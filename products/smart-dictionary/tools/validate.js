/* Валидатор словаря: запускает data/*.js в песочнице window и проверяет данные.
   Запуск: node tools/validate.js  (из папки продукта) */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const dataDir = path.join(__dirname, "..", "content", "data");
const i18nPath = path.join(__dirname, "..", "content", "locales", "i18n.js");

const sandbox = { window: {} };
vm.createContext(sandbox);

// порядок: index.js (создаёт WB и DICT_CATS), затем все cat_*.js
const files = ["index.js"].concat(
  fs.readdirSync(dataDir).filter(f => f.startsWith("cat_")).sort()
);
for (const f of files) {
  const code = fs.readFileSync(path.join(dataDir, f), "utf8");
  vm.runInContext(code, sandbox, { filename: f });
}
vm.runInContext(fs.readFileSync(i18nPath, "utf8"), sandbox, { filename: "i18n.js" });

const WB = sandbox.window.WB || [];
const CATS = sandbox.window.DICT_CATS || [];
const I18N = sandbox.window.I18N || {};
const catKeys = new Set(CATS.map(c => c.k));
const i18nCatRu = (I18N.catNames && I18N.catNames.ru) || {};
const i18nCatKz = (I18N.catNames && I18N.catNames.kz) || {};

let errors = [], warnings = [];
const seen = new Map();          // word -> first index
const perCat = {};
const levels = {};

WB.forEach((r, i) => {
  const where = `#${i}`;
  if (!Array.isArray(r) || r.length < 7) { errors.push(`${where}: запись не массив из 7 полей`); return; }
  const [cat, lvl, w, ipa, ru, kz, ex] = r;
  if (!catKeys.has(cat)) errors.push(`${where} (${w}): неизвестная категория "${cat}"`);
  if (!["A1","A2","B1","B2","C1","C2"].includes(lvl)) warnings.push(`${where} (${w}): необычный уровень "${lvl}"`);
  if (!w || typeof w !== "string") errors.push(`${where}: пустое слово`);
  if (!ipa) warnings.push(`${where} (${w}): нет транскрипции`);
  if (!ru) errors.push(`${where} (${w}): нет RU перевода`);
  if (!kz) errors.push(`${where} (${w}): нет KZ перевода`);
  if (!Array.isArray(ex) || ex.length < 3) errors.push(`${where} (${w}): нужно ≥3 примера, есть ${ex ? ex.length : 0}`);
  else if (ex.length > 5) warnings.push(`${where} (${w}): >5 примеров`);
  if (Array.isArray(ex)) ex.forEach((s, k) => { if (!s || s.length < 4) errors.push(`${where} (${w}): пустой/короткий пример [${k}]`); });
  const key = String(w).toLowerCase().trim();
  if (seen.has(key)) warnings.push(`дубль слова "${w}" (${where} и #${seen.get(key)}) — будет отброшен`);
  else seen.set(key, i);
  perCat[cat] = (perCat[cat] || 0) + 1;
  levels[lvl] = (levels[lvl] || 0) + 1;
});

// проверка переводов названий категорий
CATS.forEach(c => {
  if (!i18nCatRu[c.k]) errors.push(`нет RU названия категории "${c.k}"`);
  if (!i18nCatKz[c.k]) errors.push(`нет KZ названия категории "${c.k}"`);
  if (!perCat[c.k]) warnings.push(`категория "${c.k}" объявлена, но без слов`);
});

const uniqueCount = seen.size;
console.log("─".repeat(54));
console.log("СЛОВАРЬ: записей =", WB.length, "| уникальных =", uniqueCount, "| дублей =", WB.length - uniqueCount);
console.log("Категорий:", CATS.length);
console.log("По уровням:", JSON.stringify(levels));
console.log("По категориям:");
CATS.forEach(c => console.log("   " + (c.k + " ").padEnd(13, "·"), perCat[c.k] || 0));
console.log("─".repeat(54));
if (warnings.length) { console.log("⚠ ПРЕДУПРЕЖДЕНИЯ (" + warnings.length + "):"); warnings.slice(0, 40).forEach(w => console.log("  -", w)); }
if (errors.length) { console.log("�’ ОШИБКИ (" + errors.length + "):"); errors.slice(0, 60).forEach(e => console.log("  ✗", e)); }
console.log("─".repeat(54));
if (errors.length) { console.log("РЕЗУЛЬТАТ: ЕСТЬ ОШИБКИ"); process.exit(1); }
console.log("РЕЗУЛЬТАТ: OK" + (uniqueCount >= 1000 ? " — 1000+ слов ✓" : (" — ВНИМАНИЕ: < 1000 (" + uniqueCount + ")")));
