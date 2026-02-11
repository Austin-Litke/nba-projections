import { handValue } from "./rules.js";

export function getEls(){
  const $ = (id) => document.getElementById(id);
  return {
    bankroll: $("bankroll"),
    betLabel: $("betLabel"),
    round: $("round"),
    betInput: $("betInput"),
    dealerCards: $("dealerCards"),
    playerCards: $("playerCards"),
    dealerScore: $("dealerScore"),
    playerScore: $("playerScore"),
    msg: $("msg"),
    chip: $("chip"),
    dealBtn: $("dealBtn"),
    hitBtn: $("hitBtn"),
    standBtn: $("standBtn"),
    doubleBtn: $("doubleBtn"),
    resetBtn: $("resetBtn"),
  };
}

export function sleep(ms){ return new Promise(r => setTimeout(r, ms)); }

export function setMessage(els, text, kind=""){
  els.msg.className = "msg" + (kind ? ` ${kind}` : "");
  els.msg.textContent = text;
}

export function pulseChip(els, delta){
  els.chip.textContent =
    (delta >= 0 ? "🟢 " : "🔴 ") + (delta >= 0 ? "+$" : "-$") + Math.abs(delta);

  els.chip.classList.remove("pulse");
  void els.chip.offsetWidth;
  els.chip.classList.add("pulse");
}

export function setButtons(els, { deal, hit, stand, dbl }){
  els.dealBtn.disabled = !deal;
  els.hitBtn.disabled = !hit;
  els.standBtn.disabled = !stand;
  els.doubleBtn.disabled = !dbl;
  els.betInput.disabled = !deal;
}

export function updateHud(els, state){
  els.bankroll.textContent = `$${state.bankroll}`;
  els.round.textContent = String(state.round);
  els.betLabel.textContent = `$${state.currentBet}`;
}

export function clearBoard(els){
  els.dealerCards.innerHTML = "";
  els.playerCards.innerHTML = "";
  els.dealerScore.textContent = "—";
  els.playerScore.textContent = "—";
}

export function updateScores(els, state){
  els.playerScore.textContent = String(handValue(state.player));
  els.dealerScore.textContent = state.dealerHoleHidden
    ? (state.dealer.length ? "?" : "—")
    : String(handValue(state.dealer));
}

export function createCardEl(card, { faceDown=false, r=0, x=0 } = {}){
  const root = document.createElement("div");
  root.className = "card pop";
  root.style.setProperty("--x", `${x}px`);
  root.style.setProperty("--y", `0px`);
  root.style.setProperty("--r", `${r}deg`);

  const inner = document.createElement("div");
  inner.className = "inner";
  root.appendChild(inner);

  const front = document.createElement("div");
  front.className = "face front";

  const rank = document.createElement("div");
  rank.className = "rank" + ((card.s === "♥" || card.s === "♦") ? " red" : "");
  rank.textContent = card.r;

  const suit = document.createElement("div");
  suit.className = "suit" + ((card.s === "♥" || card.s === "♦") ? " red" : "");
  suit.textContent = card.s;

  front.append(rank, suit);

  const back = document.createElement("div");
  back.className = "face backface";

  inner.append(front, back);

  if (faceDown) root.classList.add("flipped");
  return root;
}

export function flipCard(cardEl){
  cardEl?.classList.remove("flipped");
}
