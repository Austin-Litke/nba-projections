export const SYMBOLS = {
  // HIGH
  KRONOS: { name: "🧔‍♂️", tier: "high", linePay: { 3: 10, 4: 30, 5: 120, 6: 500 }, weight: 5 },
  CLOCK:  { name: "⏱️",   tier: "high", linePay: { 3: 8,  4: 24, 5: 95,  6: 380 }, weight: 7 },
  TITAN:  { name: "⚡",   tier: "high", linePay: { 3: 6,  4: 18, 5: 75,  6: 300 }, weight: 8 },

  // MID
  GEM:    { name: "💎",   tier: "mid",  linePay: { 3: 4.5, 4: 12, 5: 45, 6: 160 }, weight: 10 },
  RUNE:   { name: "🔮",   tier: "mid",  linePay: { 3: 3.8, 4: 10, 5: 36, 6: 130 }, weight: 11 },
  HELM:   { name: "🪖",   tier: "mid",  linePay: { 3: 3.2, 4: 8.5,5: 30, 6: 110 }, weight: 12 },

  // LOW  (tuned so 3 J pays ~$1.00 on a $10 bet with 25 lines)
  // betPerLine = bet/25 so $10 bet => $0.40 per line
  // 0.40 * 2.5 = $1.00  ✅
  J:      { name: "J", tier: "low", linePay: { 3: 2.5, 4: 6.5, 5: 20, 6: 70 }, weight: 16 },
  Q:      { name: "Q", tier: "low", linePay: { 3: 2.8, 4: 7.5, 5: 24, 6: 80 }, weight: 15 },
  K:      { name: "K", tier: "low", linePay: { 3: 3.1, 4: 8.5, 5: 28, 6: 95 }, weight: 14 },
  A:      { name: "A", tier: "low", linePay: { 3: 3.5, 4: 10,  5: 35, 6: 120 }, weight: 13 },

  // SPECIALS
  WILD:   { name: "🌀", wild: true, weight: 3 },
  SCAT:   { name: "🌌", scat: true, weight: 2 },
};

export const ALL_KEYS = Object.keys(SYMBOLS);

export function isWild(k){ return !!SYMBOLS[k]?.wild; }
export function isScatter(k){ return !!SYMBOLS[k]?.scat; }
