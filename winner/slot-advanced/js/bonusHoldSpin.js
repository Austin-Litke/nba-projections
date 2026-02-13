// Hold & Spin / Money Bonus
// You get 3 respins. If you land at least one NEW money ball, respins reset to 3.
// Values are bet-based: min = bet, then weighted multipliers up to 100x.

const COLS = 5;
const ROWS = 3;
const CELLS = COLS * ROWS;

export function newHoldSpinState(bet) {
  return {
    bet,
    left: 3,
    total: 0,
    filled: Array(CELLS).fill(null), // null or number value
    spins: 0,
  };
}

// Weighted multipliers (relative to bet)
const MULTS = [
  { mult: 1.0, w: 40 },   // minimum
  { mult: 1.5, w: 22 },
  { mult: 2.0, w: 16 },
  { mult: 3.0, w: 10 },
  { mult: 5.0, w: 6 },
  { mult: 10,  w: 3 },
  { mult: 20,  w: 1.4 },
  { mult: 50,  w: 0.5 },
  { mult: 100, w: 0.1 },  // super rare
];

function weightedPickMultiplier() {
  const total = MULTS.reduce((a, x) => a + x.w, 0);
  let r = Math.random() * total;
  for (const x of MULTS) {
    r -= x.w;
    if (r <= 0) return x.mult;
  }
  return 1.0;
}

function openSlots(state) {
  const out = [];
  for (let i = 0; i < state.filled.length; i++) {
    if (state.filled[i] == null) out.push(i);
  }
  return out;
}

function ballChance(state) {
  // Starts decent, decreases as you fill the grid
  const empty = openSlots(state).length;
  const filled = CELLS - empty;
  const fillRatio = filled / CELLS; // 0..1
  return Math.max(0.22, 0.55 - fillRatio * 0.33);
}

// Executes ONE respin step.
export function holdSpinStep(state) {
  state.spins++;

  const empties = openSlots(state);
  if (empties.length === 0) {
    return { hitCount: 0, placements: [], ended: true, full: true };
  }

  const chance = ballChance(state);

  let hitCount = 0;
  const placements = [];

  // Up to 3 attempts to add balls per respin (multi-hit is rare)
  const attempts = 3;

  for (let a = 0; a < attempts; a++) {
    const emptiesNow = openSlots(state);
    if (emptiesNow.length === 0) break;

    const p = chance * (a === 0 ? 1 : a === 1 ? 0.35 : 0.15);
    if (Math.random() > p) continue;

    const pick = emptiesNow[(Math.random() * emptiesNow.length) | 0];
    const mult = weightedPickMultiplier();
    const value = Math.round(state.bet * mult);

    state.filled[pick] = value;
    state.total += value;

    hitCount++;
    placements.push({ idx: pick, value });
  }

  if (hitCount > 0) state.left = 3;
  else state.left -= 1;

  const ended = state.left <= 0;
  const full = openSlots(state).length === 0;

  return { hitCount, placements, ended: ended || full, full };
}

export const HOLDSPIN_DIM = { COLS, ROWS, CELLS };
