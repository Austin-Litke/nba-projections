import { EURO_WHEEL, colorOf } from "./roulette_data.js";

export function getEls(){
  const $ = (id) => document.getElementById(id);
  return {
    bankroll: $("bankroll"),
    betLabel: $("betLabel"),
    lastWin: $("lastWin"),
    betInput: $("betInput"),
    maxBtn: $("maxBtn"),
    betType: $("betType"),
    numberRow: $("numberRow"),
    numberPick: $("numberPick"),
    spinBtn: $("spinBtn"),
    resetBtn: $("resetBtn"),
    msg: $("msg"),
    chip: $("chip"),
    wheelInner: $("wheelInner"),
    ballRing: $("ballRing"),
    result: $("result"),
    history: $("history"),
  };
}

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
  els.spinBtn.disabled = !enabled;
  els.betInput.disabled = !enabled;
  els.maxBtn.disabled = !enabled;
  els.betType.disabled = !enabled;
  els.numberPick.disabled = !enabled;
}

export function showNumberPick(els, show){
  els.numberRow.style.display = show ? "flex" : "none";
}

export function renderWheel(els){
  els.wheelInner.innerHTML = "";
  const n = EURO_WHEEL.length;
  const step = 360 / n;

  // Read the shared radius from CSS so labels match the ball ring perfectly
  const trackPx = getComputedStyle(document.documentElement).getPropertyValue("--track").trim();
  const radius = Number(trackPx.replace("px","")) || 170;

  for (let i=0;i<n;i++){
    const num = EURO_WHEEL[i];
    const c = colorOf(num);

    const slice = document.createElement("div");
    slice.className = "slice";
    slice.style.transform = `rotate(${i * step}deg)`;

    const label = document.createElement("div");
    label.className = `label ${c}`;
    label.textContent = String(num);

    // Put the label center on the radius ring and keep text upright
    label.style.transform =
      `translate(${radius}px, 0px) translate(-50%, -50%) rotate(${-i * step}deg)`;

    slice.appendChild(label);
    els.wheelInner.appendChild(slice);
  }
}

export function renderHistory(els, items){
  els.history.innerHTML = "";
  for (const it of items){
    const d = document.createElement("div");
    d.className = `hist ${it.color}`;
    d.textContent = it.num;
    els.history.appendChild(d);
  }
}
