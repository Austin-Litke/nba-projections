import { loadHealth, loadScoreboard, loadTracked, wireUi } from "./app.js";

async function boot() {
  wireUi();

  try {
    await loadHealth();
  } catch (err) {
    const el = document.getElementById("status");
    if (el) el.textContent = String(err);
  }

  try {
    await loadScoreboard();
  } catch (err) {
    const el = document.getElementById("scoreboardOut");
    if (el) el.textContent = String(err);
  }

  try {
    await loadTracked();
  } catch (err) {
    const el = document.getElementById("trackedOut");
    if (el) el.textContent = String(err);
  }
}

boot();