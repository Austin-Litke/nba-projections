export const SYMBOLS = {
  A: { name: "A", payout: {3: 0.7, 4: 2.0, 5: 6.0},  weight: 14 },
  K: { name: "K", payout: {3: 0.7, 4: 1.9, 5: 5.5},  weight: 14 },
  Q: { name: "Q", payout: {3: 0.6, 4: 1.7, 5: 5.0},  weight: 14 },
  J: { name: "J", payout: {3: 0.55,4: 1.5, 5: 4.5},  weight: 14 },
  T: { name: "T", payout: {3: 0.5, 4: 1.4, 5: 4.0},  weight: 14 },

  LION: { name: "🦁", payout: {3: 1.2, 4: 3.5, 5: 12.0}, weight: 7 },
  GEM:  { name: "💎", payout: {3: 1.6, 4: 4.5, 5: 16.0}, weight: 6 },

  WILD: { name: "⭐", payout: null, weight: 3, wild: true },
  SCAT: { name: "🔥", payout: null, weight: 2, scatter: true },
  BONUS: { name: "🟣", payout: null, weight: 0, bonus: true },

};


// Utility lists
export const REELS = 5;
export const ROWS = 3;
export const WAYS = Math.pow(ROWS, REELS); // 3^5 = 243
