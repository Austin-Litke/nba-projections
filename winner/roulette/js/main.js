import { getEls } from "./ui.js";
import { createRouletteGame } from "./game.js";

const els = getEls();
const game = createRouletteGame(els);

game.init();

els.betInput.addEventListener("input", game.setBetFromInput);
els.maxBtn.addEventListener("click", game.setMaxBet);
els.betType.addEventListener("change", game.onBetTypeChange);
els.spinBtn.addEventListener("click", game.spin);
els.resetBtn.addEventListener("click", game.resetMoney);
