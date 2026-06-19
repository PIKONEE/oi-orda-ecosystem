/* Валидатор данных «Кабинет логопеда». node tools/validate.js
   Проверяет карточки/игру/скороговорки, считает покрытие картинок и озвучки. */
const fs = require("fs"), path = require("path"), vm = require("vm");
const C = path.join(__dirname, "..", "content");
const dataDir = path.join(C, "data"), locDir = path.join(C, "locales");
const imgDir = path.join(C, "images"), audDir = path.join(C, "audio");
const sb = { window:{} }; vm.createContext(sb);
for (const f of ["sounds_ru.js","sounds_kz.js","game_ru.js","game_kz.js","twisters_ru.js","twisters_kz.js","credits.js"])
  vm.runInContext(fs.readFileSync(path.join(dataDir,f),"utf8"), sb, {filename:f});
vm.runInContext(fs.readFileSync(path.join(locDir,"i18n.js"),"utf8"), sb, {filename:"i18n.js"});

const TR = {"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"c","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"," ":"_","-":"_","ә":"ae","ғ":"gh","қ":"q","ң":"ng","ө":"oe","ұ":"uu","ү":"ue","һ":"hh","і":"ii"};
const translit = w => String(w).toLowerCase().split("").map(c=>TR[c]!=null?TR[c]:"").join("").replace(/_+/g,"_").replace(/^_|_$/g,"");
const emojiCode = e => Array.from(e).map(c=>c.codePointAt(0)).filter(cp=>cp!==0xFE0F).map(cp=>cp.toString(16).toUpperCase()).join("-");
const hasImg = code => fs.existsSync(path.join(imgDir, code + ".svg"));
const hasAud = (lang,w) => ["mp3","ogg"].some(e => fs.existsSync(path.join(audDir, lang+"_"+translit(w)+"."+e)));

let errors=[], warns=[], cards=0, gameItems=0, tw=0;
const emojis=new Set(), wordsRu=new Set(), wordsKz=new Set();

function checkCards(arr, lang){
  (arr||[]).forEach((g,gi)=>{
    if(!g.sound) errors.push(`${lang} группа #${gi}: нет sound`);
    (g.cards||[]).forEach((c,ci)=>{
      const w=`${lang} ${g.sound} #${ci}`; cards++;
      if(!c.word) errors.push(`${w}: нет word`); else (lang==="ru"?wordsRu:wordsKz).add(c.word);
      if(!c.emoji) errors.push(`${w}: нет emoji`); else emojis.add(c.emoji);
      if(!["н","с","к"].includes(c.pos)) warns.push(`${w}: pos="${c.pos}"`);
    });
  });
}
function checkGame(arr, lang){
  (arr||[]).forEach((p,pi)=>{
    if(!p.a||!p.b) errors.push(`${lang} пара #${pi}: нет a/b`);
    (p.items||[]).forEach((it,ii)=>{
      gameItems++;
      if(!it.word) errors.push(`${lang} пара ${p.a}/${p.b} #${ii}: нет word`); else (lang==="ru"?wordsRu:wordsKz).add(it.word);
      if(it.ans!==p.a && it.ans!==p.b) errors.push(`${lang} ${it.word}: ans "${it.ans}" не из пары`);
    });
  });
}
function checkTw(arr, lang){
  (arr||[]).forEach((t,i)=>{
    tw++;
    if(!t.text) errors.push(`${lang} скороговорка #${i}: нет text`);
    if(!Array.isArray(t.sounds)||!t.sounds.length) errors.push(`${lang} #${i}: нет sounds`);
    else t.sounds.forEach(s=>{ if(!t.text.toLowerCase().includes(s.toLowerCase())) warns.push(`${lang} #${i}: звук "${s}" не найден в тексте`); });
  });
}
checkCards(sb.window.SOUNDS_RU,"ru"); checkCards(sb.window.SOUNDS_KZ,"kz");
checkGame(sb.window.GAME_RU,"ru");   checkGame(sb.window.GAME_KZ,"kz");
checkTw(sb.window.TW_RU,"ru");       checkTw(sb.window.TW_KZ,"kz");

// i18n parity
const I=sb.window.I18N||{};
if(I.ru&&I.kz){ Object.keys(I.ru).forEach(k=>{ if(!(k in I.kz)) errors.push(`i18n: нет kz."${k}"`); });
  Object.keys(I.kz).forEach(k=>{ if(!(k in I.ru)) errors.push(`i18n: нет ru."${k}"`); }); }

// покрытие
let imgOk=0; emojis.forEach(e=>{ if(hasImg(emojiCode(e))) imgOk++; });
let audRu=0; wordsRu.forEach(w=>{ if(hasAud("ru",w)) audRu++; });
let audKz=0; wordsKz.forEach(w=>{ if(hasAud("kz",w)) audKz++; });

const line="─".repeat(58);
console.log(line);
console.log(`КАРТОЧЕК: ${cards} | заданий игры: ${gameItems} | скороговорок: ${tw}`);
console.log(`Картинки OpenMoji: ${imgOk}/${emojis.size} уникальных эмодзи`);
console.log(`Озвучка (вшито): RU ${audRu}/${wordsRu.size}, KZ ${audKz}/${wordsKz.size} (нет → фолбэк speechSynthesis)`);
console.log(line);
if(warns.length){ console.log("⚠ ПРЕДУПРЕЖДЕНИЯ ("+warns.length+"):"); warns.slice(0,40).forEach(w=>console.log("  - "+w)); }
if(errors.length){ console.log("✗ ОШИБКИ ("+errors.length+"):"); errors.slice(0,60).forEach(e=>console.log("  ✗ "+e)); console.log(line); console.log("РЕЗУЛЬТАТ: ЕСТЬ ОШИБКИ"); process.exit(1); }
console.log(line); console.log("РЕЗУЛЬТАТ: OK");
