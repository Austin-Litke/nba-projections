import { DIM, PAYLINES, evaluateLines } from "./engine.js";

// Bonus grid starts empty. Only KRONOS drops in.
// Any time at least 1 new KRONOS lands, spins reset to 3.
// End when spins hit 0.

export function newKronosBonusState(bet) {
  return {
    bet,
    left: 3,
    total: 0,
    spins: 0,
    grid: Array.from({ length: DIM.COLS }, () => Array(DIM.ROWS).fill(null)), // null or "KRONOS"
  };
}

function openSlots(state) {
  const out = [];
  for (let c = 0; c < DIM.COLS; c++)
    for (let r = 0; r < DIM.ROWS; r++)
      if (state.grid[c][r] == null) out.push({ c, r });
  return out;
}

function chance(state) {
  // Pretty “slot-like”: higher early, lower later
  const empties = openSlots(state).length;
  const fillRatio = 1 - empties / (DIM.COLS * DIM.ROWS);
  return Math.max(0.18, 0.52 - fillRatio * 0.30);
}

export function kronosBonusStep(state) {
  state.spins++;

  const empties = openSlots(state);
  if (!empties.length) {
    // full grid => just end, pay lines
    return { hitCount: 0, ended: true, full: true, winNow: 0 };
  }

  let hitCount = 0;

  // up to 3 “drop attempts” per respin
  const attempts = 3;
  const pBase = chance(state);

  for (let a = 0; a < attempts; a++) {
    const emptiesNow = openSlots(state);
    if (!emptiesNow.length) break;

    const p = pBase * (a === 0 ? 1 : a === 1 ? 0.35 : 0.15);
    if (Math.random() > p) continue;

    const pick = emptiesNow[(Math.random() * emptiesNow.length) | 0];
    state.grid[pick.c][pick.r] = "KRONOS";
    hitCount++;
  }

  if (hitCount > 0) state.left = 3;
  else state.left -= 1;

  // Pay is line-based, but ONLY for KRONOS (we’ll treat all filled as KRONOS, empty as “dead”)
  // We can reuse evaluateLines by converting nulls into a blocker symbol.
  const blocker = "BLOCK";
  const gridForEval = state.grid.map(col => col.map(x => x ?? blocker));

  // Fake a paytable behavior: if blocker appears, it stops the line.
  // So we do a custom eval: count consecutive KRONOS from left along each payline.
  let totalWinThisSpin = 0;
  const betPerLine = state.bet / PAYLINES.length;

  for (const line of PAYLINES) {
    let count = 0;
    for (let c = 0; c < DIM.COLS; c++) {
      const k = gridForEval[c][line[c]];
      if (k === "KRONOS") count++;
      else break;
    }
    if (count >= 3) {
      // bonus pays are BIG. Tune these if needed.
      // 3/4/5/6 Kronos on a line:
      const mult = count === 3 ? 3 : count === 4 ? 10 : count === 5 ? 35 : 150;
      totalWinThisSpin += betPerLine * mult;
    }
  }

  state.total += totalWinThisSpin;

  const ended = state.left <= 0;
  const full = openSlots(state).length === 0;

  return { hitCount, ended: ended || full, full, winNow: totalWinThisSpin };
}
