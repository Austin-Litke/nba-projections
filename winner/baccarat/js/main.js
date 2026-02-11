import { getEls } from "./ui.js";
import { createBaccaratGame } from "./game.js";

const els = getEls();
const game = createBaccaratGame(els);

game.init();

els.betInput.addEventListener("input", game.setBetFromInput);
els.maxBtn.addEventListener("click", game.setMaxBet);
els.dealBtn.addEventListener("click", game.deal);
els.revealAllBtn.addEventListener("click", game.revealAllNow);
els.resetBtn.addEventListener("click", game.resetMoney);
