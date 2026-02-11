export const SYMBOLS = [
  { id:"seven", icon:"7️⃣", weight: 2,  mult: 25 },
  { id:"diamond", icon:"💎", weight: 3, mult: 15 },
  { id:"bell", icon:"🔔", weight: 5, mult: 10 },
  { id:"cherry", icon:"🍒", weight: 8, mult: 6 },
  { id:"lemon", icon:"🍋", weight: 10, mult: 4 },
  { id:"grape", icon:"🍇", weight: 12, mult: 3 },
  { id:"clover", icon:"🍀", weight: 14, mult: 2 },
];

export function buildWeightedBag(){
  const bag = [];
  for (const s of SYMBOLS){
    for (let i=0;i<s.weight;i++) bag.push(s);
  }
  return bag;
}

export function payoutFor3(symbolId){
  return SYMBOLS.find(s => s.id === symbolId)?.mult ?? 0;
}
