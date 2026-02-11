import { getEls } from "./ui.js";
import { createGame } from "./game.js";

const els = getEls();
const game = createGame(els);

game.init();

els.betInput.addEventListener("input", game.onBetChange);
els.dealBtn.addEventListener("click", game.startRound);
els.hitBtn.addEventListener("click", game.hit);
els.standBtn.addEventListener("click", game.stand);
els.doubleBtn.addEventListener("click", game.doubleDown);
els.resetBtn.addEventListener("click", game.resetMoney);
