import { store } from "./storage.js";
import { SYMBOLS, isWild, isScatter } from "./symbols.js";
import { DIM, spinGrid, evaluateLines, countScatters, isKronosTrigger } from "./engine.js";
import { newKronosBonusState, kronosBonusStep } from "./bonusKronos.js";

const BANKROLL_KEY = "winner_bankroll";
const DEFAULT_BANKROLL = 1000;
const CARRY_CENTS_KEY = "kronos_carry_cents";

const FS_TRIGGER = 4;           // keep free spins if you want (optional)
const BUY_RELIC_MULT = 80;      // buy price for Kronos bonus entry (tune)
const BIG_WIN_X = 35;

const $ = (id) => document.getElementById(id);

const els = {
  bankroll: $("bankroll"),
  resetBtn: $("resetBtn"),
  spinBtn: $("spinBtn"),
  autoBtn: $("autoBtn"),
  turboBtn: $("turboBtn"),
  buyBonusBtn: $("buyBonusBtn"),
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

let inBonus = false;
let bonusState = null;

// Money
function getBankroll(){ return store.loadNum(BANKROLL_KEY, DEFAULT_BANKROLL); }
function setBankroll(v){ store.saveNum(BANKROLL_KEY, Math.max(0, Math.floor(v))); }
function fmt(v){ return `$${Math.floor(v).toLocaleString()}`; }
function setStatus(t){ els.status.textContent = t; }
function sleep(ms){ return new Promise(r => setTimeout(r, ms)); }
function setTog(btn,on,a,b){ btn.classList.toggle("on",!!on); btn.textContent = on ? a : b; }

function getCarryCents(){
  const v = Number(localStorage.getItem(CARRY_CENTS_KEY));
  return Number.isFinite(v) ? Math.max(0, Math.floor(v)) : 0;
}
function setCarryCents(v){ localStorage.setItem(CARRY_CENTS_KEY, String(Math.max(0, Math.floor(v)))); }

function credit(winDollars){
  const cents = Math.max(0, Math.round(winDollars * 100));
  const carry = getCarryCents();
  const total = cents + carry;
  const dollars = Math.floor(total / 100);
  const newCarry = total % 100;
  if (dollars > 0) setBankroll(getBankroll() + dollars);
  setCarryCents(newCarry);
  return { dollars, newCarry };
}

function renderBank(){ els.bankroll.textContent = fmt(getBankroll()); }
function renderHUD(){
  els.fsCount.textContent = String(freeSpins);
  els.fsMult.textContent = String(freeMult);
}

function addHistory(text, good){
  const div = document.createElement("div");
  div.className = `hItem ${good ? "hGood" : "hBad"}`;
  div.textContent = text;
  els.history.prepend(div);
  while (els.history.children.length > 12) els.history.removeChild(els.history.lastChild);
}

function showBigWin(amount, bet){
  const x = amount / Math.max(1, bet);
  let title = "BIG WIN!";
  if (x >= 70) title = "MEGA WIN!";
  if (x >= 180) title = "UNLEASHED WIN!";
  els.bigWinTitle.textContent = title;
  els.bigWinAmt.textContent = `$${amount.toFixed(2)}`;
  els.bigWinSub.textContent = `${x.toFixed(1)}× your bet`;
  els.overlay.classList.add("on");
}
function hideBigWin(){ els.overlay.classList.remove("on"); }

// Grid render
function renderGrid(grid, winCells=null){
  els.grid.innerHTML = "";
  for (let r = 0; r < DIM.ROWS; r++){
    for (let c = 0; c < DIM.COLS; c++){
      const k = grid[c][r];
      const cell = document.createElement("div");
      cell.className = "cell";
      cell.textContent = SYMBOLS[k]?.name ?? " ";

      if (k === "KRONOS") cell.classList.add("kronos");
      if (isWild(k)) cell.classList.add("wild");

      if (winCells && winCells.has(`${c}-${r}`)) cell.classList.add("win");
      els.grid.appendChild(cell);
    }
  }
}

function renderRandomFrame(){
  const keys = Object.keys(SYMBOLS);
  const fake = Array.from({length:DIM.COLS}, () =>
    Array.from({length:DIM.ROWS}, () => keys[(Math.random()*keys.length)|0])
  );
  renderGrid(fake);
}

// ---------- Bonus UI ----------
function openBonus(on){ els.bonusOverlay.classList.toggle("on", !!on); }

function renderBonus(){
  if (!bonusState) return;

  els.bonusLeft.textContent = String(bonusState.left);
  els.bonusTotal.textContent = fmt(bonusState.total);

  els.bonusGrid.innerHTML = "";
  for (let r = 0; r < DIM.ROWS; r++){
    for (let c = 0; c < DIM.COLS; c++){
      const v = bonusState.grid[c][r];
      const cell = document.createElement("div");
      cell.className = "bonusCell" + (v ? " filled" : "");
      cell.textContent = v ? SYMBOLS.KRONOS.name : "";
      els.bonusGrid.appendChild(cell);
    }
  }
}

async function startBonus(bet, note){
  inBonus = true;
  autoplay = false;
  setTog(els.autoBtn, autoplay, "Autoplay: On", "Autoplay: Off");

  bonusState = newKronosBonusState(bet);
  els.bonusNote.textContent = note || "Kronos drops reset spins to 3.";
  els.bonusSpinBtn.disabled = false;
  els.bonusCloseBtn.disabled = true;

  openBonus(true);
  renderBonus();
  setStatus("⏳ KRONOS BONUS started!");
}

async function bonusRespin(){
  if (!inBonus || !bonusState) return;
  els.bonusSpinBtn.disabled = true;

  const step = kronosBonusStep(bonusState);
  renderBonus();

  if (step.hitCount > 0) {
    els.bonusNote.textContent = `KRONOS landed (${step.hitCount}) — spins reset to 3. +$${step.winNow.toFixed(2)} this respin`;
  } else {
    els.bonusNote.textContent = `No KRONOS… spins left: ${bonusState.left}. +$${step.winNow.toFixed(2)} this respin`;
  }

  await sleep(turbo ? 220 : 420);

  if (step.ended){
    const total = bonusState.total;
    const credited = credit(total);
    renderBank();

    els.lastWin.textContent = fmt(credited.dollars);
    addHistory(`Kronos Bonus win $${total.toFixed(2)} (credited ${fmt(credited.dollars)})`, true);
    setStatus(`Kronos Bonus ended. Total: $${total.toFixed(2)}`);

    els.bonusSpinBtn.disabled = true;
    els.bonusCloseBtn.disabled = false;
    return;
  }

  els.bonusSpinBtn.disabled = false;
}

function closeBonus(){
  openBonus(false);
  inBonus = false;
  bonusState = null;
}

// ---------- Spin ----------
async function spin({ forceBonus=false } = {}){
  if (spinning || inBonus) return;
  spinning = true;

  const bet = Math.floor(Number(els.betInput.value) || 1);
  if (bet < 1){ setStatus("Bet must be at least $1."); spinning=false; return; }

  const isFS = freeSpins > 0;

  if (forceBonus && isFS){
    setStatus("You can’t buy the Kronos bonus during free spins.");
    spinning=false;
    return;
  }

  // charge bet if not FS and not forced buy already handled
  if (!isFS && !forceBonus){
    if (bet > getBankroll()){
      setStatus("Not enough bankroll.");
      spinning=false;
      return;
    }
    setBankroll(getBankroll() - bet);
    renderBank();
  }

  // spin animation
  setStatus(isFS ? "Free Spin…" : "Spinning…");
  const spinTime = turbo ? 520 : 1200;
  const start = performance.now();
  while (performance.now() - start < spinTime){
    renderRandomFrame();
    await sleep(turbo ? 18 : 34);
  }

  let grid = spinGrid();
  renderGrid(grid);

  // Kronos Bonus trigger
  if (!isFS && (forceBonus || isKronosTrigger(grid))){
    spinning = false;
    await startBonus(bet, forceBonus ? `Bought Kronos Bonus for ${fmt(bet * BUY_RELIC_MULT)}`
                                    : `Triggered! First reel FULL of KRONOS.`);
    return;
  }

  // Line eval
  const res = evaluateLines(grid, bet);
  const scat = countScatters(grid);

  // Free spins (optional)
  if (!isFS && scat >= FS_TRIGGER){
    const add = scat === 4 ? 10 : scat === 5 ? 15 : 25;
    freeSpins += add;
    setStatus(`🌌 ${scat} scatters! Free Spins +${add}`);
    renderHUD();
  }

  // Apply FS multiplier if in FS
  const win = res.totalWin * (isFS ? freeMult : 1);

  if (win > 0){
    renderGrid(grid, res.winCells);
    await sleep(turbo ? 200 : 650);

    const credited = credit(win);
    renderBank();
    els.lastWin.textContent = fmt(credited.dollars);

    addHistory(`Win $${win.toFixed(2)} (${res.winningLines} line${res.winningLines===1?"":"s"})`, true);

    // FS multiplier ramps on any FS win
    if (isFS){
      freeMult += 1;
      renderHUD();
    }

    if (win >= bet * BIG_WIN_X) showBigWin(win, bet);
    else setStatus(`Win: $${win.toFixed(2)} • Lines: ${res.winningLines}`);
  } else {
    els.lastWin.textContent = "$0";
    addHistory(`Lost ${fmt(bet)}${isFS ? " (FS)" : ""}`, false);
    setStatus(isFS ? "No win (Free Spin)." : "No win.");
  }

  // consume FS
  if (isFS){
    freeSpins -= 1;
    if (freeSpins <= 0){
      freeSpins = 0;
      freeMult = 1;
    }
    renderHUD();
  }

  spinning = false;

  if (autoplay){
    const betNow = Math.floor(Number(els.betInput.value) || 1);
    if (freeSpins <= 0 && getBankroll() < betNow){
      autoplay = false;
      setTog(els.autoBtn, autoplay, "Autoplay: On", "Autoplay: Off");
      setStatus("Autoplay stopped: bankroll too low.");
      return;
    }
    await sleep(turbo ? 180 : 700);
    spin();
  }
}

// Controls
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

els.maxBtn.onclick = () => { els.betInput.value = String(getBankroll()); };

document.querySelectorAll(".chip").forEach(btn => {
  btn.addEventListener("click", () => {
    const chip = Number(btn.dataset.chip);
    const cur = Number(els.betInput.value) || 1;
    els.betInput.value = String(Math.max(1, Math.floor(cur + chip)));
  });
});

els.buyBonusBtn.onclick = async () => {
  if (spinning || inBonus) return;
  if (freeSpins > 0) { setStatus("Can’t buy Kronos Bonus during Free Spins."); return; }

  const bet = Math.floor(Number(els.betInput.value) || 1);
  const cost = bet * BUY_RELIC_MULT;
  if (cost > getBankroll()){
    setStatus(`Not enough bankroll. Cost: ${fmt(cost)}.`);
    return;
  }

  setBankroll(getBankroll() - cost);
  renderBank();

  await spin({ forceBonus: true });
};

els.bonusSpinBtn.onclick = bonusRespin;
els.bonusCloseBtn.onclick = closeBonus;
els.bonusOverlay.addEventListener("click", (e) => {
  if (e.target === els.bonusOverlay && !els.bonusCloseBtn.disabled) closeBonus();
});

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
els.overlay.addEventListener("click", (e) => { if (e.target === els.overlay) hideBigWin(); });

// Init
if (!Number.isFinite(Number(localStorage.getItem(BANKROLL_KEY)))) setBankroll(DEFAULT_BANKROLL);
if (!Number.isFinite(Number(localStorage.getItem(CARRY_CENTS_KEY)))) setCarryCents(0);

renderBank();
renderHUD();
els.lastWin.textContent = "$0";
setStatus("Ready.");
renderGrid(spinGrid());
