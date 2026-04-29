import { api } from "./api.js";
import { state } from "./state.js";
import {
  renderStatus,
  renderScoreboard,
  renderPitcherStatus,
  renderPitcherDetail,
  renderPitcherProjection,
  renderPitcherLines,
  renderPitcherLineup,
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
}

export async function loadPitcherProjection(pitcherId) {
  renderPitcherStatus("Loading projection...");
  state.pitcherProjection = await api.pitcherProjection(pitcherId, 5);
  renderPitcherProjection(state.pitcherProjection, state.pitcherLines);
}

export async function loadPitcherLines(pitcherId) {
  renderPitcherStatus("Loading lines...");
  state.pitcherLines = await api.pitcherLines(pitcherId);
  renderPitcherLines(state.pitcherLines);

  if (state.pitcherProjection) {
    renderPitcherProjection(state.pitcherProjection, state.pitcherLines);
  }
}

export async function loadPitcherGameLog(pitcherId) {
  renderPitcherStatus("Loading recent starts...");
  state.pitcherGameLog = await api.pitcherGameLog(pitcherId, 5);
  renderPitcherGameLog(state.pitcherGameLog);
}

export async function selectPitcher(pitcherId) {
  try {
    state.pitcher = null;
    state.pitcherProjection = null;
    state.pitcherLines = null;
    state.pitcherLineup = null;
    state.pitcherGameLog = null;

    els.pitcherDetail.innerHTML = "";
    els.pitcherProjection.innerHTML = "";
    els.pitcherLines.innerHTML = "";
    els.pitcherLineup.innerHTML = "";
    els.pitcherGameLog.innerHTML = "";

    await loadPitcher(pitcherId);
    await loadPitcherProjection(pitcherId);
    await loadPitcherLines(pitcherId);
    await loadPitcherLineup();
    await loadPitcherGameLog(pitcherId);

    renderPitcherStatus("Pitcher, projection, lines, lineup, and recent starts loaded.");
  } catch (err) {
    renderPitcherStatus(String(err));
    els.pitcherDetail.innerHTML = "";
    els.pitcherProjection.innerHTML = "";
    els.pitcherLines.innerHTML = "";
    els.pitcherLineup.innerHTML = "";
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

export async function loadPitcherLineup() {
  const gameId = state.pitcherProjection?.matchup?.gameId;

  if (!gameId) {
    els.pitcherLineup.innerHTML = `
      <div class="detail-card">
        <h3>Opponent Lineup</h3>
        <div class="muted">No game ID found for lineup lookup.</div>
      </div>
    `;
    return;
  }

  renderPitcherStatus("Loading opponent lineup...");
  state.pitcherLineup = await api.lineup(gameId);
  renderPitcherLineup(state.pitcherLineup, state.pitcherProjection);
}