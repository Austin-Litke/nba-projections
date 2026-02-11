export function baccaratPoint(card){
  // A=1, 2-9 face value, 10/J/Q/K = 0
  if (card.r === "A") return 1;
  if (["K","Q","J","10"].includes(card.r)) return 0;
  return Number(card.r);
}

export function handTotal(hand){
  const sum = hand.reduce((a,c) => a + baccaratPoint(c), 0);
  return sum % 10;
}

export function isNatural(total){
  return total === 8 || total === 9;
}

// Baccarat drawing rules
export function shouldPlayerDraw(playerTotal){
  return playerTotal <= 5;
}

export function shouldBankerDraw(bankerTotal, playerThirdCard){
  // If player stands (no third card):
  if (!playerThirdCard) return bankerTotal <= 5;

  const p3 = baccaratPoint(playerThirdCard);

  // Banker third-card rules:
  if (bankerTotal <= 2) return true;
  if (bankerTotal === 3) return p3 !== 8;
  if (bankerTotal === 4) return p3 >= 2 && p3 <= 7;
  if (bankerTotal === 5) return p3 >= 4 && p3 <= 7;
  if (bankerTotal === 6) return p3 === 6 || p3 === 7;
  return false; // 7 stands
}

export function outcome(playerTotal, bankerTotal){
  if (playerTotal > bankerTotal) return "player";
  if (bankerTotal > playerTotal) return "banker";
  return "tie";
}
