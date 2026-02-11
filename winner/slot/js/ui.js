export function getEls(){
  const $ = (id) => document.getElementById(id);
  return {
    bankroll: $("bankroll"),
    betLabel: $("betLabel"),
    lastWin: $("lastWin"),
    betInput: $("betInput"),
    maxBtn: $("maxBtn"),
    spinBtn: $("spinBtn"),
    autoBtn: $("autoBtn"),
    resetBtn: $("resetBtn"),
    msg: $("msg"),
    chip: $("chip"),
    paytable: $("paytable"),
    reels: [ $("reel0"), $("reel1"), $("reel2") ],
    reelShells: Array.from(document.querySelectorAll(".reel")),
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
  els.autoBtn.disabled = !enabled;
  els.maxBtn.disabled = !enabled;
  els.betInput.disabled = !enabled;
}

export function renderPaytable(els, symbols){
  els.paytable.innerHTML = "";
  for (const s of symbols){
    const row = document.createElement("div");
    row.className = "payrow";
    row.innerHTML = `
      <div class="left">
        <span class="icons">${s.icon}${s.icon}${s.icon}</span>
        <span>${s.id}</span>
      </div>
      <div><b>${s.mult}x</b></div>
    `;
    els.paytable.appendChild(row);
  }
}

export function renderReel(els, reelIndex, icons3){
  const win = els.reels[reelIndex];
  win.innerHTML = "";
  for (const icon of icons3){
    const d = document.createElement("div");
    d.className = "symbol";
    d.textContent = icon;
    win.appendChild(d);
  }
}

export function setReelSpinning(els, on){
  els.reelShells.forEach(r => r.classList.toggle("spinning", on));
}

export function flashWin(els, reelIndexes=[0,1,2]){
  for (const i of reelIndexes){
    els.reels[i].classList.remove("flash");
    void els.reels[i].offsetWidth;
    els.reels[i].classList.add("flash");
  }
}
