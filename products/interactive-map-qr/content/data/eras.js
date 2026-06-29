/* Периоды истории Казахстана (мельче, чтобы на карте было немного событий за раз).
   Активный период для года Y = период с наибольшим from ≤ Y.
   terr — ключ территории в window.TERRITORIES (несколько периодов могут делить одну
   территорию). from/to — годы (до н.э. — отрицательные). */
window.ERAS = [
  // territory (terr) показывается ТОЛЬКО там, где было казахское государство:
  // ханство/жузы (1465–1821) и советская республика → совр. Казахстан (1920–).
  // До ханства и в составе Российской империи (1822–1920) territory = null (не рисуем).
  {key:"saka",      from:-800, terr:null,           color:"#c2a06b", nameRu:"Саки и ранние кочевники",            nameKz:"Сақтар және ерте көшпелілер"},
  {key:"huns",      from:-200, terr:null,           color:"#b5835a", nameRu:"Гунны, уйсуны, кангюй",               nameKz:"Ғұндар, үйсіндер, қаңлылар"},
  {key:"turkic",    from:552,  terr:null,           color:"#7f9172", nameRu:"Тюркский каганат",                   nameKz:"Түрік қағанаты"},
  {key:"medieval",  from:766,  terr:null,           color:"#8d9db6", nameRu:"Карлуки, Караханиды, Кипчаки",       nameKz:"Қарлұқтар, Қарахандар, Қыпшақтар"},
  {key:"mongol",    from:1219, terr:null,           color:"#b08aa6", nameRu:"Монголы, Золотая Орда, Ак-Орда",     nameKz:"Моңғолдар, Алтын Орда, Ақ Орда"},
  {key:"khanate1",  from:1465, terr:"khanate_early",color:"#c08552", nameRu:"Казахское ханство: образование",     nameKz:"Қазақ хандығы: құрылуы"},
  {key:"khanate2",  from:1600, terr:"khanate_peak", color:"#a96a2c", nameRu:"Ханство: расцвет и борьба с джунгарами", nameKz:"Хандық: гүлдену және жоңғармен күрес"},
  {key:"colonial1", from:1731, terr:"zhuzes",       color:"#9aa0a6", nameRu:"Присоединение к России",             nameKz:"Ресейге қосылу"},
  {key:"colonial2", from:1822, terr:null,           color:"#868c93", nameRu:"Колониальные реформы и восстания",   nameKz:"Отарлық реформалар мен көтерілістер"},
  {key:"colonial3", from:1875, terr:null,           color:"#79808a", nameRu:"Колонизация и национальное пробуждение", nameKz:"Отарлау және ұлттық ояну"},
  {key:"alash",     from:1917, terr:null,           color:"#c9a227", nameRu:"Революция и Алаш",                   nameKz:"Революция және Алаш"},
  {key:"soviet1",   from:1920, terr:"modern",       color:"#a4503f", nameRu:"Советский Казахстан: становление",   nameKz:"Кеңестік Қазақстан: қалыптасу"},
  {key:"soviet2",   from:1940, terr:"modern",       color:"#8f4436", nameRu:"Война и поздний СССР",               nameKz:"Соғыс және кейінгі КСРО"},
  {key:"indep1",    from:1991, terr:"modern",       color:"#2a9d8f", nameRu:"Становление независимости",          nameKz:"Тәуелсіздіктің қалыптасуы"},
  {key:"indep2",    from:2005, terr:"modern",       color:"#1f8276", nameRu:"Современный Казахстан",              nameKz:"Қазіргі Қазақстан"}
];

/* Категории событий: цвет метки + название RU/KZ. */
window.CATS = [
  {key:"state",   color:"#2a6f97", nameRu:"Государство и политика", nameKz:"Мемлекет және саясат"},
  {key:"war",     color:"#9d0208", nameRu:"Войны и битвы",          nameKz:"Соғыстар мен шайқастар"},
  {key:"treaty",  color:"#6a4c93", nameRu:"Договоры и реформы",     nameKz:"Шарттар мен реформалар"},
  {key:"culture", color:"#1b7a43", nameRu:"Культура и наука",       nameKz:"Мәдениет және ғылым"},
  {key:"city",    color:"#b5651d", nameRu:"Города и памятники",     nameKz:"Қалалар мен ескерткіштер"},
  {key:"tragedy", color:"#3a3a3a", nameRu:"Трагедии и восстания",   nameKz:"Қасіреттер мен көтерілістер"},
  {key:"modern",  color:"#0a9396", nameRu:"Современность",          nameKz:"Қазіргі заман"}
];

/* Накопитель событий — каждый data/events_*.js делает window.EVENTS.push(...) */
window.EVENTS = window.EVENTS || [];
