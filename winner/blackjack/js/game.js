import { store } from "./storage.js";
import { clampBet, handValue, isBlackjack } from "./rules.js";
import { draw } from "./deck.js";
import {
  sleep, setMessage, pulseChip, setButtons, updateHud, clearBoard, updateScores,
  createCardEl, flipCard
} from "./ui.js";

export function createGame(els){
  const state = {
    bankroll: store.loadNum("winner_bankroll", 1000),
    round: store.loadNum("bj_round", 1),
    currentBet: 25,
    deck: [],
    player: [],
    dealer: [],
    inRound: false,
    dealerHoleHidden: true,
  };

  let dealerHoleEl = null;

  function persist(){
    store.saveNum("winner_bankroll", state.bankroll);
    store.saveNum("bj_round", state.round);
  }

  async function dealOne({ to, who, faceDown=false, delay=180 }){
    draw(state, to);

    const container = who === "dealer" ? els.dealerCards : els.playerCards;
    const idx = to.length - 1;

    const r = -6 + idx * 6;
    const x = idx * 2;

    const el = createCardEl(to[idx], { faceDown, r, x });
    container.appendChild(el);

    updateScores(els, state);
    await sleep(delay);
    return el;
  }

  function finishRound(){
    state.inRound = false;
    state.round += 1;
    setButtons(els, { deal:true, hit:false, stand:false, dbl:false });
    updateHud(els, state);
    persist();
  }

  async function endRoundNatural(pBJ, dBJ){
    state.dealerHoleHidden = false;
    updateScores(els, state);

    await sleep(250);
    flipCard(dealerHoleEl);
    await sleep(250);

    if (pBJ && dBJ){
      state.bankroll += state.currentBet;
      pulseChip(els, +state.currentBet);
      setMessage(els, "Push. Both blackjack.");
    } else if (pBJ){
      const payout = Math.floor(state.currentBet * 2.5);
      state.bankroll += payout;
      pulseChip(els, +payout);
      setMessage(els, "Blackjack! You win (3:2).", "good");
    } else {
      setMessage(els, "Dealer has blackjack. You lose.", "bad");
    }

    finishRound();
  }

  async function dealerPlay(){
    setButtons(els, { deal:false, hit:false, stand:false, dbl:false });

    state.dealerHoleHidden = false;
    updateScores(els, state);

    await sleep(250);
    flipCard(dealerHoleEl);
    await sleep(250);

    while (handValue(state.dealer) < 17){
      await dealOne({ to: state.dealer, who:"dealer", delay:180 });
    }

    const p = handValue(state.player);
    const d = handValue(state.dealer);

    if (d > 21){
      state.bankroll += state.currentBet * 2;
      pulseChip(els, +state.currentBet * 2);
      setMessage(els, "Dealer busts. You win!", "good");
    } else if (p > d){
      state.bankroll += state.currentBet * 2;
      pulseChip(els, +state.currentBet * 2);
      setMessage(els, "You win!", "good");
    } else if (p < d){
      setMessage(els, "You lose.", "bad");
    } else {
      state.bankroll += state.currentBet;
      pulseChip(els, +state.currentBet);
      setMessage(els, "Push.");
    }

    finishRound();
  }

  async function startRound(){
    state.currentBet = clampBet(Number(els.betInput.value || 0));
    els.betInput.value = state.currentBet;

    if (state.currentBet > state.bankroll){
      setMessage(els, "You don't have enough money for that bet.", "bad");
      return;
    }

    setButtons(els, { deal:false, hit:false, stand:false, dbl:false });

    state.inRound = true;
    state.dealerHoleHidden = true;
    dealerHoleEl = null;

    clearBoard(els);
    state.player = [];
    state.dealer = [];

    state.bankroll -= state.currentBet;
    pulseChip(els, -state.currentBet);
    updateHud(els, state);

    setMessage(els, "Dealing...");

    await dealOne({ to: state.player, who:"player" });
    await dealOne({ to: state.dealer, who:"dealer" });
    await dealOne({ to: state.player, who:"player" });
    dealerHoleEl = await dealOne({ to: state.dealer, who:"dealer", faceDown:true });

    setButtons(els, { deal:false, hit:true, stand:true, dbl:true });
    setMessage(els, "Hit, Stand, or Double.");
    persist();

    const pBJ = isBlackjack(state.player);
    const dBJ = isBlackjack(state.dealer);
    if (pBJ || dBJ) await endRoundNatural(pBJ, dBJ);
  }

  async function hit(){
    if (!state.inRound) return;

    setButtons(els, { deal:false, hit:false, stand:false, dbl:false });
    await dealOne({ to: state.player, who:"player", delay:140 });

    if (handValue(state.player) > 21){
      state.dealerHoleHidden = false;
      updateScores(els, state);
      flipCard(dealerHoleEl);
      setMessage(els, "Bust. You lose.", "bad");
      finishRound();
      return;
    }

    setButtons(els, { deal:false, hit:true, stand:true, dbl:true });
    persist();
  }

  async function stand(){
    if (!state.inRound) return;
    await dealerPlay();
  }

  async function doubleDown(){
    if (!state.inRound) return;

    if (state.bankroll < state.currentBet){
      setMessage(els, "Not enough bankroll to double.", "bad");
      return;
    }

    setButtons(els, { deal:false, hit:false, stand:false, dbl:false });

    state.bankroll -= state.currentBet;
    pulseChip(els, -state.currentBet);

    state.currentBet *= 2;
    els.betInput.value = state.currentBet;
    updateHud(els, state);

    await dealOne({ to: state.player, who:"player", delay:140 });

    if (handValue(state.player) > 21){
      state.dealerHoleHidden = false;
      updateScores(els, state);
      flipCard(dealerHoleEl);
      setMessage(els, "Double… and bust. You lose.", "bad");
      finishRound();
      return;
    }

    await dealerPlay();
  }

  function resetMoney(){
    state.bankroll = 1000;
    state.round = 1;
    persist();
    updateHud(els, state);
    setMessage(els, "Reset bankroll to $1000.");
    pulseChip(els, 0);
  }

  function onBetChange(){
    state.currentBet = clampBet(Number(els.betInput.value));
    updateHud(els, state);
  }

  function init(){
    updateHud(els, state);
    els.betInput.value = state.currentBet;

    clearBoard(els);
    updateScores(els, state);
    setButtons(els, { deal:true, hit:false, stand:false, dbl:false });
    setMessage(els, "Place a bet and hit Deal.");
  }

  return { init, startRound, hit, stand, doubleDown, resetMoney, onBetChange };
}
