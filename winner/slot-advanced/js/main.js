import { store } from "./storage.js";
import { spinGrid, evaluateWays, applyCascade } from "./slotEngine.js";
import { SYMBOLS } from "./symbols.js";
import { newHoldSpinState, holdSpinStep, HOLDSPIN_DIM } from "./bonusHoldSpin.js";

const BANKROLL_KEY = "winner_bankroll";
const DEFAULT_BANKROLL = 1000;

// Keep cents accuracy locally (bankroll stays whole dollars)
const CARRY_CENTS_KEY = "slotadv_carry_cents";

// Bonus config
const BUY_BONUS_MULT = 75;      // buy price = bet * 75
const BONUS_TRIGGER_COUNT = 3;  // 3+ BONUS symbols triggers bonus

const $ = (id) => document.getElementById(id);

const els = {
  bankroll: $("bankroll"),
  resetBtn: $("resetBtn"),
  spinBtn: $("spinBtn"),
  autoBtn: $("autoBtn"),
  turboBtn: $("turboBtn"),
  betInput: $("betInput"),
  maxBtn: $("maxBtn"),
  grid: $("grid"),
  status: $("status"),
  history: $("history"),

  fsCount: $("fsCount"),
  fsMult: $("fsMult"),
  lastWin: $("lastWin"),

  overlay: $("overlay"),
  bigWinTitle: $("bigWinTitle"),
  bigWinAmt: $("bigWinAmt"),
  bigWinSub: $("bigWinSub"),
  closeOverlayBtn: $("closeOverlayBtn"),

  // Bonus UI (must exist in index.html or these will be null)
  buyBonusBtn: $("buyBonusBtn"),
  bonusOverlay: $("bonusOverlay"),
  bonusLeft: $("bonusLeft"),
  bonusTotal: $("bonusTotal"),
  bonusGrid: $("bonusGrid"),
  bonusSpinBtn: $("bonusSpinBtn"),
  bonusCloseBtn: $("bonusCloseBtn"),
  bonusNote: $("bonusNote"),
};

let freeSpins = 0;
let freeMult = 1;
let autoplay = false;
let turbo = false;
let spinning = false;

// Bonus runtime
let inBonus = false;
let bonusState = null;

// ---------- Money ----------
function getBankroll() {
  return store.loadNum(BANKROLL_KEY, DEFAULT_BANKROLL);
}
function setBankroll(v) {
  store.saveNum(BANKROLL_KEY, Math.max(0, Math.floor(v)));
}
function fmt(v) {
  return `$${Math.floor(v).toLocaleString()}`;
}

function getCarryCents() {
  const v = Number(localStorage.getItem(CARRY_CENTS_KEY));
  return Number.isFinite(v) ? Math.max(0, Math.floor(v)) : 0;
}
function setCarryCents(v) {
  localStorage.setItem(CARRY_CENTS_KEY, String(Math.max(0, Math.floor(v))));
}

// Credit winnings accurately while bankroll remains whole dollars.
// Returns how much got credited + carry remainder.
function creditWinningsDollarsFloat(winDollars) {
  const cents = Math.max(0, Math.round(winDollars * 100));
  const carry = getCarryCents();
  const total = cents + carry;

  const dollarsToCredit = Math.floor(total / 100);
  const newCarry = total % 100;

  if (dollarsToCredit > 0) setBankroll(getBankroll() + dollarsToCredit);
  setCarryCents(newCarry);

  return { dollarsToCredit, newCarryCents: newCarry, totalCentsWon: cents };
}

function renderBank() {
  els.bankroll.textContent = fmt(getBankroll());
}

// ---------- UI helpers ----------
function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function setStatus(t) {
  els.status.textContent = t;
}

function setTog(btn, on, onText, offText) {
  btn.classList.toggle("on", !!on);
  btn.textContent = on ? onText : offText;
}

function renderHUD() {
  els.fsCount.textContent = String(freeSpins);
  els.fsMult.textContent = String(freeMult);
}

function showBigWin(amount, bet) {
  let title = "BIG WIN!";
  const x = amount / Math.max(1, bet);

  if (x >= 40) title = "MEGA WIN!";
  if (x >= 100) title = "LEGENDARY WIN!";

  els.bigWinTitle.textContent = title;
  els.bigWinAmt.textContent = `$${amount.toFixed(2)}`;
  els.bigWinSub.textContent = `${x.toFixed(1)}× your bet`;

  els.overlay.classList.add("on");
}
function hideBigWin() {
  els.overlay.classList.remove("on");
}

// ---------- History ----------
function addHistory(text, good) {
  const div = document.createElement("div");
  div.className = `hItem ${good ? "hGood" : "hBad"}`;
  div.innerHTML = `<div>${text}</div>`;
  els.history.prepend(div);
  while (els.history.children.length > 10) {
    els.history.removeChild(els.history.lastChild);
  }
}

// ---------- Rendering ----------
function renderGrid(grid, winCells = null) {
  els.grid.innerHTML = "";
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 5; c++) {
      const cell = document.createElement("div");
      const key = grid[c][r];
      cell.className = "cell";
      cell.dataset.col = String(c);
      cell.textContent = SYMBOLS[key].name;

      if (winCells && winCells.has(`${c}-${r}`)) {
        cell.classList.add("win");
      }

      els.grid.appendChild(cell);
    }
  }
}

function renderRandomSpinFrame() {
  const keys = Object.keys(SYMBOLS);
  const fake = [];
  for (let c = 0; c < 5; c++) {
    const col = [];
    for (let r = 0; r < 3; r++) {
      col.push(keys[(Math.random() * keys.length) | 0]);
    }
    fake.push(col);
  }
  renderGrid(fake);
}

function setColSpinning(col, on) {
  els.grid.querySelectorAll(`.cell[data-col="${col}"]`).forEach((el) => {
    el.classList.toggle("colSpin", !!on);
  });
}

// ---------- Payout shaping ----------
const CASCADE_EXP_BASE = 1.9;
const BIG_WIN_THRESHOLD_X = 25;

function applyCascadeBonus(totalWinRaw, cascades, bet, isFreeSpin) {
  if (cascades <= 0) return totalWinRaw;

  const guarantee = bet * Math.pow(CASCADE_EXP_BASE, cascades - 1);
  if (isFreeSpin) return Math.max(totalWinRaw, 0);
  return Math.max(totalWinRaw, guarantee);
}

// ---------- BONUS helpers ----------
function countBonusSymbols(grid) {
  let n = 0;
  for (let c = 0; c < 5; c++) {
    for (let r = 0; r < 3; r++) {
      const k = grid[c][r];
      if (SYMBOLS[k] && SYMBOLS[k].bonus) n++;
    }
  }
  return n;
}

function openBonusOverlay(on) {
  if (!els.bonusOverlay) return;
  els.bonusOverlay.classList.toggle("on", !!on);
}

function renderBonusUI() {
  if (!bonusState || !els.bonusGrid) return;

  els.bonusLeft.textContent = String(bonusState.left);
  els.bonusTotal.textContent = fmt(bonusState.total);

  els.bonusGrid.innerHTML = "";
  for (let i = 0; i < HOLDSPIN_DIM.CELLS; i++) {
    const cell = document.createElement("div");
    const v = bonusState.filled[i];
    cell.className = "bonusCell" + (v != null ? " filled" : "");
    cell.textContent = (v != null) ? `$${v}` : "";
    els.bonusGrid.appendChild(cell);
  }
}

async function startHoldSpinBonus(bet, reasonText) {
  inBonus = true;
  autoplay = false; // pause autoplay during bonus
  setTog(els.autoBtn, autoplay, "Autoplay: On", "Autoplay: Off");

  bonusState = newHoldSpinState(bet);

  if (els.bonusNote) els.bonusNote.textContent = reasonText || "";
  if (els.bonusCloseBtn) els.bonusCloseBtn.disabled = true;

  openBonusOverlay(true);
  renderBonusUI();
  setStatus("🟣 Hold & Spin Bonus started!");
}

async function doBonusRespin() {
  if (!bonusState || !inBonus) return;
  if (!els.bonusSpinBtn) return;

  els.bonusSpinBtn.disabled = true;

  const step = holdSpinStep(bonusState);
  renderBonusUI();

  if (els.bonusNote) {
    els.bonusNote.textContent =
      step.hitCount > 0
        ? `Hit ${step.hitCount} ball${step.hitCount === 1 ? "" : "s"}! Spins reset to 3.`
        : `No hit… spins left: ${bonusState.left}`;
  }

  await sleep(turbo ? 250 : 450);

  if (step.ended) {
    // Bonus ends: pay total
    const total = bonusState.total;
    const credited = creditWinningsDollarsFloat(total);
    renderBank();

    els.lastWin.textContent = fmt(credited.dollarsToCredit);
    addHistory(`Bonus win ${fmt(credited.dollarsToCredit)} (Hold & Spin)`, true);

    setStatus(`Bonus ended. Won $${total.toFixed(2)} (credited ${fmt(credited.dollarsToCredit)}).`);

    if (els.bonusCloseBtn) els.bonusCloseBtn.disabled = false;
    if (els.bonusSpinBtn) els.bonusSpinBtn.disabled = true;

    return;
  }

  // Continue
  els.bonusSpinBtn.disabled = false;
}

function closeBonus() {
  if (!inBonus) return;
  openBonusOverlay(false);
  inBonus = false;
  bonusState = null;

  // resume autoplay only if user manually turns it back on
}

// ---------- Spin ----------
async function spin({ forceBonus = false } = {}) {
  if (spinning || inBonus) return;
  spinning = true;

  const bet = Math.floor(Number(els.betInput.value) || 1);
  if (bet < 1) {
    setStatus("Bet must be at least $1.");
    spinning = false;
    return;
  }

  const isFreeSpin = freeSpins > 0;

  // buying/forcing bonus not allowed during free spins
  if (forceBonus && isFreeSpin) {
    setStatus("You can’t buy the bonus during free spins.");
    spinning = false;
    return;
  }

  // charge bet only if NOT in free spins
  if (!isFreeSpin) {
    if (bet > getBankroll()) {
      setStatus("Not enough bankroll.");
      spinning = false;
      return;
    }
    setBankroll(getBankroll() - bet);
    renderBank();
  }

  // --- Reel spin animation ---
  setStatus(isFreeSpin ? "Free Spin…" : "Spinning…");
  els.grid.classList.add("spinning");

  const spinTime = turbo ? 650 : 1350;
  const stopGap = turbo ? 140 : 260;

  const start = performance.now();
  for (let c = 0; c < 5; c++) setColSpinning(c, true);

  let rafRun = true;
  const raf = () => {
    if (!rafRun) return;
    renderRandomSpinFrame();
    if (performance.now() - start < spinTime + stopGap * 5) {
      requestAnimationFrame(raf);
    }
  };
  requestAnimationFrame(raf);

  for (let c = 0; c < 5; c++) {
    await sleep(stopGap);
    setColSpinning(c, false);
  }

  rafRun = false;
  els.grid.classList.remove("spinning");

  // Final grid
  let grid = spinGrid();
  renderGrid(grid);

  // --- BONUS trigger (base grid) ---
  if (!isFreeSpin) {
    const bcount = countBonusSymbols(grid);
    if (forceBonus || bcount >= BONUS_TRIGGER_COUNT) {
      spinning = false;

      await startHoldSpinBonus(
        bet,
        forceBonus
          ? `Bought bonus for ${fmt(bet * BUY_BONUS_MULT)}`
          : `Triggered with ${bcount} bonus symbols!`
      );

      // Enable respin button
      if (els.bonusSpinBtn) els.bonusSpinBtn.disabled = false;
      return;
    }
  }

  // --- Evaluate + true cascades ---
  let cascades = 0;
  let totalWinRaw = 0;

  const spinBaseMult = isFreeSpin ? freeMult : 1;

  while (true) {
    const res = evaluateWays(grid, bet);

    if (res.totalWin <= 0) {
      if (res.scatters >= 3) {
        const addFS = res.scatters === 3 ? 8 : res.scatters === 4 ? 12 : 18;
        freeSpins += addFS;
        setStatus(`🔥 ${res.scatters} scatters! Free Spins +${addFS}`);
        renderHUD();
      }
      break;
    }

    cascades++;
    totalWinRaw += res.totalWin * spinBaseMult;

    renderGrid(grid, res.winCells);
    await sleep(turbo ? 200 : 650);

    grid = applyCascade(grid, res.winCells);
    renderGrid(grid);
    await sleep(turbo ? 170 : 420);

    if (isFreeSpin) {
      freeMult += 1;
      renderHUD();
    }
  }

  const totalWinFinal = applyCascadeBonus(totalWinRaw, cascades, bet, isFreeSpin);

  // Pay out
  if (totalWinFinal > 0) {
    const credited = creditWinningsDollarsFloat(totalWinFinal);
    renderBank();

    els.lastWin.textContent = fmt(credited.dollarsToCredit);

    addHistory(
      `Won ${fmt(credited.dollarsToCredit)} (${cascades} cascade${cascades === 1 ? "" : "s"})`,
      true
    );

    if (totalWinFinal >= bet * BIG_WIN_THRESHOLD_X) {
      showBigWin(totalWinFinal, bet);
    } else {
      setStatus(
        `Win: $${totalWinFinal.toFixed(2)} (${cascades} cascade${cascades === 1 ? "" : "s"})`
      );
    }
  } else {
    els.lastWin.textContent = "$0";
    addHistory(`Lost ${fmt(bet)}${isFreeSpin ? " (free spin)" : ""}`, false);
    setStatus(isFreeSpin ? "No win (free spin)." : "No win.");
  }

  // Consume a free spin AFTER spin ends
  if (isFreeSpin) {
    freeSpins -= 1;
    if (freeSpins <= 0) {
      freeSpins = 0;
      freeMult = 1;
    }
    renderHUD();
  } else {
    renderHUD();
  }

  spinning = false;

  // Autoplay
  if (autoplay) {
    const betNow = Math.floor(Number(els.betInput.value) || 1);
    if (freeSpins <= 0 && getBankroll() < betNow) {
      autoplay = false;
      setTog(els.autoBtn, autoplay, "Autoplay: On", "Autoplay: Off");
      setStatus("Autoplay stopped: bankroll too low.");
      return;
    }

    await sleep(turbo ? 220 : 900);
    spin();
  }
}

// ---------- Controls ----------
els.spinBtn.onclick = () => spin();

els.autoBtn.onclick = () => {
  if (inBonus) return;
  autoplay = !autoplay;
  setTog(els.autoBtn, autoplay, "Autoplay: On", "Autoplay: Off");
  if (autoplay && !spinning) spin();
};

els.turboBtn.onclick = () => {
  turbo = !turbo;
  setTog(els.turboBtn, turbo, "Turbo: On", "Turbo: Off");
};

els.maxBtn.onclick = () => {
  els.betInput.value = String(getBankroll());
};

document.querySelectorAll(".chip").forEach((btn) => {
  btn.addEventListener("click", () => {
    const chip = Number(btn.dataset.chip);
    const cur = Number(els.betInput.value) || 1;
    els.betInput.value = String(Math.max(1, Math.floor(cur + chip)));
  });
});

if (els.buyBonusBtn) {
  els.buyBonusBtn.onclick = async () => {
    if (spinning || inBonus) return;

    const bet = Math.floor(Number(els.betInput.value) || 1);
    const cost = bet * BUY_BONUS_MULT;

    if (freeSpins > 0) {
      setStatus("You can’t buy the bonus during free spins.");
      return;
    }
    if (cost > getBankroll()) {
      setStatus(`Not enough bankroll to buy bonus. Cost: ${fmt(cost)}.`);
      return;
    }

    setBankroll(getBankroll() - cost);
    renderBank();

    // Start bonus (uses bet to set ball values)
    await startHoldSpinBonus(bet, `Bought bonus for ${fmt(cost)}.`);
    if (els.bonusSpinBtn) els.bonusSpinBtn.disabled = false;
  };
}

// Bonus buttons
if (els.bonusSpinBtn) els.bonusSpinBtn.onclick = doBonusRespin;
if (els.bonusCloseBtn) els.bonusCloseBtn.onclick = closeBonus;
if (els.bonusOverlay) {
  els.bonusOverlay.addEventListener("click", (e) => {
    if (e.target === els.bonusOverlay && els.bonusCloseBtn && !els.bonusCloseBtn.disabled) {
      closeBonus();
    }
  });
}

els.resetBtn.onclick = () => {
  setBankroll(DEFAULT_BANKROLL);
  setCarryCents(0);

  freeSpins = 0;
  freeMult = 1;
  autoplay = false;
  spinning = false;

  if (inBonus) closeBonus();

  setTog(els.autoBtn, autoplay, "Autoplay: On", "Autoplay: Off");

  renderBank();
  renderHUD();
  els.lastWin.textContent = "$0";
  setStatus("Bankroll reset to $1000.");
};

els.closeOverlayBtn.onclick = hideBigWin;
els.overlay.addEventListener("click", (e) => {
  if (e.target === els.overlay) hideBigWin();
});

// ---------- Init ----------
if (!Number.isFinite(Number(localStorage.getItem(BANKROLL_KEY)))) {
  setBankroll(DEFAULT_BANKROLL);
}
if (!Number.isFinite(Number(localStorage.getItem(CARRY_CENTS_KEY)))) {
  setCarryCents(0);
}

renderBank();
renderHUD();
els.lastWin.textContent = "$0";
setStatus("Ready.");
renderGrid(spinGrid());
