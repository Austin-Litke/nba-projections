// winner/sports/js/main.js
import { loadGames, wireUi, REFRESH_MS } from "./app.js";

wireUi();

// Catch first load errors (prevents silent “Loading…”)
loadGames().catch(e => {
  const s = document.getElementById("status");
  if (s) s.textContent = `loadGames failed: ${e?.message || e}`;
});

// Auto refresh
setInterval(() => {
  loadGames().catch(e => {
    const s = document.getElementById("status");
    if (s) s.textContent = `auto refresh failed: ${e?.message || e}`;
  });
}, REFRESH_MS);