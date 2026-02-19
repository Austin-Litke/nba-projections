import { SYMBOLS, ALL_KEYS, isWild, isScatter } from "./symbols.js";
import { weightedPick } from "./rng.js";

const COLS = 6;
const ROWS = 5;
export const DIM = { COLS, ROWS };

// 25 paylines (row indexes 0..4)
// Each line is length 6 (one row index per reel)
export const PAYLINES = [
  // 5 straight
  [0,0,0,0,0,0],
  [1,1,1,1,1,1],
  [2,2,2,2,2,2],
  [3,3,3,3,3,3],
  [4,4,4,4,4,4],

  // 10 “V” / “Λ” style
  [0,1,2,1,0,1],
  [4,3,2,3,4,3],
  [1,2,3,2,1,2],
  [3,2,1,2,3,2],
  [0,0,1,2,1,0],
  [4,4,3,2,3,4],
  [2,1,0,1,2,1],
  [2,3,4,3,2,3],
  [1,0,1,2,3,4],
  [3,4,3,2,1,0],

  // 10 zigzags
  [0,1,0,1,0,1],
  [4,3,4,3,4,3],
  [1,0,1,0,1,0],
  [3,4,3,4,3,4],
  [0,1,2,3,4,3],
  [4,3,2,1,0,1],
  [2,1,2,3,2,1],
  [2,3,2,1,2,3],
  [1,2,1,0,1,2],
  [3,2,3,4,3,2],
];

function buildWeights() {
  const m = {};
  for (const k of ALL_KEYS) m[k] = SYMBOLS[k].weight ?? 1;
  return m;
}
const WEIGHTS = buildWeights();

export function spinGrid() {
  const grid = Array.from({ length: COLS }, () => Array(ROWS).fill(null));
  for (let c = 0; c < COLS; c++) {
    for (let r = 0; r < ROWS; r++) {
      grid[c][r] = weightedPick(WEIGHTS);
    }
  }
  // small “juice” chance for a wild
  if (Math.random() < 0.12) {
    const c = (Math.random() * COLS) | 0;
    const r = (Math.random() * ROWS) | 0;
    grid[c][r] = "WILD";
  }
  return grid;
}

// Count scatters
export function countScatters(grid) {
  let n = 0;
  for (let c = 0; c < COLS; c++)
    for (let r = 0; r < ROWS; r++)
      if (isScatter(grid[c][r])) n++;
  return n;
}

// Kronos trigger: first column full of KRONOS
export function isKronosTrigger(grid) {
  for (let r = 0; r < ROWS; r++) {
    if (grid[0][r] !== "KRONOS") return false;
  }
  return true;
}

// Evaluate line pays
// bet is TOTAL bet. We split it across paylines: betPerLine = bet / PAYLINES.length
export function evaluateLines(grid, bet) {
  const betPerLine = bet / PAYLINES.length;
  const baseBet = 10;                 // the bet size your paytable is tuned around
  const tierBoost = Math.min(1.35, Math.max(0.85, bet / baseBet));
// bet=10 => 1.00x
// bet=20 => 2.00x BUT capped at 1.35x here (so it doesn't explode)
// bet=5  => 0.50x but floored at 0.85x (so small bets don't feel awful)


  let totalWin = 0;
  const winCells = new Set();
  let winningLines = 0;

  for (let li = 0; li < PAYLINES.length; li++) {
    const line = PAYLINES[li];

    // Determine the “base symbol” by scanning from left for first non-wild, non-scatter
    let base = null;
    for (let c = 0; c < COLS; c++) {
      const k = grid[c][line[c]];
      if (isScatter(k)) { base = null; break; } // scatters don't pay on lines
      if (!isWild(k)) { base = k; break; }
    }
    if (!base) continue;

    // Count consecutive matches from left (base or wild)
    let count = 0;
    const positions = [];
    for (let c = 0; c < COLS; c++) {
      const k = grid[c][line[c]];
      if (isScatter(k)) break;
      if (k === base || isWild(k)) {
        count++;
        positions.push(`${c}-${line[c]}`);
      } else {
        break;
      }
    }

    if (count >= 3) {
      const payTable = SYMBOLS[base]?.linePay;
      const mult = payTable?.[count] ?? 0;
      if (mult > 0) {
        const win = betPerLine * mult * tierBoost;

        totalWin += win;
        winningLines++;
        for (const p of positions) winCells.add(p);
      }
    }
  }

  return { totalWin, winCells, winningLines, betPerLine };
}
