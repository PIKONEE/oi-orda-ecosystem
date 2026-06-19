/* Порядок и оформление разделов словаря.
   Ключ (k) совпадает с первым элементом записей в cat_*.js и с I18N.catNames. */
window.DICT_CATS = [
  {k:"basics",     e:"🧩"},
  {k:"phrases",    e:"💬"},
  {k:"people",     e:"👨‍👩‍👧"},
  {k:"food",       e:"🍎"},
  {k:"home",       e:"🏠"},
  {k:"objects",    e:"🧰"},
  {k:"clothing",   e:"👕"},
  {k:"body",       e:"🩺"},
  {k:"animals",    e:"🐾"},
  {k:"nature",     e:"🌿"},
  {k:"city",       e:"🏙️"},
  {k:"society",    e:"🌍"},
  {k:"travel",     e:"✈️"},
  {k:"work",       e:"💼"},
  {k:"school",     e:"🎓"},
  {k:"tech",       e:"💻"},
  {k:"time",       e:"⏰"},
  {k:"emotions",   e:"😊"},
  {k:"verbs",      e:"🏃"},
  {k:"adjectives", e:"🎨"},
  {k:"money",      e:"💰"},
  {k:"sports",     e:"⚽"},
  {k:"misc",       e:"✨"},
  {k:"academic",      e:"📑"},
  {k:"business2",     e:"📈"},
  {k:"science",       e:"🔬"},
  {k:"nature2",       e:"🌱"},
  {k:"society2",      e:"⚖️"},
  {k:"character",     e:"🧠"},
  {k:"verbs2",        e:"⚙️"},
  {k:"communication", e:"🗣️"},
  {k:"phrasal",       e:"🔗"},
  {k:"abstract",      e:"💡"},
  {k:"adv_academic",  e:"🏛️"},
  {k:"adv_verbs",     e:"✒️"},
  {k:"adv_adjectives",e:"💎"},
  {k:"adv_people",    e:"🎭"},
  {k:"adv_society",   e:"⚖️"},
  {k:"adv_phrases",   e:"🗂️"}
];
/* Тематические группы для главной: группа → мини-разделы.
   k — ключ группы (совпадает с I18N.groupNames), cats — список cat-ключей. */
window.DICT_GROUPS = [
  {k:"basics_comm", e:"🗣️", cats:["basics","phrases","communication","people"]},
  {k:"daily",       e:"🏡", cats:["food","home","objects","clothing","time","money"]},
  {k:"person",      e:"🧍", cats:["body","emotions","character","sports"]},
  {k:"world",       e:"🌍", cats:["city","travel","animals","nature","nature2","society","society2"]},
  {k:"study",       e:"🎓", cats:["school","academic","science","tech","work","business2"]},
  {k:"language",    e:"🔤", cats:["verbs","verbs2","adjectives","phrasal","abstract","misc"]},
  {k:"advanced",    e:"🏛️", cats:["adv_academic","adv_verbs","adv_adjectives","adv_people","adv_society","adv_phrases"]}
];

/* Накопитель «сырых» слов. Каждый cat_*.js делает window.WB.push([...]) */
window.WB = window.WB || [];
