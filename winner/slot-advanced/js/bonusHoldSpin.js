// Hold & Spin / Money Bonus
// You get 3 respins. If you land at least one NEW money ball, respins reset to 3.
// Values are bet-based. Includes jackpots: MINI/MINOR/MAJOR and GRAND-on-full.

const COLS = 5;
const ROWS = 3;
const CELLS = COLS * ROWS;

export const HOLDSPIN_DIM = { COLS, ROWS, CELLS };

export function newHoldSpinState(bet) {
  return {
    bet,
    left: 3,
    total: 0,
    spins: 0,
    filled: Array(CELLS).fill(null), // null or { kind:"money", value } or { kind:"jp", name, value }
    jackpots: { mini: false, minor: false, major: false, grand: false },
  };
}

// ---------- Base money multipliers (relative to bet) ----------
const MONEY_MULTS = [
  { mult: 1.0, w: 40 },   // minimum
  { mult: 1.5, w: 22 },
  { mult: 2.0, w: 16 },
  { mult: 3.0, w: 10 },
  { mult: 5.0, w: 6 },
  { mult: 10,  w: 3 },
  { mult: 20,  w: 1.4 },
  { mult: 50,  w: 0.5 },
  { mult: 100, w: 0.1 },  // super rare money value (not GRAND)
];

function weightedPick(list) {
  const total = list.reduce((a, x) => a + x.w, 0);
  let r = Math.random() * total;
  for (const x of list) {
    r -= x.w;
    if (r <= 0) return x;
  }
  return list[0];
}

function pickMoneyValue(bet) {
  const chosen = weightedPick(MONEY_MULTS);
  return Math.round(bet * chosen.mult);
}

function openSlots(state) {
  const out = [];
  for (let i = 0; i < state.filled.length; i++) {
    if (state.filled[i] == null) out.push(i);
  }
  return out;
}

function isFull(state) {
  return openSlots(state).length === 0;
}

// Chance to land a ball each respin.
function ballChance(state) {
  const empty = openSlots(state).length;
  const filled = CELLS - empty;
  const fillRatio = filled / CELLS; // 0..1
  // roughly: 55% early -> 22% late
  return Math.max(0.22, 0.55 - fillRatio * 0.33);
}

// ---------- Jackpots (only inside bonus) ----------
// NOTE: GRAND is NOT dropped randomly. It is awarded only when full grid.
function jackpotDefs(bet) {
  return [
    { key: "mini",  name: "MINI",  mult: 5,   w: 0.30 },  // ~0.30 weight
    { key: "minor", name: "MINOR", mult: 10,  w: 0.14 },
    { key: "major", name: "MAJOR", mult: 50,  w: 0.03 },
    // no GRAND here
  ].map(x => ({ ...x, value: Math.round(bet * x.mult) }));
}

// Probability to attempt a jackpot drop on a given successful placement
function jackpotAttemptChance(state) {
  // very rare; slightly higher later (feels exciting)
  const filled = CELLS - openSlots(state).length;
  const fillRatio = filled / CELLS;
  // 1.2% early -> 2.2% late
  return 0.012 + fillRatio * 0.010;
}

function pickJackpot(state) {
  const defs = jackpotDefs(state.bet).filter(d => !state.jackpots[d.key]);
  if (!defs.length) return null;

  // Weighted among remaining jackpots
  const total = defs.reduce((a, x) => a + x.w, 0);
  let r = Math.random() * total;
  for (const d of defs) {
    r -= d.w;
    if (r <= 0) return d;
  }
  return defs[0];
}

// Executes ONE respin step.
export function holdSpinStep(state) {
  state.spins++;

  const empties = openSlots(state);
  if (empties.length === 0) {
    return { hitCount: 0, placements: [], ended: true, full: true, awardedGrand: false };
  }

  const chance = ballChance(state);

  let hitCount = 0;
  const placements = [];

  // Up to 3 attempts per respin (multi-hit is rare)
  const attempts = 3;

  for (let a = 0; a < attempts; a++) {
    const emptiesNow = openSlots(state);
    if (emptiesNow.length === 0) break;

    const p = chance * (a === 0 ? 1 : a === 1 ? 0.35 : 0.15);
    if (Math.random() > p) continue;

    const idx = emptiesNow[(Math.random() * emptiesNow.length) | 0];

    // Decide if this placement is a jackpot ball or a normal money ball
    let placed;

    const canTryJackpot = Math.random() < jackpotAttemptChance(state);
    if (canTryJackpot) {
      const jp = pickJackpot(state);
      if (jp) {
        state.jackpots[jp.key] = true;
        placed = { kind: "jp", name: jp.name, value: jp.value, key: jp.key };
      }
    }

    // fallback to money if no jackpot selected
    if (!placed) {
      placed = { kind: "money", value: pickMoneyValue(state.bet) };
    }

    state.filled[idx] = placed;
    state.total += placed.value;

    hitCount++;
    placements.push({ idx, ...placed });
  }

  if (hitCount > 0) state.left = 3;
  else state.left -= 1;

  // If full, award GRAND (only way to get GRAND)
  let awardedGrand = false;
  if (isFull(state) && !state.jackpots.grand) {
    const grandValue = Math.round(state.bet * 1000);
    state.jackpots.grand = true;
    state.total += grandValue;
    awardedGrand = true;
  }

  const ended = state.left <= 0 || isFull(state);
  return { hitCount, placements, ended, full: isFull(state), awardedGrand };
}
