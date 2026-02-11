export function buildDeck(){
  const suits = ["♠","♥","♦","♣"];
  const ranks = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"];
  const d = [];
  for (const s of suits) for (const r of ranks) d.push({ r, s });

  for (let i = d.length - 1; i > 0; i--){
    const j = Math.floor(Math.random() * (i + 1));
    [d[i], d[j]] = [d[j], d[i]];
  }
  return d;
}

export function draw(state, toHand){
  if (state.deck.length === 0) state.deck = buildDeck();
  toHand.push(state.deck.pop());
}
