import { store } from "./storage.js";
import { draw } from "./deck.js";
import {
  handTotal, isNatural, shouldPlayerDraw, shouldBankerDraw, outcome
} from "./rules.js";
import {
  sleep, setMessage, pulseChip, updateHud, setButtons, setRevealEnabled, clearTable,
  createCardEl, setScores, revealAll, allRevealed, hype
} from "./ui.js";

function clampInt(n, min, max){
  n = Math.floor(Number(n));
  if (!Number.isFinite(n)) return min;
  return Math.max(min, Math.min(max, n));
}

export function createBaccaratGame(els){
  const state = {
    bankroll: store.loadNum("winner_bankroll", 1000), // shared bankroll
    bet: store.loadNum("baccarat_bet", 10),
    lastWin: 0,

    deck: [],
    player: [],
    banker: [],

    inRound: false,
    phase: "idle", // idle | await_initial_reveal | await_draw_reveal | resolved
    betOn: "player",
  };

  function persist(){
    store.saveNum("winner_bankroll", state.bankroll);
    store.saveNum("baccarat_bet", state.bet);
  }

  function clampBet(){
    state.bet = clampInt(els.betInput.value, 1, Math.max(1, state.bankroll));
    els.betInput.value = state.bet;
  }

  function setMaxBet(){
    state.bet = Math.max(1, state.bankroll);
    els.betInput.value = state.bet;
    updateHud(els, state);
    persist();
  }

  function setBetFromInput(){
    clampBet();
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

  function onAnyFlip(){
    // This gets called when any single card flips up.
    // If all currently dealt cards are revealed, advance the round.
    if (!state.inRound) return;

    const pAll = allRevealed(els.playerCards);
    const bAll = allRevealed(els.bankerCards);

    if (pAll && bAll){
      if (state.phase === "await_initial_reveal"){
        continueAfterInitialReveal();
      } else if (state.phase === "await_draw_reveal"){
        resolveAfterAllRevealed();
      }
    }
  }

  function renderHands(faceDown=true){
    els.playerCards.innerHTML = "";
    els.bankerCards.innerHTML = "";

    for (const c of state.player){
      els.playerCards.appendChild(createCardEl(c, faceDown, onAnyFlip));
    }
    for (const c of state.banker){
      els.bankerCards.appendChild(createCardEl(c, faceDown, onAnyFlip));
    }
  }

  async function deal(){
    if (state.inRound) return;

    clampBet();
    updateHud(els, state);

    if (state.bet > state.bankroll){
      setMessage(els, "Not enough bankroll for that bet.", "bad");
      return;
    }

    state.inRound = true;
    state.phase = "await_initial_reveal";
    state.betOn = els.betOn.value;

    setButtons(els, false);
    setRevealEnabled(els, true);
    clearTable(els);

    // Take bet now (we only pay/return later once revealed)
    state.bankroll -= state.bet;
    state.lastWin = 0;
    pulseChip(els, -state.bet);
    updateHud(els, state);

    setMessage(els, "Dealing... reveal BOTH hands to continue 👀");

    state.player = [];
    state.banker = [];

    // Deal 2 each, face-down
    draw(state, state.player); renderHands(true); await sleep(220);
    draw(state, state.banker); renderHands(true); await sleep(220);
    draw(state, state.player); renderHands(true); await sleep(220);
    draw(state, state.banker); renderHands(true); await sleep(220);

    // DO NOT compute totals / payout yet. Wait for reveals.
    setScores(els, "?", "?");
    setMessage(els, "Click cards to reveal. Or press Reveal All.", "");
  }

  async function continueAfterInitialReveal(){
    // All 4 initial cards are revealed.
    // Now we apply natural/draw rules AND deal third cards face-down if needed.
    let pTotal = handTotal(state.player);
    let bTotal = handTotal(state.banker);

    setScores(els, pTotal, bTotal);

    const natural = isNatural(pTotal) || isNatural(bTotal);
    if (natural){
      // Natural ends immediately — but still only after reveals (which we now have).
      state.phase = "resolved";
      resolveRound(pTotal, bTotal, natural);
      return;
    }

    setMessage(els, "No natural. Drawing rules will apply... reveal draws to finish.", "");

    // Decide draws
    let playerThird = null;
    if (shouldPlayerDraw(pTotal)){
      draw(state, state.player);
      playerThird = state.player[state.player.length - 1];
      renderHands(true);
      await sleep(260);
      // don’t update totals yet; wait until reveal
    }

    // Banker draw uses bankerTotal BEFORE any banker draw, and may depend on playerThird value
    if (shouldBankerDraw(bTotal, playerThird)){
      draw(state, state.banker);
      renderHands(true);
      await sleep(260);
    }

    // Now we wait for all cards (including any 3rd cards) to be revealed
    state.phase = "await_draw_reveal";

    // If no draws happened (still 2 vs 2), we can resolve immediately since they’re already revealed
    const noDraws = (state.player.length === 2 && state.banker.length === 2);
    if (noDraws){
      resolveAfterAllRevealed();
    } else {
      // Keep totals hidden until they reveal the new cards
      setScores(els, "?", "?");
      setMessage(els, "Reveal the new card(s) to see the result.", "");
    }
  }

  function resolveAfterAllRevealed(){
    const pTotal = handTotal(state.player);
    const bTotal = handTotal(state.banker);
    setScores(els, pTotal, bTotal);

    state.phase = "resolved";
    resolveRound(pTotal, bTotal, false);
  }

  function resolveRound(pTotal, bTotal, natural){
    const result = outcome(pTotal, bTotal);
    const betOn = state.betOn;

    // Payouts: we already subtracted bet.
    // If win: return bet + profit
    let totalReturn = 0;
    let profit = 0;

    if (betOn === "player"){
      if (result === "player"){
        profit = state.bet;
        totalReturn = state.bet + profit;
      }
    } else if (betOn === "banker"){
      if (result === "banker"){
        profit = Math.floor(state.bet * 0.95);
        totalReturn = state.bet + profit;
      }
    } else { // tie
      if (result === "tie"){
        profit = state.bet * 8;
        totalReturn = state.bet + profit;
      }
    }

    if (totalReturn > 0){
      state.bankroll += totalReturn;
      state.lastWin = profit;
      pulseChip(els, +totalReturn);
      setMessage(els, `WIN! ${result.toUpperCase()} (${pTotal}-${bTotal}) +$${profit}`, "good");

      // Hype if natural 8/9 and you won the bet
      const betWon = (betOn === result) || (betOn === "tie" && result === "tie");
      if (natural && betWon){
        hype(els, "NATURAL WIN!", `${result.toUpperCase()} ${Math.max(pTotal,bTotal)} — paid +$${profit}`);
      }
    } else {
      state.lastWin = 0;
      setMessage(els, `Lose. Result: ${result.toUpperCase()} (${pTotal}-${bTotal})`, "bad");
    }

    updateHud(els, state);
    persist();

    // End round
    state.inRound = false;
    state.phase = "idle";
    setButtons(els, true);
    setRevealEnabled(els, false);
  }

  function revealAllNow(){
    if (!state.inRound){
      // If not in round, just no-op
      return;
    }

    revealAll(els.playerCards);
    revealAll(els.bankerCards);

    // Manually trigger advancement (since revealAll doesn't trigger click events)
    onAnyFlip();
  }

  function init(){
    els.betInput.value = state.bet;
    updateHud(els, state);
    clearTable(els);
    setButtons(els, true);
    setRevealEnabled(els, false);
    setMessage(els, "Pick a bet and deal. Click cards to reveal.", "");
    persist();
  }

  return {
    init,
    deal,
    revealAllNow,
    setBetFromInput,
    setMaxBet,
    resetMoney
  };
}
