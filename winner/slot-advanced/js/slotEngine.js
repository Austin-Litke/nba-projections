import { SYMBOLS, REELS, ROWS, WAYS } from "./symbols.js";

const SYMBOL_KEYS = Object.keys(SYMBOLS);

function weightedPick(){
  const total = SYMBOL_KEYS.reduce((a,k)=>a + (SYMBOLS[k].weight || 0), 0);
  let r = Math.random() * total;
  for (const k of SYMBOL_KEYS){
    r -= SYMBOLS[k].weight || 0;
    if (r <= 0) return k;
  }
  return "A";
}

export function spinGrid(){
  const grid = [];
  for (let c=0; c<REELS; c++){
    const col = [];
    for (let r=0; r<ROWS; r++){
      col.push(weightedPick());
    }
    grid.push(col);
  }
  return grid;
}

function countScatters(grid){
  let s = 0;
  for (let c=0; c<REELS; c++){
    for (let r=0; r<ROWS; r++){
      if (SYMBOLS[grid[c][r]].scatter) s++;
    }
  }
  return s;
}

export function evaluateWays(grid, totalBet){
  // totalBet is the player’s full wager (like $10).
  // In ways slots, the bet is spread across all ways:
  const betPerWay = totalBet / WAYS;

  let totalWin = 0;
  const winCells = new Set();
  const wins = [];

  // Evaluate each paying symbol (non-scatter, non-wild as base symbol)
  for (const symKey of SYMBOL_KEYS){
    const sym = SYMBOLS[symKey];
    if (!sym.payout) continue; // excludes WILD and SCAT

    let waysCount = 1;
    let matchedReels = 0;

    // Determine how many reels in a row we match from left
    for (let c=0; c<REELS; c++){
      let matchesThisReel = 0;

      for (let r=0; r<ROWS; r++){
        const here = grid[c][r];
        if (here === symKey || SYMBOLS[here].wild){
          matchesThisReel++;
        }
      }

      if (matchesThisReel > 0){
        waysCount *= matchesThisReel;
        matchedReels++;
      } else {
        break;
      }
    }

    if (matchedReels >= 3){
      const pay = sym.payout[matchedReels] || 0;
      if (pay > 0){
        // Payout is per-way bet * ways * pay multiplier
        const win = betPerWay * waysCount * pay;
        totalWin += win;
        wins.push({ symbol: symKey, count: matchedReels, ways: waysCount, win });

        // Mark winning cells for cascade:
        // mark any cell in the first matchedReels that is either symKey or WILD
        for (let c=0; c<matchedReels; c++){
          for (let r=0; r<ROWS; r++){
            const here = grid[c][r];
            if (here === symKey || SYMBOLS[here].wild){
              winCells.add(`${c}-${r}`);
            }
          }
        }
      }
    }
  }

  const scatters = countScatters(grid);
  return { totalWin, wins, winCells, scatters };
}

export function applyCascade(grid, winCells){
  // Remove winning symbols and drop down
  for (let c=0; c<REELS; c++){
    // Remove from bottom up
    for (let r=ROWS-1; r>=0; r--){
      if (winCells.has(`${c}-${r}`)){
        grid[c].splice(r, 1);
      }
    }
    // Refill at top
    while (grid[c].length < ROWS){
      grid[c].unshift(weightedPick());
    }
  }
  return grid;
}
