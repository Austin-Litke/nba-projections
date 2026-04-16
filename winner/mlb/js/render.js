import { els } from "./dom.js";

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function renderStatus(data) {
  els.status.textContent = data?.message || "Unknown status";
}

export function renderPitcherStatus(text) {
  if (els.pitcherStatus) {
    els.pitcherStatus.textContent = text || "";
  }
}

function pitcherButton(team) {
  const pitcher = team?.probablePitcher;
  if (!pitcher?.id || !pitcher?.name) {
    return `Probable: ${esc(pitcher?.name || "TBD")}`;
  }

  return `
    Probable:
    <button class="link-btn" data-pitcher-id="${esc(pitcher.id)}">
      ${esc(pitcher.name)}
    </button>
  `;
}

function teamLine(label, team) {
  const name = team?.name || "Unknown team";
  return `
    <div class="team-row">
      <div class="team-main">${esc(label)}: ${esc(name)}</div>
      <div class="team-sub">${pitcherButton(team)}</div>
    </div>
  `;
}

export function renderScoreboard(data) {
  const games = data?.games || [];

  if (!games.length) {
    els.scoreboardOut.innerHTML = `<div class="muted">No games found for this date.</div>`;
    return;
  }

  els.scoreboardOut.innerHTML = games.map((g) => `
    <div class="game-card">
      <div class="game-top">
        <div class="game-status">${esc(g?.status?.detailed || "Unknown")}</div>
        <div class="game-date">${esc(g?.officialDate || "")}</div>
      </div>

      ${teamLine("Away", g.away)}
      ${teamLine("Home", g.home)}

      <div class="game-meta">
        Venue: ${esc(g?.venue?.name || "Unknown")}
      </div>
    </div>
  `).join("");
}

export function renderPitcherDetail(data) {
  const p = data?.pitcher || {};
  const season = data?.season || {};

  els.pitcherDetail.innerHTML = `
    <div class="detail-card">
      <h3>${esc(p.fullName || "Unknown Pitcher")}</h3>
      <div class="detail-row">Pitcher ID: ${esc(p.id || "")}</div>
      <div class="detail-row">Throws: ${esc(p.pitchHand || "Unknown")}</div>
      <div class="detail-row">Team: ${esc(p.teamName || "Unknown")}</div>
      <div class="detail-row">ERA: ${esc(season.era ?? "")}</div>
      <div class="detail-row">Innings: ${esc(season.inningsPitched ?? "")}</div>
      <div class="detail-row">Strikeouts: ${esc(season.strikeOuts ?? "")}</div>
      <div class="detail-row">Starts: ${esc(season.gamesStarted ?? "")}</div>
    </div>
  `;
}

export function renderPitcherGameLog(data) {
  const games = data?.games || [];

  if (!games.length) {
    els.pitcherGameLog.innerHTML = `<div class="muted">No recent starts found.</div>`;
    return;
  }

  els.pitcherGameLog.innerHTML = `
    <div class="detail-card">
      <h3>Recent Starts</h3>
      ${games.map((g) => `
        <div class="log-row">
          <div><strong>${esc(g.date || "")}</strong> vs ${esc(g.opponent || "Unknown")}</div>
          <div>IP: ${esc(g.inningsPitched ?? "")} | K: ${esc(g.strikeOuts ?? "")} | ER: ${esc(g.earnedRuns ?? "")}</div>
        </div>
      `).join("")}
    </div>
  `;
}