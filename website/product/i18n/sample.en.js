// English sample content. Same shape as sample.zh.js. The 26 words keep the
// Chinese sample's segmentation and timing (edit-model.js): segments are words
// 0–4, 5–8, 9–16, 17–22, 23–25; the razor demo cuts before word 13.
export default {
  spaced: true, // words are joined with spaces
  words: [
    "Let's", "head", "along", "the river", "first,",
    "Wait", "till the team", "grabs", "supplies,",
    "Then", "we'll all go", "to", "the hilltop", "and check", "for any", "new", "missions,",
    "If we", "run into", "enemies", "on the way,", "find", "cover first,",
    "Don't", "rush", "to shoot.",
  ],
  team: "Got it. You go on ahead.",
  readings: ["emissions,", "missions,", "positions,"],
  raw: ["let's head along the river first got it you go on ahead send ", { bad: "Alana" }, " up front to tank for a bit ", { bad: "twelve F" }, "'s skill isn't ready yet then we'll all go to the hilltop and check for any new ", { bad: "emissions" }],
  rows: [
    ["Let's head along the river first,"],
    ["Got it. You go on ahead."],
    ["Send ", { fix: "Alanna" }, " up front to tank for a bit,"],
    [{ fix: "12F" }, "'s skill isn't ready yet."],
    ["Then we'll all go to the hilltop and check for any new ", { review: "missions" }, "."],
  ],
  proofread: [
    { pre: "Send ", from: "Alana", to: "Alanna", post: " up front to tank" },
    { pre: "", from: "twelve F", to: "12F", post: "'s skill isn't ready" },
    { pre: "", from: "Silver Ash", to: "SilverAsh", post: ", hold your skill" },
    { pre: "", from: "Amia", to: "Amiya", post: ", ult now" },
  ],
  proofAdd: ["Silver Ash → SilverAsh", "twelve F → 12F"],
  add: { alias: "Silver Ash", name: "SilverAsh" },
  // Glossary entries by id (product/glossary-data.json). Arknights and Zenless
  // Zone Zero use the games' English names; Roco Kingdom names are translated.
  glossary: {
    ark0: "12F", ark1: "Alanna", ark2: "Aroma", ark3: "Amiya", ark4: "Ascalon",
    ark5: "Shaw", ark6: "Ela", ark7: "Erato", ark8: "Irene", ark9: "Iris",
    zzz0: "Soldier 11", zzz1: "Ellen", zzz2: "Alice", zzz3: "Aria", zzz4: "Anby",
    zzz5: "Anton", zzz6: "Orphie", zzz7: "Orphie & Magus", zzz8: "Burnice", zzz9: "Trigger",
    roco0: "Dimo", roco1: "Holy Light Dimo", roco2: "Holy Grass Dimo", roco3: "Holy Fire Dimo", roco4: "Holy Water Dimo",
    roco5: "Meowmeow", roco6: "Meowoo", roco7: "Magic Cat", roco8: "Leafcrown Magic Cat", roco9: "Brawler Cool Cat",
  },
};
