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
  renderBestPicks,
  renderTracked,
  renderAutoBestPicks,
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

export async function loadPitcherGameLog(pitcherId) {
  renderPitcherStatus("Loading recent starts...");
  state.pitcherGameLog = await api.pitcherGameLog(pitcherId, 5);
  renderPitcherGameLog(state.pitcherGameLog);
}

function pickBestSide(simulation) {
  const overEV = simulation?.overEV;
  const underEV = simulation?.underEV;

  if (overEV == null && underEV == null) return "";

  if ((overEV ?? -999) >= (underEV ?? -999)) {
    return "Over";
  }

  return "Under";
}

function currentTrackPayload() {
  const projData = state.pitcherProjection || {};
  const pitcher = projData.pitcher || state.pitcher?.pitcher || {};
  const matchup = projData.matchup || {};
  const projection = projData.projection || {};
  const simulation = projData.simulation || {};
  const line = simulation.line ?? null;

  return {
    sport: "mlb",
    market: "pitcher_strikeouts",
    side: pickBestSide(simulation),
    line,
    pitcher,
    matchup,
    projection,
    simulation,
    opponentEnvironment: projData.opponentEnvironment || {},
    createdFrom: "mlb_room",
  };
}

export async function trackCurrentPick() {
  try {
    const payload = currentTrackPayload();

    if (!payload.pitcher?.id) {
      els.trackStatus.textContent = "No pitcher selected.";
      return;
    }

    if (payload.line == null) {
      els.trackStatus.textContent = "No strikeout line available to track.";
      return;
    }

    els.trackStatus.textContent = "Tracking pick...";
    const res = await api.track(payload);

    els.trackStatus.textContent = `Tracked pick #${res.prediction?.id ?? ""}`;
    await loadTracked();
  } catch (err) {
    els.trackStatus.textContent = String(err);
  }
}

export async function settlePick(id, gameId, pitcherId) {
  try {
    const res = await api.settle({
      id,
      gameId,
      pitcherId,
    });

    await loadTracked();
  } catch (err) {
    console.error(err);
  }
}

export async function loadTracked() {
  try {
    const data = await api.tracked();
    state.tracked = data;

    renderBestPicks(data);
    renderTracked(data);

    if (state.autoBestPicks) {
      renderAutoBestPicks(state.autoBestPicks, data);
    }
  } catch (err) {
    els.trackedOut.textContent = String(err);
    if (els.bestPicksOut) {
      els.bestPicksOut.textContent = String(err);
    }
  }
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

  els.bestPicksFilter?.addEventListener("change", () => {
    if (state.autoBestPicks) {
      renderAutoBestPicks(state.autoBestPicks, state.tracked);
    }
  });

  els.trackedOut?.addEventListener("click", async (e) => {
    const btn = e.target.closest(".clv-btn");
    if (!btn) return;

    const id = btn.getAttribute("data-id");
    const pitcherName = btn.getAttribute("data-pitcher-name");
    const side = btn.getAttribute("data-side");
    const line = btn.getAttribute("data-line");

    await updateClvForPick(id, pitcherName, side, line);
  });

  els.bestPicksSort?.addEventListener("change", () => {
    if (state.autoBestPicks) {
      renderAutoBestPicks(state.autoBestPicks, state.tracked);
    }
  });

  els.bestPicksOut?.addEventListener("click", async (e) => {
    const btn = e.target.closest(".track-auto-btn");
    if (!btn) return;

    const index = btn.getAttribute("data-index");
    await trackAutoBestPick(index);
  });

  els.scoreboardOut?.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-pitcher-id]");
    if (!btn) return;

    const pitcherId = btn.getAttribute("data-pitcher-id");
    if (!pitcherId) return;

    await selectPitcher(pitcherId);
  });
  els.trackedFilter?.addEventListener("change", loadTracked);
  els.trackBtn?.addEventListener("click", trackCurrentPick);
  els.refreshTrackedBtn?.addEventListener("click", loadTracked);
  els.settleAllBtn?.addEventListener("click", settleAllPending);
  els.trackedSort?.addEventListener("change", loadTracked);
  els.scanBestPicksBtn?.addEventListener("click", scanBestPicks);
  els.trackAllBestPicksBtn?.addEventListener("click", trackAllAutoBestPicks);

  // 👇 ADD THIS PART
  els.trackedOut?.addEventListener("click", async (e) => {
    const btn = e.target.closest(".settle-btn");
    if (!btn) return;

    const id = btn.getAttribute("data-id");
    const gameId = btn.getAttribute("data-game");
    const pitcherId = btn.getAttribute("data-pitcher");

    await settlePick(id, gameId, pitcherId);
  });
}

export async function settleAllPending() {
  try {
    els.trackStatus.textContent = "Settling all pending picks...";
    const res = await api.settleAll();

    els.trackStatus.textContent =
      `Settled ${res.settledCount || 0} pending picks` +
      (res.errorCount ? `, ${res.errorCount} errors` : "");

    await loadTracked();
  } catch (err) {
    els.trackStatus.textContent = String(err);
  }
}

export async function scanBestPicks() {
  try {
    els.bestPicksOut.textContent = "Scanning today's board...";

    const data = await api.bestPicks();
    state.autoBestPicks = data;

    const trackedData = await api.tracked();
    state.tracked = trackedData;

    renderAutoBestPicks(data, trackedData);
    renderTracked(trackedData);
  } catch (err) {
    els.bestPicksOut.textContent = String(err);
  }
}

export async function trackAutoBestPick(index) {
  try {
    const pick = state.autoBestPicks?.picks?.[Number(index)];

    if (!pick) {
      els.trackStatus.textContent = "Auto pick not found.";
      return;
    }

    const payload = {
      sport: "mlb",
      market: "pitcher_strikeouts",
      side: pick.side,
      line: pick.line,
      pitcher: pick.pitcher,
      matchup: pick.matchup,
      projection: pick.projection,
      simulation: pick.simulation,
      opponentEnvironment: pick.opponentEnvironment || {},
      createdFrom: "auto_best_board",
    };

    els.trackStatus.textContent = "Tracking auto pick...";
    const res = await api.track(payload);

    els.trackStatus.textContent = `Tracked auto pick #${res.prediction?.id ?? ""}`;

    await loadTracked();
  } catch (err) {
    els.trackStatus.textContent = String(err);
  }
}

function autoPickKey(p) {
  return `${p.pitcher?.id}|${p.matchup?.gameId}|${p.side}|${p.line}`;
}

function trackedPickKey(p) {
  return `${p.pitcher?.id}|${p.matchup?.gameId}|${p.side}|${p.line}`;
}

export async function trackAllAutoBestPicks() {
  try {
    const picks = state.autoBestPicks?.picks || [];

    if (!picks.length) {
      els.trackStatus.textContent = "No auto best picks loaded. Click Scan Today first.";
      return;
    }

    const trackedData = await api.tracked();
    const tracked = trackedData?.predictions || [];

    const trackedKeys = new Set(tracked.map(trackedPickKey));

    const untracked = picks.filter((p) => {
      const ev = p.ev;
      return ev != null && ev > 0 && !trackedKeys.has(autoPickKey(p));
    });

    if (!untracked.length) {
      els.trackStatus.textContent = "All +EV auto picks are already tracked.";
      return;
    }

    els.trackStatus.textContent = `Tracking ${untracked.length} auto pick(s)...`;

    let saved = 0;
    let failed = 0;

    for (const pick of untracked) {
      const payload = {
        sport: "mlb",
        market: "pitcher_strikeouts",
        side: pick.side,
        line: pick.line,
        pitcher: pick.pitcher,
        matchup: pick.matchup,
        projection: pick.projection,
        simulation: pick.simulation,
        opponentEnvironment: pick.opponentEnvironment || {},
        createdFrom: "auto_best_board_bulk",
      };

      try {
        await api.track(payload);
        saved += 1;
      } catch {
        failed += 1;
      }
    }

    els.trackStatus.textContent =
      `Tracked ${saved} auto pick(s)` +
      (failed ? `, ${failed} failed` : "");

    await loadTracked();
  } catch (err) {
    els.trackStatus.textContent = String(err);
  }
}

export async function updateClvForPick(id, pitcherName, side, line) {
  try {
    els.trackStatus.textContent = "Updating CLV...";

    const res = await api.updateClv({
      id,
      pitcherName,
      side,
      line,
    });

    els.trackStatus.textContent = `Updated CLV for pick #${res.prediction?.id ?? ""}`;

    await loadTracked();
  } catch (err) {
    els.trackStatus.textContent = String(err);
  }
}