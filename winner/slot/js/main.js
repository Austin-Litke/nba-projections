import { getEls } from "./ui.js";
import { createSlotGame } from "./game.js";

const els = getEls();
const game = createSlotGame(els);

game.init();

els.betInput.addEventListener("input", game.setBetFromInput);
els.maxBtn.addEventListener("click", game.setMaxBet);
els.spinBtn.addEventListener("click", game.spinOnce);
els.autoBtn.addEventListener("click", () => game.autoSpin(10));
els.resetBtn.addEventListener("click", game.resetMoney);
