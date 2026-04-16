import { api } from "./api.js";
import { state } from "./state.js";
import {
  renderStatus,
  renderScoreboard,
  renderPitcherStatus,
  renderPitcherDetail,
  renderPitcherGameLog,
} from "./render.js";
import { els } from "./dom.js";

export async function loadHealth() {
  state.health = await api.health();
  renderStatus(state.health);
}

export async function loadScoreboard() {
  state.scoreboard = await api.scoreboard();
  renderScoreboard(state.scoreboard);
}

export async function loadPitcher(pitcherId) {
  state.currentPitcherId = pitcherId;
  renderPitcherStatus("Loading pitcher...");
  state.pitcher = await api.pitcher(pitcherId);
  renderPitcherDetail(state.pitcher);
  renderPitcherStatus("Pitcher loaded.");
}

export async function loadPitcherGameLog(pitcherId) {
  renderPitcherStatus("Loading recent starts...");
  state.pitcherGameLog = await api.pitcherGameLog(pitcherId, 5);
  renderPitcherGameLog(state.pitcherGameLog);
  renderPitcherStatus("Pitcher and recent starts loaded.");
}

export async function selectPitcher(pitcherId) {
  try {
    els.pitcherDetail.innerHTML = "";
    els.pitcherGameLog.innerHTML = "";
    await loadPitcher(pitcherId);
    await loadPitcherGameLog(pitcherId);
  } catch (err) {
    renderPitcherStatus(String(err));
    els.pitcherDetail.innerHTML = "";
    els.pitcherGameLog.innerHTML = "";
  }
}

export function wireUi() {
  els.refreshBtn?.addEventListener("click", async () => {
    try {
      els.scoreboardOut.textContent = "Loading...";
      await loadScoreboard();
    } catch (err) {
      els.scoreboardOut.textContent = String(err);
    }
  });

  els.scoreboardOut?.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-pitcher-id]");
    if (!btn) return;

    const pitcherId = btn.getAttribute("data-pitcher-id");
    if (!pitcherId) return;

    await selectPitcher(pitcherId);
  });
}