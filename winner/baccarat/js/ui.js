export function getEls(){
  const $ = (id) => document.getElementById(id);
  return {
    bankroll: $("bankroll"),
    betLabel: $("betLabel"),
    lastWin: $("lastWin"),

    betInput: $("betInput"),
    maxBtn: $("maxBtn"),
    betOn: $("betOn"),

    dealBtn: $("dealBtn"),
    revealAllBtn: $("revealAllBtn"),
    resetBtn: $("resetBtn"),

    bankerCards: $("bankerCards"),
    playerCards: $("playerCards"),
    bankerScore: $("bankerScore"),
    playerScore: $("playerScore"),

    msg: $("msg"),
    chip: $("chip"),

    hype: $("hype"),
    hypeTitle: $("hypeTitle"),
    hypeSub: $("hypeSub"),
    confetti: $("confetti"),
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

export function updateHud(els, state){
  els.bankroll.textContent = `$${state.bankroll}`;
  els.betLabel.textContent = `$${state.bet}`;
  els.lastWin.textContent = `$${state.lastWin}`;
}

export function setButtons(els, enabled){
  els.dealBtn.disabled = !enabled;
  els.betInput.disabled = !enabled;
  els.betOn.disabled = !enabled;
  els.maxBtn.disabled = !enabled;
  // reveal button is controlled separately by the game (phase-based)
}

export function setRevealEnabled(els, enabled){
  els.revealAllBtn.disabled = !enabled;
}

export function clearTable(els){
  els.bankerCards.innerHTML = "";
  els.playerCards.innerHTML = "";
  els.bankerScore.textContent = "—";
  els.playerScore.textContent = "—";
}

export function createCardEl(card, faceDown=true, onFlip=null){
  const root = document.createElement("div");
  root.className = "card deal" + (faceDown ? " faceDown" : "");

  const inner = document.createElement("div");
  inner.className = "inner";

  const front = document.createElement("div");
  front.className = "face front";

  const isRed = (card.s === "♥" || card.s === "♦");

  const rank = document.createElement("div");
  rank.className = "rank" + (isRed ? " red" : "");
  rank.textContent = card.r;

  const suit = document.createElement("div");
  suit.className = "suit" + (isRed ? " red" : "");
  suit.textContent = card.s;

  const center = document.createElement("div");
  center.className = "center" + (isRed ? " red" : "");
  center.textContent = card.s;

  front.append(rank, center, suit);

  const back = document.createElement("div");
  back.className = "face back";

  inner.append(front, back);
  root.appendChild(inner);

  // click-to-reveal (only flips from down -> up; not back down)
  root.addEventListener("click", () => {
    if (!root.classList.contains("faceDown")) return;
    root.classList.remove("faceDown");
    if (typeof onFlip === "function") onFlip();
  });

  return root;
}

export function setScores(els, playerTotal, bankerTotal){
  els.playerScore.textContent = String(playerTotal);
  els.bankerScore.textContent = String(bankerTotal);
}

export function revealAll(container){
  container.querySelectorAll(".card.faceDown").forEach(c => c.classList.remove("faceDown"));
}

export function allRevealed(container){
  return container.querySelectorAll(".card.faceDown").length === 0;
}

export function hype(els, title, sub){
  els.hypeTitle.textContent = title;
  els.hypeSub.textContent = sub;

  els.confetti.innerHTML = "";
  for (let i=0;i<30;i++){
    const p = document.createElement("div");
    p.className = "piece";
    p.style.left = `${Math.random()*100}%`;
    p.style.top = `${-20 - Math.random()*80}px`;
    p.style.background = Math.random() > 0.5 ? "rgba(255,209,102,.9)" : "rgba(61,220,151,.85)";
    p.style.animationDelay = `${Math.random()*120}ms`;
    els.confetti.appendChild(p);
  }

  els.hype.classList.add("on");
  setTimeout(() => els.hype.classList.remove("on"), 1600);
}
