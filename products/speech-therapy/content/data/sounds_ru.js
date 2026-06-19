/* Карточки звуков (русский). Группы по проблемному звуку. У каждого слова есть эмодзи
   (→ картинка OpenMoji) и позиция звука (н=начало, с=середина, к=конец). Озвучка слова
   подбирается автоматически (TTS/Wikimedia) + рантайм-фолбэк speechSynthesis. */
window.SOUNDS_RU = [
 {sound:"Р", color:"#e0556b", cards:[
   {word:"рыба", emoji:"🐟", pos:"н"}, {word:"ракета", emoji:"🚀", pos:"н"},
   {word:"роза", emoji:"🌹", pos:"н"}, {word:"радуга", emoji:"🌈", pos:"н"},
   {word:"корова", emoji:"🐄", pos:"с"}, {word:"топор", emoji:"🪓", pos:"к"} ]},
 {sound:"Л", color:"#5b8def", cards:[
   {word:"луна", emoji:"🌙", pos:"н"}, {word:"лампа", emoji:"💡", pos:"н"},
   {word:"лимон", emoji:"🍋", pos:"н"}, {word:"лиса", emoji:"🦊", pos:"н"},
   {word:"лошадь", emoji:"🐴", pos:"н"}, {word:"лук", emoji:"🧅", pos:"н"} ]},
 {sound:"С", color:"#3fb6a8", cards:[
   {word:"солнце", emoji:"☀️", pos:"н"}, {word:"собака", emoji:"🐕", pos:"н"},
   {word:"сова", emoji:"🦉", pos:"н"}, {word:"слон", emoji:"🐘", pos:"н"},
   {word:"самолёт", emoji:"✈️", pos:"н"}, {word:"автобус", emoji:"🚌", pos:"к"} ]},
 {sound:"Ш", color:"#f08a3c", cards:[
   {word:"шар", emoji:"🎈", pos:"н"}, {word:"шапка", emoji:"🧢", pos:"н"},
   {word:"кошка", emoji:"🐈", pos:"с"}, {word:"машина", emoji:"🚗", pos:"с"},
   {word:"мышь", emoji:"🐁", pos:"к"}, {word:"груша", emoji:"🍐", pos:"с"} ]},
 {sound:"З", color:"#8e6fd8", cards:[
   {word:"замок", emoji:"🔒", pos:"н"}, {word:"заяц", emoji:"🐰", pos:"н"},
   {word:"зонт", emoji:"☂️", pos:"н"}, {word:"звезда", emoji:"⭐", pos:"н"},
   {word:"зебра", emoji:"🦓", pos:"н"}, {word:"коза", emoji:"🐐", pos:"с"} ]},
 {sound:"Ж", color:"#d98a2b", cards:[
   {word:"жук", emoji:"🪲", pos:"н"}, {word:"жираф", emoji:"🦒", pos:"н"},
   {word:"ёжик", emoji:"🦔", pos:"с"}, {word:"ножницы", emoji:"✂️", pos:"с"},
   {word:"лыжи", emoji:"🎿", pos:"с"}, {word:"снежинка", emoji:"❄️", pos:"с"} ]},
 {sound:"Ц", color:"#c0518a", cards:[
   {word:"цветок", emoji:"🌸", pos:"н"}, {word:"цыплёнок", emoji:"🐤", pos:"н"},
   {word:"яйцо", emoji:"🥚", pos:"с"}, {word:"курица", emoji:"🐔", pos:"с"},
   {word:"кольцо", emoji:"💍", pos:"с"}, {word:"огурец", emoji:"🥒", pos:"к"} ]},
 {sound:"Ч", color:"#2f9e6e", cards:[
   {word:"часы", emoji:"⏰", pos:"н"}, {word:"чашка", emoji:"☕", pos:"н"},
   {word:"бабочка", emoji:"🦋", pos:"с"}, {word:"очки", emoji:"👓", pos:"с"},
   {word:"мяч", emoji:"⚽", pos:"к"}, {word:"ключ", emoji:"🔑", pos:"к"} ]},
 {sound:"Щ", color:"#5aa02c", cards:[
   {word:"щенок", emoji:"🐶", pos:"н"}, {word:"щётка", emoji:"🧹", pos:"н"},
   {word:"ящик", emoji:"📦", pos:"с"}, {word:"овощи", emoji:"🥦", pos:"с"},
   {word:"плащ", emoji:"🧥", pos:"к"}, {word:"борщ", emoji:"🍲", pos:"к"} ]}
];
