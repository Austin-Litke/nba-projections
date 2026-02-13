import { store } from "./storage.js";

const BANKROLL_KEY = "winner_bankroll"; // ✅ matches your slot state snippet
const DEFAULT_BANKROLL = 1000;

const $ = (id) => document.getElementById(id);

const els = {
  bankroll: $("bankroll"),
  resetBtn: $("resetBtn"),
  roundStatus: $("roundStatus"),
  multVal: $("multVal"),
  plane: $("plane"),
  boom: $("boom"),
  history: $("history"),
  betInput: $("betInput"),
  maxBtn: $("maxBtn"),
  startBtn: $("startBtn"),
  cashoutBtn: $("cashoutBtn"),
  msg: $("msg"),
  chips: Array.from(document.querySelectorAll(".chip")),
};

const state = {
  running: false,
  crashed: false,
  cashed: false,
  bet: 10,
  mult: 1.0,
  crashAt: 0,
  t0: 0,
  raf: 0,
  history: [],
};

function getBankroll(){
  return store.loadNum(BANKROLL_KEY, DEFAULT_BANKROLL);
}
function setBankroll(v){
  store.saveNum(BANKROLL_KEY, Math.max(0, Math.floor(v)));
}
function fmtMoney(v){
  const n = Math.floor(Number(v) || 0);
  return `$${n.toLocaleString()}`;
}

function clamp(n, a, b){ return Math.max(a, Math.min(b, n)); }

function refreshBankroll(){
  els.bankroll.textContent = fmtMoney(getBankroll());
}

function setMessage(text, tone="muted"){
  els.msg.className = "muted small";
  els.msg.textContent = text;
  if (tone === "good") els.msg.style.color = "var(--good)";
  else if (tone === "bad") els.msg.style.color = "var(--bad)";
  else els.msg.style.color = "";
}

function setMultiplier(x){
  els.multVal.textContent = `${x.toFixed(2)}×`;
}

function resetVisuals(){
  els.boom.style.display = "none";
  els.plane.style.opacity = "1";
  els.plane.textContent = "✈️";
  els.plane.style.transform = `translate(0px, 0px) rotate(0deg)`;
}

function renderHistory(){
  els.history.innerHTML = "";
  for (const h of state.history.slice(0, 10)){
    const div = document.createElement("div");
    div.className = `hItem ${h.result === "cashout" ? "hGood" : "hBad"}`;
    const left = h.result === "cashout"
      ? `Cashed @ ${h.cashoutAt.toFixed(2)}×`
      : `Crashed @ ${h.crashAt.toFixed(2)}×`;
    const right = h.result === "cashout"
      ? `+${fmtMoney(h.payout)}`
      : `-${fmtMoney(h.bet)}`;
    div.innerHTML = `<div>${left}</div><b>${right}</b>`;
    els.history.appendChild(div);
  }
}

function readBet(){
  const v = Number(els.betInput.value);
  if (!Number.isFinite(v)) return 1;
  return Math.floor(clamp(v, 1, 1_000_000));
}

// Crash distribution: low crashes common; big multipliers rare
function sampleCrashPoint(){
  const r = Math.random();
  if (r < 0.92){
    const u = Math.random();
    const x = 1.05 + (-Math.log(1 - u)) * 0.9;
    return clamp(x, 1.05, 6.0);
  } else {
    const u = Math.random();
    const x = 6 + (-Math.log(1 - u)) * 6.0;
    return clamp(x, 6.0, 30.0);
  }
}

function multiplierAt(tSec){
  const p = 1.35;
  const k = 0.22;
  return 1 + Math.pow(tSec, p) * k;
}

function updateFrame(now){
  if (!state.running) return;

  const t = (now - state.t0) / 1000;
  state.mult = multiplierAt(t);

  setMultiplier(state.mult);

  const x = clamp(t * 120, 0, 520);
  const y = clamp(t * 40, 0, 180);
  const rot = clamp(t * 6, 0, 18);
  els.plane.style.transform = `translate(${x}px, ${-y}px) rotate(${rot}deg)`;

  if (state.mult >= state.crashAt){
    crash();
    return;
  }

  state.raf = requestAnimationFrame(updateFrame);
}

function startRound(){
  if (state.running) return;

  const bet = readBet();
  const bank = getBankroll();

  if (bet > bank){
    setMessage("Not enough money for that bet.", "bad");
    return;
  }

  setBankroll(bank - bet);
  refreshBankroll();

  state.bet = bet;
  state.running = true;
  state.cashed = false;
  state.crashed = false;
  state.mult = 1.0;
  state.crashAt = sampleCrashPoint();
  state.t0 = performance.now();

  resetVisuals();
  setMultiplier(1.0);

  els.roundStatus.textContent = "Flying… tap Cash Out!";
  els.startBtn.disabled = true;
  els.cashoutBtn.disabled = false;

  setMessage(`Bet ${fmtMoney(bet)}. Good luck…`);
  state.raf = requestAnimationFrame(updateFrame);
}

function cashOut(){
  if (!state.running || state.cashed || state.crashed) return;

  state.cashed = true;
  state.running = false;
  cancelAnimationFrame(state.raf);

  const cashoutAt = state.mult;
  const payout = Math.floor(state.bet * cashoutAt);

  setBankroll(getBankroll() + payout);
  refreshBankroll();

  els.roundStatus.textContent = `Cashed out at ${cashoutAt.toFixed(2)}× (would’ve crashed at ${state.crashAt.toFixed(2)}×)`;

  els.startBtn.disabled = false;
  els.cashoutBtn.disabled = true;

 setMessage(`Cashed out! +${fmtMoney(payout)} (crash was ${state.crashAt.toFixed(2)}×)`, "good");


  state.history.unshift({
    result: "cashout",
    bet: state.bet,
    cashoutAt,
    crashAt: state.crashAt,
    payout
  });
  renderHistory();
}

function crash(){
  if (!state.running) return;

  state.running = false;
  state.crashed = true;
  cancelAnimationFrame(state.raf);

  els.boom.style.display = "block";

  const rect = els.plane.getBoundingClientRect();
  const skyRect = els.plane.parentElement.getBoundingClientRect();
  const cx = rect.left - skyRect.left + rect.width/2;
  const cy = rect.top - skyRect.top + rect.height/2;
  els.boom.style.left = `${cx}px`;
  els.boom.style.top = `${cy}px`;

  els.plane.style.opacity = "0.25";
  els.roundStatus.textContent = `CRASHED at ${state.crashAt.toFixed(2)}×`;

  els.startBtn.disabled = false;
  els.cashoutBtn.disabled = true;

  setMessage(`Ouch. You lost ${fmtMoney(state.bet)}.`, "bad");

  state.history.unshift({
    result: "crash",
    bet: state.bet,
    crashAt: state.crashAt,
    payout: 0
  });
  renderHistory();
}

/* ---------------- UI wiring ---------------- */

els.chips.forEach(btn => {
  btn.addEventListener("click", () => {
    const chip = Number(btn.dataset.chip);
    const cur = readBet();
    els.betInput.value = String(cur + chip);
  });
});

els.maxBtn.addEventListener("click", () => {
  els.betInput.value = String(getBankroll());
});

els.startBtn.addEventListener("click", startRound);
els.cashoutBtn.addEventListener("click", cashOut);

els.resetBtn.addEventListener("click", () => {
  // If a round is running, stop it cleanly
  if (state.running){
    state.running = false;
    cancelAnimationFrame(state.raf);
  }

  setBankroll(DEFAULT_BANKROLL);
  refreshBankroll();

  // Reset UI
  state.history = [];
  renderHistory();
  resetVisuals();
  setMultiplier(1.0);
  els.roundStatus.textContent = "Waiting…";
  els.startBtn.disabled = false;
  els.cashoutBtn.disabled = true;
  setMessage("Bankroll reset to $1000.");
});

/* ---------------- init ---------------- */

// IMPORTANT: make sure the shared bankroll exists (some games only create it after first load)
if (!Number.isFinite(Number(localStorage.getItem(BANKROLL_KEY)))){
  setBankroll(getBankroll()); // writes default if missing
}

refreshBankroll();
setMultiplier(1.0);
renderHistory();
setMessage("Place a bet and start.");
