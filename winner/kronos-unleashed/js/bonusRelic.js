export const RELIC_DIM = { COLS: 6, ROWS: 5, CELLS: 30 };

export function newRelicState(bet) {
  return {
    bet,
    left: 3,
    total: 0,
    spins: 0,
    filled: Array(RELIC_DIM.CELLS).fill(null), // null or {kind,value} / {kind:"jp",name,value}
    jackpots: { mini:false, minor:false, major:false, grand:false },
  };
}

const MONEY_MULTS = [
  { mult: 1.0, w: 40 },
  { mult: 1.5, w: 22 },
  { mult: 2.0, w: 16 },
  { mult: 3.0, w: 10 },
  { mult: 5.0, w: 6 },
  { mult: 10,  w: 3 },
  { mult: 20,  w: 1.4 },
  { mult: 50,  w: 0.5 },
  { mult: 100, w: 0.1 },
];

function pickWeighted(list) {
  const total = list.reduce((a, x) => a + x.w, 0);
  let r = Math.random() * total;
  for (const x of list) { r -= x.w; if (r <= 0) return x; }
  return list[0];
}

function openSlots(state) {
  const out = [];
  for (let i = 0; i < state.filled.length; i++) if (state.filled[i] == null) out.push(i);
  return out;
}
function isFull(state){ return openSlots(state).length === 0; }

function ballChance(state) {
  const empty = openSlots(state).length;
  const filled = RELIC_DIM.CELLS - empty;
  const fillRatio = filled / RELIC_DIM.CELLS;
  return Math.max(0.16, 0.46 - fillRatio * 0.26);
}

function jackpotDefs(bet) {
  return [
    { key:"mini",  name:"MINI",  mult:5,  w:0.30 },
    { key:"minor", name:"MINOR", mult:10, w:0.14 },
    { key:"major", name:"MAJOR", mult:50, w:0.03 },
  ].map(x => ({ ...x, value: Math.round(bet * x.mult) }));
}
function jackpotAttemptChance(state) {
  const filled = RELIC_DIM.CELLS - openSlots(state).length;
  const ratio = filled / RELIC_DIM.CELLS;
  return 0.010 + ratio * 0.010;
}
function pickJackpot(state) {
  const defs = jackpotDefs(state.bet).filter(d => !state.jackpots[d.key]);
  if (!defs.length) return null;
  const d = pickWeighted(defs);
  return d;
}
function pickMoneyValue(bet) {
  const d = pickWeighted(MONEY_MULTS);
  return Math.round(bet * d.mult);
}

export function relicStep(state) {
  state.spins++;

  const empties = openSlots(state);
  if (!empties.length) return { hitCount:0, placements:[], ended:true, full:true, awardedGrand:false };

  const chance = ballChance(state);
  let hitCount = 0;
  const placements = [];

  const attempts = 3;
  for (let a = 0; a < attempts; a++) {
    const emptiesNow = openSlots(state);
    if (!emptiesNow.length) break;

    const p = chance * (a === 0 ? 1 : a === 1 ? 0.35 : 0.15);
    if (Math.random() > p) continue;

    const idx = emptiesNow[(Math.random() * emptiesNow.length) | 0];

    let placed = null;
    if (Math.random() < jackpotAttemptChance(state)) {
      const jp = pickJackpot(state);
      if (jp) {
        state.jackpots[jp.key] = true;
        placed = { kind:"jp", name:jp.name, value:jp.value, key:jp.key };
      }
    }
    if (!placed) placed = { kind:"money", value: pickMoneyValue(state.bet) };

    state.filled[idx] = placed;
    state.total += placed.value;
    hitCount++;
    placements.push({ idx, ...placed });
  }

  if (hitCount > 0) state.left = 3;
  else state.left -= 1;

  let awardedGrand = false;
  if (isFull(state) && !state.jackpots.grand) {
    const grandValue = Math.round(state.bet * 1000);
    state.jackpots.grand = true;
    state.total += grandValue;
    awardedGrand = true;
  }

  const ended = state.left <= 0 || isFull(state);
  return { hitCount, placements, ended, full:isFull(state), awardedGrand };
}
