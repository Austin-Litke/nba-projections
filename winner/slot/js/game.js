// winner/slot/js/game.js  (replace the previous content with this)
import { store } from "./storage.js";
import { sleep, clampInt } from "./rng.js";
import { SYMBOLS, buildWeightedBag, payoutFor3 } from "./paytable.js";
import {
  setMessage, pulseChip, updateHud, setButtons,
  renderPaytable, renderReel, setReelSpinning, flashWin
} from "./ui.js";

export function createSlotGame(els){
  const bag = buildWeightedBag();

  const state = {
    bankroll: store.loadNum("winner_bankroll", 1000), // <-- shared bankroll key
    bet: store.loadNum("slot_bet", 10),
    lastWin: 0,
    spinning: false,
    autoLeft: 0,
  };

  function persist(){
    store.saveNum("winner_bankroll", state.bankroll); // persist shared bankroll
    store.saveNum("slot_bet", state.bet);
  }

  function pick(){
    return bag[Math.floor(Math.random() * bag.length)];
  }

  function clampBet(){
    state.bet = clampInt(state.bet, 1, Math.max(1, state.bankroll));
  }

  function setBetFromInput(){
    state.bet = clampInt(els.betInput.value, 1, 999999);
    clampBet();
    els.betInput.value = state.bet;
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

  function showRandomPreview(){
    for (let r=0;r<3;r++){
      const icons = [pick().icon, pick().icon, pick().icon];
      renderReel(els, r, icons);
    }
  }

  // Evaluate paylines given a 3x3 finalGrid: finalGrid[row][reel] -> symbolObj
  // Returns { totalWin, details: [{lineName, win, icons}] }
  function evaluatePaylines(finalGrid){
    const paylines = [
      { name: "Top", coords: [ [0,0], [0,1], [0,2] ] },
      { name: "Middle", coords: [ [1,0], [1,1], [1,2] ] },
      { name: "Bottom", coords: [ [2,0], [2,1], [2,2] ] },
      { name: "Diag TL→BR", coords: [ [0,0], [1,1], [2,2] ] },
      { name: "Diag BL→TR", coords: [ [2,0], [1,1], [0,2] ] },
    ];

    let totalWin = 0;
    const details = [];

    for (const line of paylines){
      const ids = line.coords.map(([row,reel]) => finalGrid[row][reel].id);
      const icons = line.coords.map(([row,reel]) => finalGrid[row][reel].icon);
      const allSame = ids.every(id => id === ids[0]);
      if (allSame){
        const mult = payoutFor3(ids[0]); // multiplier from paytable
        const win = mult * state.bet;
        totalWin += win;
        details.push({ lineName: line.name, win, icons });
      }
    }

    return { totalWin, details };
  }

  async function spinOnce(){
    if (state.spinning) return;
    clampBet();
    updateHud(els, state);

    if (state.bet > state.bankroll){
      setMessage(els, "Not enough bankroll for that bet.", "bad");
      return;
    }

    state.spinning = true;
    state.lastWin = 0;
    setButtons(els, false);

    // take bet up front
    state.bankroll -= state.bet;
    pulseChip(els, -state.bet);
    updateHud(els, state);
    setMessage(els, "Spinning...");

    setReelSpinning(els, true);

    // Build final 3x3 grid: rows x reels
    // For realism we simulate rapid updates, then stop each reel to reveal its 3 symbols.
    const finalGrid = [
      [null,null,null], // top row symbols for reels 0..2
      [null,null,null], // middle row
      [null,null,null], // bottom row
    ];

    // Decide final symbols per reel (3 symbols each)
    const finalPerReel = [0,1,2].map(() => [ pick(), pick(), pick() ]); // [top, mid, bottom]

    const stopDelays = [650, 900, 1150];

    // Spin each reel with quick previews until it stops, then render final column
    for (let r=0;r<3;r++){
      const stopAt = performance.now() + stopDelays[r];
      while (performance.now() < stopAt){
        renderReel(els, r, [ pick().icon, pick().icon, pick().icon ]);
        await sleep(60);
      }
      // Use finalPerReel[r] as the real column (top,middle,bottom)
      const col = finalPerReel[r];
      // renderReel expects [topIcon, midIcon, bottomIcon]
      renderReel(els, r, [ col[0].icon, col[1].icon, col[2].icon ]);
      // fill finalGrid: finalGrid[row][reel]
      finalGrid[0][r] = col[0];
      finalGrid[1][r] = col[1];
      finalGrid[2][r] = col[2];
      await sleep(80);
    }

    setReelSpinning(els, false);

    // Evaluate paylines across the grid
    const { totalWin, details } = evaluatePaylines(finalGrid);

    if (totalWin > 0){
      state.bankroll += totalWin;
      state.lastWin = totalWin;
      pulseChip(els, +totalWin);
      updateHud(els, state);
      setMessage(els, `WIN $${totalWin} — ${details.map(d => `${d.lineName}(${d.icons.join('')})`).join(' • ')}`, "good");
      flashWin(els);
    } else {
      state.lastWin = 0;
      updateHud(els, state);
      // show the middle row icons to summarize
      setMessage(els, `No win. ${finalGrid[1][0].icon}${finalGrid[1][1].icon}${finalGrid[1][2].icon}`, "");
    }

    state.spinning = false;
    setButtons(els, true);
    persist();
  }

  async function autoSpin(times=10){
    if (state.spinning) return;
    state.autoLeft = times;
    while (state.autoLeft > 0){
      if (state.bet > state.bankroll) break;
      await spinOnce();
      state.autoLeft--;
      await sleep(250);
    }
    if (state.bet > state.bankroll){
      setMessage(els, "Auto stopped: not enough bankroll.", "bad");
    }
  }

  function init(){
    renderPaytable(els, SYMBOLS);
    clampBet();
    els.betInput.value = state.bet;
    showRandomPreview();
    updateHud(els, state);
    setButtons(els, true);
    setMessage(els, "Set your bet and spin.");
    persist();
  }

  return { init, spinOnce, autoSpin, setBetFromInput, setMaxBet, resetMoney };
}
