import { loadGames, wireUi, REFRESH_MS } from "./app.js";

wireUi();
loadGames();
setInterval(loadGames, REFRESH_MS);