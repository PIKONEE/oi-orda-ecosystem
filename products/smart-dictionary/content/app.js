/* ============================================================
   Умный словарь — логика (версия для учителя у доски)
   Разделы · карточки-урок · квиз · поиск · скрытие перевода
   Без личной статистики и повторения. Работает автономно и в оболочке.
   ============================================================ */
(function () {
"use strict";

/* ---------- утилиты ---------- */
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const escapeHtml = s => String(s).replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const escapeReg = s => String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
function shuffle(a){ a = a.slice(); for (let i = a.length - 1; i > 0; i--){ const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
function sample(arr, n){ return shuffle(arr).slice(0, n); }
function log(m){ try { window.core && window.core.log && window.core.log("[dict] " + m); } catch (e) {} }

/* ---------- данные ---------- */
const RAW = window.WB || [];
const SEEN = new Set();
const WORDS = [];
let dropped = 0;
RAW.forEach(r => {
  if (!Array.isArray(r) || r.length < 7) { dropped++; return; }
  const [cat, lvl, w, ipa, ru, kz, ex] = r;
  if (!w || !ru || !kz || !Array.isArray(ex) || !ex.length) { dropped++; return; }
  const key = String(w).toLowerCase().trim();
  if (SEEN.has(key)) { dropped++; return; }
  SEEN.add(key);
  WORDS.push({ id: WORDS.length, key, cat, lvl, w, ipa: ipa || "", ru, kz, ex: ex.slice(0, 5) });
});
const BY_ID = new Map(WORDS.map(x => [x.id, x]));
log("words: " + WORDS.length + (dropped ? (", dropped " + dropped) : ""));

/* ---------- состояние ---------- */
const state = {
  lang: localStorage.getItem("sd_lang") || "ru",
  view: "home",
  topic: null,          // ключ категории | "all" | "search"
  level: "all",
  selectMode: false,
  selection: new Set(),
  hideTr: false,
  query: ""
};

/* ---------- i18n ---------- */
const I18N = window.I18N || { ru: {}, kz: {}, catNames: { ru: {}, kz: {} } };
function t(key, vars){
  let s = (I18N[state.lang] && I18N[state.lang][key]) || (I18N.ru && I18N.ru[key]) || key;
  if (vars) for (const k in vars) s = s.replace(new RegExp("\\{" + k + "\\}", "g"), vars[k]);
  return s;
}
const catName = k => (I18N.catNames[state.lang] || I18N.catNames.ru || {})[k] || k;
const catEmoji = k => { const c = (window.DICT_CATS || []).find(x => x.k === k); return c ? c.e : "📚"; };
const tr  = w => state.lang === "kz" ? w.kz : w.ru;
const trAlt = w => state.lang === "kz" ? w.ru : w.kz;
function applyStatic(){
  $$("[data-i18n]").forEach(el => el.textContent = t(el.dataset.i18n));
  $$("[data-i18n-ph]").forEach(el => el.placeholder = t(el.dataset.i18nPh));
  document.documentElement.lang = state.lang;
}

/* ---------- аудио (Web Speech, мягкая деградация) ---------- */
const TTS = ("speechSynthesis" in window);
let voices = [];
if (TTS){ const lv = () => { voices = window.speechSynthesis.getVoices() || []; }; lv(); window.speechSynthesis.onvoiceschanged = lv; }
function speak(text, btn){
  if (!TTS) return;
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US"; u.rate = 0.9;
    const v = voices.find(v => /^en/i.test(v.lang)); if (v) u.voice = v;
    if (btn){ btn.classList.add("playing"); u.onend = u.onerror = () => btn.classList.remove("playing"); }
    window.speechSynthesis.speak(u);
  } catch (e) {}
}

/* ---------- тосты ---------- */
let toastTimer;
function toast(msg){ const el = $("#toast"); el.textContent = msg; el.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove("show"), 2200); }

/* ---------- общие хелперы ---------- */
function boldWord(sentence, word){ return escapeHtml(sentence).replace(new RegExp("\\b(" + escapeReg(word) + ")\\b", "gi"), "<b>$1</b>"); }
const wordsOfCat = k => WORDS.filter(w => w.cat === k);

/* ============================================================
   ГЛАВНАЯ — разделы
   ============================================================ */
const LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"];
function groupName(k){ return ((I18N.groupNames && (I18N.groupNames[state.lang] || I18N.groupNames.ru)) || {})[k] || k; }
function dominantLevel(catKey){
  const counts = {};
  wordsOfCat(catKey).forEach(w => { counts[w.lvl] = (counts[w.lvl] || 0) + 1; });
  let best = "A1", bestN = -1;
  LEVEL_ORDER.forEach(l => { if ((counts[l] || 0) > bestN){ bestN = counts[l] || 0; best = l; } });
  return best;
}
function catTile(catKey){
  const n = wordsOfCat(catKey).length;
  const lvl = dominantLevel(catKey);
  const el = document.createElement("button");
  el.className = "cat cat-img lvl-" + lvl;
  el.dataset.go = catKey;
  el.style.setProperty("--card-img", "url('assets/cards/" + catKey + ".svg')");
  el.innerHTML =
    `<h3>${escapeHtml(catName(catKey))}</h3>
     <div class="meta">${n} ${t("words")} <span class="lvl-tag lvl-${lvl}">${lvl}</span></div>`;
  return el;
}
function renderLegend(){
  const el = $("#legend"); if (!el) return;
  el.innerHTML = `<span class="lg-label">${t("levelsLabel")}:</span>` +
    LEVEL_ORDER.map(l => `<span class="lg"><i class="dot lvl-${l}"></i>${l}</span>`).join("");
}
function renderHome(){
  // featured «Все слова»
  const slot = $("#allWordsSlot");
  if (slot){
    slot.innerHTML = "";
    const all = document.createElement("button");
    all.className = "cat all"; all.dataset.go = "all";
    all.innerHTML =
      `<span class="all-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 7c-1.7-1.1-4-1.4-6-1-.5.1-.8.5-.8 1v10.5c0 .6.5 1 1.1.9 1.9-.4 4-.1 5.7 1"/><path d="M12 7c1.7-1.1 4-1.4 6-1 .5.1.8.5.8 1v10.5c0 .6-.5 1-1.1.9-1.9-.4-4-.1-5.7 1"/><path d="M12 7v12.4"/></svg></span>` +
      `<div class="all-txt"><h3>${t("allWords")}</h3><div class="meta">${WORDS.length} ${t("words")}</div></div>` +
      `<span class="all-go">›</span>`;
    slot.appendChild(all);
  }
  renderLegend();
  // группы → мини-разделы
  const groups = $("#groups"); groups.innerHTML = "";
  (window.DICT_GROUPS || []).forEach((g, gi) => {
    const cats = g.cats.filter(k => wordsOfCat(k).length);
    if (!cats.length) return;
    const total = cats.reduce((s, k) => s + wordsOfCat(k).length, 0);
    const block = document.createElement("div");
    block.className = "group";
    const head = document.createElement("div");
    head.className = "group-head";
    head.innerHTML = `<span class="g-emoji">${g.e}</span><h2>${escapeHtml(groupName(g.k))}</h2><span class="g-count">${total}</span>`;
    const grid = document.createElement("div");
    grid.className = "cats";
    cats.forEach(k => grid.appendChild(catTile(k)));
    block.appendChild(head); block.appendChild(grid);
    groups.appendChild(block);
  });
}

/* ---------- поиск на главной ---------- */
function runSearch(q){
  state.query = q;
  const sb = $("#sectionsBlock"), sr = $("#searchResults");
  const query = q.trim().toLowerCase();
  if (!query){ sr.classList.add("hidden"); sb.classList.remove("hidden"); return; }
  sb.classList.add("hidden"); sr.classList.remove("hidden");
  const list = WORDS.filter(w => w.w.toLowerCase().includes(query) || w.ru.toLowerCase().includes(query) || w.kz.toLowerCase().includes(query));
  const LIMIT = 60;                                  // не рендерим тысячи карточек → нет лагов
  const shown = list.length > LIMIT ? list.slice(0, LIMIT) : list;
  $("#searchTitle").textContent = list.length ? `“${q}” · ${list.length}` : t("emptyTitle");
  renderWords($("#searchList"), shown, false);
  if (list.length > LIMIT){
    const more = document.createElement("div");
    more.className = "search-more";
    more.textContent = (state.lang === "kz" ? "Тағы " : "Ещё ") + (list.length - LIMIT) +
      (state.lang === "kz" ? " — сұранысты нақтылаңыз" : " — уточните запрос");
    $("#searchList").appendChild(more);
  }
}

/* ============================================================
   РАЗДЕЛ
   ============================================================ */
function currentList(){
  let list = state.topic === "all" ? WORDS.slice() : wordsOfCat(state.topic);
  if (state.level !== "all") list = list.filter(w => w.lvl === state.level);
  return list;
}
function buildLevelFilter(){
  const lvls = Array.from(new Set((state.topic === "all" ? WORDS : wordsOfCat(state.topic)).map(w => w.lvl))).sort();
  if (state.level !== "all" && !lvls.includes(state.level)) state.level = "all";
  const btn = (v, label) => `<button class="lvl-btn${state.level === v ? " on" : ""}" data-lvl="${v}">${escapeHtml(label)}</button>`;
  $("#fltLevel").innerHTML = btn("all", t("allLevels")) + lvls.map(l => btn(l, l)).join("");
}
function openTopic(key){
  state.topic = key; state.level = "all"; state.selectMode = false; state.selection.clear(); state.hideTr = false;
  $("#topicEmoji").textContent = key === "all" ? "📚" : catEmoji(key);
  $("#topicName").textContent = key === "all" ? t("allWords") : catName(key);
  buildLevelFilter();
  $("#toggleTr").classList.remove("on"); $("#toggleTr").firstElementChild.textContent = t("hideTr");
  $("#toggleSelect").classList.remove("on"); $("#toggleSelect").firstElementChild.textContent = t("selectWords");
  $("#selTools").classList.add("hidden");
  setView("topic");
}
function renderTopic(){
  const list = currentList();
  $("#topicCount").textContent = list.length + " " + t("words");
  $("#wordlist").classList.toggle("hide-tr", state.hideTr);
  renderWords($("#wordlist"), list, state.selectMode);
  updateSelCount();
}
function renderWords(container, list, showPick){
  if (!list.length){ container.innerHTML = `<div class="empty"><div class="e-emoji">🔍</div><h3>${t("emptyTitle")}</h3><p>${t("emptyDesc")}</p></div>`; return; }
  const frag = document.createDocumentFragment();
  list.forEach(w => {
    const card = document.createElement("div");
    card.className = "wcard" + (state.selection.has(w.id) ? " sel" : "");
    card.dataset.id = w.id;
    const spk = TTS ? `<button class="w-spk" data-speak="${w.id}">🔊</button>` : "";
    const pick = showPick ? `<button class="w-pick" data-pick="${w.id}">${state.selection.has(w.id) ? "✓" : "+"}</button>` : "";
    const ex = w.ex.map(s => `<li>${boldWord(s, w.w)}</li>`).join("");
    card.innerHTML =
      `<div class="w-top">
         <div><div class="w-word">${escapeHtml(w.w)}</div><div class="w-ipa">${escapeHtml(w.ipa)}</div></div>
         ${spk}${pick}
       </div>
       <span class="w-lvl">${escapeHtml(w.lvl)}</span>
       <div class="w-tr">${escapeHtml(tr(w))}<span class="w-alt">${escapeHtml(trAlt(w))}</span></div>
       <button class="w-ex-btn" data-ex="${w.id}">📖 ${t("examples")} <span style="opacity:.6">(${w.ex.length})</span></button>
       <ul class="w-ex">${ex}</ul>`;
    frag.appendChild(card);
  });
  container.innerHTML = ""; container.appendChild(frag);
}
function updateSelCount(){
  const n = state.selection.size;
  $("#selCount").textContent = n ? t("selectedN", { n }) : "";
}

/* выбор слов */
function toggleSelect(id){
  if (state.selection.has(id)) state.selection.delete(id); else state.selection.add(id);
  const card = $(`.wcard[data-id="${id}"]`);
  if (card){ const on = state.selection.has(id); card.classList.toggle("sel", on); const p = card.querySelector(".w-pick"); if (p) p.textContent = on ? "✓" : "+"; }
  updateSelCount();
}

/* источник для карточек/квиза: выбор (если есть) либо весь список раздела */
function sourceIds(){
  let list = currentList();
  if (state.selectMode && state.selection.size) list = list.filter(w => state.selection.has(w.id));
  return list.map(w => w.id);
}

/* ============================================================
   КАРТОЧКИ-УРОК (без оценок: вперёд/назад/перевернуть)
   ============================================================ */
const fc = { ids: [], i: 0, flipped: false };
function startCards(ids){
  ids = ids.filter(id => BY_ID.has(id));
  if (!ids.length){ toast(t("toastTooFew")); return; }
  fc.ids = ids.slice(); fc.i = 0; fc.flipped = false;
  $("#ovCards").classList.add("show");
  showCard();
}
function showCard(){
  const w = BY_ID.get(fc.ids[fc.i]); fc.flipped = false;
  $("#fcCounter").textContent = (fc.i + 1) + " / " + fc.ids.length;
  const spk = TTS ? `<div class="fspk" id="fcSpeak">🔊</div>` : "";
  const ex = w.ex.map(s => `<li>${boldWord(s, w.w)}</li>`).join("");
  $("#fcBody").innerHTML =
    `<div class="fc-scene"><div class="fc" id="fcCard">
       <div class="fc-face fc-front"><div class="fw">${escapeHtml(w.w)}</div><div class="fipa">${escapeHtml(w.ipa)}</div>${spk}</div>
       <div class="fc-face fc-back"><div class="btr">${escapeHtml(tr(w))}<span class="alt">${escapeHtml(trAlt(w))}</span></div><ul class="bex">${ex}</ul></div>
     </div></div>`;
  $("#fcFlip").textContent = t("showTr");
  $("#fcPrev").disabled = fc.i === 0;
  $("#fcNext").disabled = fc.i === fc.ids.length - 1;
}
function flipCard(){ fc.flipped = !fc.flipped; $("#fcCard").classList.toggle("flipped", fc.flipped); $("#fcFlip").textContent = fc.flipped ? t("hideTr") : t("showTr"); }
function moveCard(d){ const n = fc.i + d; if (n < 0 || n >= fc.ids.length) return; fc.i = n; showCard(); }
function shuffleCards(){ fc.ids = shuffle(fc.ids); fc.i = 0; showCard(); }
function closeCards(){ $("#ovCards").classList.remove("show"); if (TTS) window.speechSynthesis.cancel(); }

/* ============================================================
   КВИЗ (только текущая сессия, без сохранения)
   ============================================================ */
const qz = { items: [], idx: 0, score: 0, mistakes: [], source: [] };
function startQuiz(ids){
  ids = ids.filter(id => BY_ID.has(id));
  if (!ids.length){ toast(t("toastTooFew")); return; }
  qz.source = ids.slice();
  const pool = ids.map(id => BY_ID.get(id));
  const picked = sample(pool, Math.min(20, pool.length));
  qz.items = picked.map(w => makeQuestion(w, pool));
  qz.idx = 0; qz.score = 0; qz.mistakes = [];
  $("#ovQuiz").classList.add("show"); $("#qzScore").textContent = "0";
  showQuestion();
}
function distractors(answer, field, pool, k){
  const want = String(answer[field]).toLowerCase();
  const same = shuffle(pool.filter(w => w.id !== answer.id && w.cat === answer.cat));
  const any = shuffle(WORDS.filter(w => w.id !== answer.id));
  const out = [], used = new Set([want]);
  for (const src of [same, any]) for (const w of src){
    const v = String(w[field]).toLowerCase(); if (used.has(v)) continue;
    used.add(v); out.push(w); if (out.length >= k) return out;
  }
  return out;
}
function makeQuestion(w, pool){
  const langField = state.lang === "kz" ? "kz" : "ru";
  const kinds = ["trans", "word"];
  const exCand = w.ex.filter(s => new RegExp("\\b" + escapeReg(w.w) + "\\b", "i").test(s));
  if (exCand.length) kinds.push("blank");
  const kind = kinds[Math.floor(Math.random() * kinds.length)];
  let prompt, sub = "", field, correctVal;
  if (kind === "trans"){ prompt = `${escapeHtml(w.w)}<span class="qipa">${escapeHtml(w.ipa)}</span>`; field = langField; correctVal = w[langField]; }
  else if (kind === "word"){ prompt = escapeHtml(tr(w)); field = "w"; correctVal = w.w; }
  else { const sent = exCand[Math.floor(Math.random() * exCand.length)];
         prompt = escapeHtml(sent).replace(new RegExp("\\b(" + escapeReg(w.w) + ")\\b", "i"), '<span class="blank">_____</span>');
         sub = t("qBlankSub"); field = "w"; correctVal = w.w; }
  const opts = shuffle([{ v: correctVal, ok: true }].concat(distractors(w, field, pool, 3).map(d => ({ v: d[field], ok: false }))));
  return { w, kind, prompt, sub, opts, answered: false };
}
function showQuestion(){
  const q = qz.items[qz.idx];
  $("#qzProg").style.width = (qz.idx / qz.items.length * 100) + "%";
  const lbl = q.kind === "trans" ? t("qKindTrans") : q.kind === "word" ? t("qKindWord") : t("qKindBlank");
  $("#qzBody").innerHTML =
    `<div class="quiz-card">
       <div class="q-kind">${lbl} · ${qz.idx + 1}/${qz.items.length}</div>
       <div class="q-prompt">${q.prompt}</div>
       <div class="q-sub">${q.sub}</div>
       <div class="q-opts" id="qOpts">${q.opts.map((o, i) => `<button class="q-opt" data-opt="${i}">${escapeHtml(o.v)}</button>`).join("")}</div>
       <div class="q-next"><button id="qNext">${qz.idx + 1 < qz.items.length ? t("qNext") : t("qFinish")} →</button></div>
     </div>`;
}
function answerQuiz(i){
  const q = qz.items[qz.idx]; if (q.answered) return; q.answered = true;
  if (q.opts[i].ok){ qz.score++; $("#qzScore").textContent = qz.score; } else qz.mistakes.push(q);
  $$("#qOpts .q-opt").forEach((btn, idx) => { btn.disabled = true; if (q.opts[idx].ok) btn.classList.add("correct"); else if (idx === i) btn.classList.add("wrong"); });
  $("#qNext").classList.add("show");
}
function nextQuestion(){ if (!qz.items[qz.idx].answered) return; qz.idx++; if (qz.idx >= qz.items.length) quizResults(); else showQuestion(); }
function quizResults(){
  $("#qzProg").style.width = "100%";
  const total = qz.items.length, score = qz.score, pct = Math.round(score / total * 100);
  const R = 90, C = 2 * Math.PI * R, off = C * (1 - pct / 100);
  let head, emoji;
  if (pct === 100){ head = t("perfect"); emoji = "🏆"; }
  else if (pct >= 80){ head = t("great"); emoji = "🎉"; }
  else if (pct >= 60){ head = t("good"); emoji = "👍"; }
  else { head = t("needPractice"); emoji = "📚"; }
  const color = pct >= 80 ? "#16a34a" : pct >= 60 ? "#d97706" : "#e11d48";
  const mist = qz.mistakes.length
    ? `<div class="mistakes"><h3>${t("mistakesTitle")}</h3>` + qz.mistakes.map(q =>
        `<div class="mrow"><span class="mw">${escapeHtml(q.w.w)} <span style="color:var(--muted)">${escapeHtml(q.w.ipa)}</span></span><span class="mt">${escapeHtml(tr(q.w))}</span></div>`).join("") + `</div>` : "";
  $("#qzBody").innerHTML =
    `<div class="results">
       <div class="celebrate">${emoji}</div>
       <div class="ring"><svg width="200" height="200"><circle cx="100" cy="100" r="${R}" fill="none" stroke="#e2e8f0" stroke-width="14"/>
         <circle cx="100" cy="100" r="${R}" fill="none" stroke="${color}" stroke-width="14" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C}" id="ringFill" style="transition:stroke-dashoffset 1s var(--ease)"/></svg>
         <div class="pct" style="color:${color}">${pct}%</div></div>
       <h2>${head}</h2>
       <div class="rsub">${t("resScore", { a: score, b: total })}</div>
       <div class="ractions"><button class="b1" id="qzAgain">↻ ${t("resAgain")}</button><button class="b2" id="qzDone">${t("resDone")}</button></div>
       ${mist}
     </div>`;
  setTimeout(() => { const rf = $("#ringFill"); if (rf) rf.style.strokeDashoffset = off; }, 60);
}
function closeQuiz(){ $("#ovQuiz").classList.remove("show"); }

/* ============================================================
   НАВИГАЦИЯ
   ============================================================ */
function setView(v){
  state.view = v;
  $("#view-home").classList.toggle("hidden", v !== "home");
  $("#view-topic").classList.toggle("hidden", v !== "topic");
  if (v === "home") renderHome();
  if (v === "topic") renderTopic();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function goHome(){ state.topic = null; $("#search").value = ""; runSearch(""); setView("home"); }
function setLang(l){
  state.lang = l; localStorage.setItem("sd_lang", l);
  $$(".lang button").forEach(b => b.classList.toggle("active", b.dataset.lang === l));
  applyStatic();
  if (state.view === "home"){ renderHome(); if (state.query) runSearch(state.query); }
  else { $("#topicName").textContent = state.topic === "all" ? t("allWords") : catName(state.topic);
         $("#toggleTr").firstElementChild.textContent = state.hideTr ? t("showTr") : t("hideTr");
         $("#toggleSelect").firstElementChild.textContent = state.selectMode ? t("doneSelect") : t("selectWords");
         buildLevelFilter();
         renderTopic(); }
}

/* ============================================================
   СОБЫТИЯ
   ============================================================ */
function bind(){
  $("#goHome").addEventListener("click", goHome);
  $$(".lang button").forEach(b => b.addEventListener("click", () => setLang(b.dataset.lang)));

  // кнопка «наверх» (показывается при прокрутке, прокручивает страницу в начало)
  const toTop = $("#toTop");
  if (toTop){
    toTop.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
    window.addEventListener("scroll", () => toTop.classList.toggle("show", window.scrollY > 400), { passive: true });
  }

  // главная: поиск и переход в раздел
  let searchTimer;
  $("#search").addEventListener("input", e => { const v = e.target.value; clearTimeout(searchTimer); searchTimer = setTimeout(() => runSearch(v), 130); });
  $("#sectionsBlock").addEventListener("click", e => { const g = e.target.closest("[data-go]"); if (g) openTopic(g.dataset.go); });

  // результаты поиска: озвучка/примеры/перевод
  $("#searchList").addEventListener("click", wordlistClick);

  // раздел
  $("#topicBack").addEventListener("click", goHome);
  $("#fltLevel").addEventListener("click", e => { const b = e.target.closest("[data-lvl]"); if (!b) return; state.level = b.dataset.lvl; buildLevelFilter(); renderTopic(); });
  $("#actCards").addEventListener("click", () => startCards(sourceIds()));
  $("#actQuiz").addEventListener("click", () => startQuiz(sourceIds()));
  $("#toggleTr").addEventListener("click", () => {
    state.hideTr = !state.hideTr;
    $("#toggleTr").classList.toggle("on", state.hideTr);
    $("#toggleTr").firstElementChild.textContent = state.hideTr ? t("showTr") : t("hideTr");
    $("#wordlist").classList.toggle("hide-tr", state.hideTr);
  });
  $("#toggleSelect").addEventListener("click", () => {
    state.selectMode = !state.selectMode;
    if (!state.selectMode) state.selection.clear();
    $("#toggleSelect").classList.toggle("on", state.selectMode);
    $("#toggleSelect").firstElementChild.textContent = state.selectMode ? t("doneSelect") : t("selectWords");
    $("#selTools").classList.toggle("hidden", !state.selectMode);
    renderTopic();
  });
  $("#selAll").addEventListener("click", () => { currentList().forEach(w => state.selection.add(w.id)); renderTopic(); });
  $("#selClear").addEventListener("click", () => { state.selection.clear(); renderTopic(); });
  $("#wordlist").addEventListener("click", wordlistClick);

  // карточки
  $("#ovCards").addEventListener("click", e => {
    if (e.target.closest("#fcClose")) return closeCards();
    if (e.target.closest("#fcShuffle")) return shuffleCards();
    if (e.target.closest("#fcSpeak")){ speak(BY_ID.get(fc.ids[fc.i]).w, e.target.closest("#fcSpeak")); return; }
    if (e.target.closest("#fcPrev")) return moveCard(-1);
    if (e.target.closest("#fcNext")) return moveCard(1);
    if (e.target.closest("#fcFlip") || e.target.closest("#fcCard")) return flipCard();
  });

  // квиз
  $("#ovQuiz").addEventListener("click", e => {
    if (e.target.closest("#qzClose") || e.target.closest("#qzDone")) return closeQuiz();
    if (e.target.closest("#qzAgain")) return startQuiz(qz.source);
    const o = e.target.closest("[data-opt]"); if (o) return answerQuiz(+o.dataset.opt);
    if (e.target.closest("#qNext")) return nextQuestion();
  });

  // клавиатура (удобно у доски / с пультом-кликером)
  document.addEventListener("keydown", e => {
    if ($("#ovCards").classList.contains("show")){
      if (e.key === "ArrowLeft") moveCard(-1);
      else if (e.key === "ArrowRight") moveCard(1);
      else if (e.code === "Space"){ e.preventDefault(); flipCard(); }
      else if (e.key === "Escape") closeCards();
      return;
    }
    if ($("#ovQuiz").classList.contains("show")){
      const q = qz.items[qz.idx];
      if (!q.answered && ["1","2","3","4"].includes(e.key)){ const b = $(`[data-opt="${+e.key - 1}"]`); if (b) answerQuiz(+e.key - 1); }
      else if (q.answered && (e.key === "Enter" || e.code === "Space")){ e.preventDefault(); nextQuestion(); }
      else if (e.key === "Escape") closeQuiz();
    }
  });
}
function wordlistClick(e){
  const sp = e.target.closest("[data-speak]");
  const pk = e.target.closest("[data-pick]");
  const ex = e.target.closest("[data-ex]");
  const trEl = e.target.closest(".w-tr");
  if (sp){ speak(BY_ID.get(+sp.dataset.speak).w, sp); return; }
  if (pk){ toggleSelect(+pk.dataset.pick); return; }
  if (ex){ ex.closest(".wcard").classList.toggle("open"); return; }
  if (trEl && e.currentTarget.classList.contains("hide-tr")){ trEl.classList.toggle("revealed"); return; }
}

/* ---------- мост к оболочке (опционально) ---------- */
function initCore(){
  try {
    if (typeof qt !== "undefined" && qt.webChannelTransport && typeof QWebChannel !== "undefined")
      new QWebChannel(qt.webChannelTransport, ch => { window.core = ch.objects.core; log("ready"); });
    else if (typeof core !== "undefined") window.core = core;
  } catch (e) {}
}

/* ---------- старт ---------- */
function boot(){
  if (!WORDS.length){ document.body.innerHTML = '<div style="display:grid;place-items:center;height:100vh;color:#7c899e;font-family:sans-serif;text-align:center"><div><div style="font-size:3rem">📚</div><p>Словарь не загрузился (content/data/).</p></div></div>'; return; }
  applyStatic();
  $$(".lang button").forEach(b => b.classList.toggle("active", b.dataset.lang === state.lang));
  bind();
  setView("home");
  initCore();
  log("booted");
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();

})();
