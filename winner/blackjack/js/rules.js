export function cardValue(rank){
  if (rank === "A") return 11;
  if (["K","Q","J"].includes(rank)) return 10;
  return Number(rank);
}

export function handValue(hand){
  let total = 0, aces = 0;
  for (const c of hand){
    total += cardValue(c.r);
    if (c.r === "A") aces++;
  }
  while (total > 21 && aces > 0){
    total -= 10;
    aces--;
  }
  return total;
}

export function isBlackjack(hand){
  return hand.length === 2 && handValue(hand) === 21;
}

export function clampBet(b){
  if (!Number.isFinite(b) || b <= 0) return 1;
  return Math.max(1, Math.floor(b));
}
