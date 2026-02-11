import { store } from "./storage.js";
import { EURO_WHEEL, colorOf, dozenOf } from "./roulette_data.js";
import {
  setMessage, pulseChip, updateHud, setButtons,
  showNumberPick, renderWheel, renderHistory
} from "./ui.js";

function clampInt(n, min, max){
  n = Math.floor(Number(n));
  if (!Number.isFinite(n)) return min;
  return Math.max(min, Math.min(max, n));
}

function sleep(ms){ return new Promise(r => setTimeout(r, ms)); }

// Normalize to [0, 360)
function norm360(deg){
  return ((deg % 360) + 360) % 360;
}

// Smallest signed angle difference in degrees (-180..180]
function shortestDelta(target, current){
  let d = norm360(target - current);
  if (d > 180) d -= 360;
  return d;
}

function randBetween(min, max){
  return min + Math.random() * (max - min);
}

export function createRouletteGame(els){
  const state = {
    bankroll: store.loadNum("winner_bankroll", 1000), // shared bankroll
    bet: store.loadNum("roulette_bet", 10),
    lastWin: 0,
    spinning: false,
    history: [],
    wheelAngle: store.loadNum("roulette_angle", 0),
    ballAngle: store.loadNum("roulette_ball_angle", 0),
  };

  function persist(){
    store.saveNum("winner_bankroll", state.bankroll);
    store.saveNum("roulette_bet", state.bet);
    store.saveNum("roulette_angle", state.wheelAngle);
    store.saveNum("roulette_ball_angle", state.ballAngle);
  }

  function clampBet(){
    state.bet = clampInt(state.bet, 1, Math.max(1, state.bankroll));
    els.betInput.value = state.bet;
  }

  function setBetFromInput(){
    state.bet = clampInt(els.betInput.value, 1, 999999);
    clampBet();
    updateHud(els, state);
    persist();
  }

  function setMaxBet(){
    state.bet = Math.max(1, state.bankroll);
    els.betInput.value = state.bet;
    updateHud(els, state);
    persist();
  }

  function resetMoney(){
    state.bankroll = 1000;
    state.bet = 10;
    state.lastWin = 0;
    els.betInput.value = state.bet;
    updateHud(els, state);
    setMessage(els, "Reset bankroll to $1000.");
    pulseChip(els, 0);
    persist();
  }

  function currentBetSpec(){
    const type = els.betType.value;
    const pick = clampInt(els.numberPick.value, 0, 36);
    return { type, pick };
  }

  function payoutMultiplier(resultNum, betSpec){
    const { type, pick } = betSpec;

    if (type === "number") return resultNum === pick ? 35 : 0;
    if (resultNum === 0) return 0;

    if (type === "red")   return colorOf(resultNum) === "red" ? 1 : 0;
    if (type === "black") return colorOf(resultNum) === "black" ? 1 : 0;
    if (type === "even")  return resultNum % 2 === 0 ? 1 : 0;
    if (type === "odd")   return resultNum % 2 === 1 ? 1 : 0;

    const d = dozenOf(resultNum);
    if (type === "dozen1") return d === 1 ? 2 : 0;
    if (type === "dozen2") return d === 2 ? 2 : 0;
    if (type === "dozen3") return d === 3 ? 2 : 0;

    return 0;
  }

  function pushHistory(num){
    state.history.unshift({ num: String(num), color: colorOf(num) });
    state.history = state.history.slice(0, 12);
    renderHistory(els, state.history);
  }

  const N = EURO_WHEEL.length;
  const STEP = 360 / N;

  // Compute which pocket is under the ball (using nearest pocket)
function pocketUnderBall(){
  const n = EURO_WHEEL.length;
  const step = 360 / n;

  // Relative angle from wheel to ball
  const rel = norm360(state.ballAngle - state.wheelAngle);

  // Convert angle -> nearest pocket index
  let i = Math.floor((rel + step / 2) / step) % n;

  // ✅ Calibration: your result is 9 pockets clockwise from the ball.
  // To correct that, shift index 9 pockets counter-clockwise.
  const OFFSET_POCKETS = 9;
  i = (i - OFFSET_POCKETS + n) % n;

  return i;
}


  // Align the wheel so pocketIndex is EXACTLY under the ball (no guessing)
//   function settleWheelToPocket(pocketIndex, durationMs = 200){
//     const targetWheelAngle = state.ballAngle - pocketIndex * STEP; // exact alignment condition
//     const delta = shortestDelta(targetWheelAngle, state.wheelAngle);
//     state.wheelAngle = state.wheelAngle + delta;

//     els.wheelInner.style.transition = `transform ${durationMs}ms ease-out`;
//     els.wheelInner.style.transform = `rotate(${state.wheelAngle}deg)`;
//   }

  function animateSpin(durationMs){
    // Make ball end somewhere random (NOT always top)
    const ballExtra = 10 * 360 + randBetween(0, 360);
    const ballStopOffset = randBetween(-STEP * 0.45, STEP * 0.45);
    const ballEnd = state.ballAngle - ballExtra + ballStopOffset;

    // Wheel spins too; it doesn't "decide" the result, it just spins with flair.
    // We'll settle it after.
    const wheelExtra = 7 * 360 + randBetween(0, 360);
    const wheelEnd = state.wheelAngle + wheelExtra + randBetween(-180, 180);

    state.ballAngle = ballEnd;
    state.wheelAngle = wheelEnd;

    els.ballRing.style.transition = `transform ${durationMs}ms cubic-bezier(.12,.78,.1,1)`;
    els.wheelInner.style.transition = `transform ${durationMs}ms cubic-bezier(.12,.78,.1,1)`;

    els.ballRing.style.transform = `rotate(${ballEnd}deg)`;
    els.wheelInner.style.transform = `rotate(${wheelEnd}deg)`;
  }

 async function spin(){
  if (state.spinning) return;

  clampBet();
  updateHud(els, state);

  if (state.bet > state.bankroll){
    setMessage(els, "Not enough bankroll for that bet.", "bad");
    return;
  }

  const betSpec = currentBetSpec();

  state.spinning = true;
  state.lastWin = 0;
  setButtons(els, false);

  // Take bet
  state.bankroll -= state.bet;
  pulseChip(els, -state.bet);
  updateHud(els, state);
  setMessage(els, "Spinning...");

  const duration = 3300;

  // 🔥 RANDOM SPIN (no pre-picked result)
  const ballExtra = 10 * 360 + Math.random() * 360;
  const wheelExtra = 7 * 360 + Math.random() * 360;

  state.ballAngle -= ballExtra;
  state.wheelAngle += wheelExtra;

  // Apply animation
  els.ballRing.style.transition =
    `transform ${duration}ms cubic-bezier(.12,.78,.1,1)`;

  els.wheelInner.style.transition =
    `transform ${duration}ms cubic-bezier(.12,.78,.1,1)`;

  els.ballRing.style.transform =
    `rotate(${state.ballAngle}deg)`;

  els.wheelInner.style.transform =
    `rotate(${state.wheelAngle}deg)`;

  // Wait for animation to fully finish
  await sleep(duration + 80);

  // ✅ Now determine which pocket is under the ball
  const pocketIndex = pocketUnderBall();
  const resultNum = EURO_WHEEL[pocketIndex];

  // Calculate payout
  const mult = payoutMultiplier(resultNum, betSpec);
  const winTotal = mult > 0 ? state.bet * (mult + 1) : 0;

  if (winTotal > 0){
    state.bankroll += winTotal;
    state.lastWin = winTotal - state.bet; // profit
    pulseChip(els, +winTotal);
    setMessage(
      els,
      `WIN! Ball landed on ${resultNum} (${colorOf(resultNum)}). Paid $${winTotal}.`,
      "good"
    );
  } else {
    state.lastWin = 0;
    setMessage(
      els,
      `No win. Ball landed on ${resultNum} (${colorOf(resultNum)}).`,
      ""
    );
  }

  els.result.textContent =
    `Result: ${resultNum} (${colorOf(resultNum)})`;

  pushHistory(resultNum);

  updateHud(els, state);

  // 🔥 IMPORTANT: remove transitions so nothing moves again
  els.ballRing.style.transition = "";
  els.wheelInner.style.transition = "";

  state.spinning = false;
  setButtons(els, true);
  persist();
}


  function onBetTypeChange(){
    showNumberPick(els, els.betType.value === "number");
  }

  function init(){
    renderWheel(els);
    clampBet();
    updateHud(els, state);
    onBetTypeChange();

    els.result.textContent = "Result: —";
    renderHistory(els, state.history);

    els.wheelInner.style.transform = `rotate(${state.wheelAngle}deg)`;
    els.ballRing.style.transform = `rotate(${state.ballAngle}deg)`;

    setButtons(els, true);
    setMessage(els, "Choose a bet and spin.");
    persist();
  }

  return { init, spin, resetMoney, setBetFromInput, setMaxBet, onBetTypeChange };
}
