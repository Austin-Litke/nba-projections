import { els } from "./dom.js";

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function lineForPitcher(projectionData, linesData) {
  const lines = linesData?.lines || [];
  const proj = projectionData?.projection || {};
  const kLine = lines.find((x) => x?.statKey === "pitcher_strikeouts");

  if (!kLine || typeof kLine.line !== "number" || typeof proj.strikeouts !== "number") {
    return null;
  }

  const edge = Number((proj.strikeouts - kLine.line).toFixed(2));

  let lean = "No edge";
  let leanClass = "lean-neutral";

  if (edge > 0.75) {
    lean = "Strong Over";
    leanClass = "lean-over-strong";
  } else if (edge > 0.25) {
    lean = "Lean Over";
    leanClass = "lean-over";
  } else if (edge < -0.75) {
    lean = "Strong Under";
    leanClass = "lean-under-strong";
  } else if (edge < -0.25) {
    lean = "Lean Under";
    leanClass = "lean-under";
  }

  return {
    line: kLine.line,
    edge,
    lean,
    leanClass,
    overOdds: kLine.overOdds,
    underOdds: kLine.underOdds,
  };
}

function gameStatText(g) {
  const parts = [];

  if (g?.battersFaced != null && g?.battersFaced !== "") parts.push(`BF: ${g.battersFaced}`);
  if (g?.inningsPitched != null && g?.inningsPitched !== "") parts.push(`IP: ${g.inningsPitched}`);
  if (g?.strikeOuts != null && g?.strikeOuts !== "") parts.push(`K: ${g.strikeOuts}`);
  if (g?.earnedRuns != null && g?.earnedRuns !== "") parts.push(`ER: ${g.earnedRuns}`);

  return parts.join(" | ");
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
        <div class="game-date">
          ${esc(g?.officialDate || "")}
          ${g?.startTime ? `<div class="game-time">${esc(g.startTime)}</div>` : ""}
        </div>
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

export function renderPitcherProjection(projectionData, linesData = null) {
  const p = projectionData?.projection || {};
  const season = projectionData?.season || {};
  const recent = projectionData?.recent || {};
  const meta = projectionData?.meta || {};
  const matchup = projectionData?.matchup || {};
  const lineData = lineForPitcher(projectionData, linesData);

  els.pitcherProjection.innerHTML = `
    <div class="detail-card">
      <h3>Phase 2 Projection</h3>
      <div class="detail-row"><strong>Projected Ks:</strong> ${esc(p.strikeouts ?? "")}</div>
      <div class="detail-row"><strong>Expected BF:</strong> ${esc(p.expectedBattersFaced ?? "")}</div>
      <div class="detail-row"><strong>Blended K%:</strong> ${esc(p.kPct ?? "")}</div>
      <div class="detail-row"><strong>Adjusted K%:</strong> ${esc(p.adjustedKPct ?? "")}</div>
      <div class="detail-row"><strong>Role:</strong> ${esc(p.role ?? "")}</div>
      <div class="detail-row"><strong>Confidence:</strong> ${esc(p.confidence ?? "")}</div>
      <div class="detail-row"><strong>Model:</strong> ${esc(p.modelVersion ?? "")}</div>

      <div class="detail-row" style="margin-top:10px;"><strong>Opponent:</strong> ${esc(matchup.opponentTeam ?? "Unknown")}</div>
      <div class="detail-row"><strong>Opponent Adj:</strong> ${esc(meta.opponentAdjustment ?? "")}</div>

      ${
        lineData
          ? `
        <div class="detail-row" style="margin-top:10px;"><strong>Line:</strong> ${esc(lineData.line)}</div>
        <div class="detail-row"><strong>Edge:</strong> ${esc(lineData.edge)}</div>
        <div class="detail-row">
          <strong>Lean:</strong>
          <span class="${esc(lineData.leanClass)}">${esc(lineData.lean)}</span>
        </div>
        <div class="detail-row muted">
          Higher: ${esc(lineData.overOdds ?? "")} | Lower: ${esc(lineData.underOdds ?? "")}
        </div>
      `
          : `
        <div class="detail-row muted" style="margin-top:10px;">No strikeout line available yet for edge calculation.</div>
      `
      }

      <div class="detail-row" style="margin-top:10px;"><strong>Season Starts:</strong> ${esc(season.gamesStarted ?? "")}</div>
      <div class="detail-row"><strong>Season BF/Start:</strong> ${esc(season.bfPerStart ?? "")}</div>
      <div class="detail-row"><strong>Season K%:</strong> ${esc(season.kPct ?? "")}</div>
      <div class="detail-row muted">Raw season BF/Start: ${esc(season.rawBfPerStart ?? "")}</div>
      <div class="detail-row muted">Raw season K%: ${esc(season.rawKPct ?? "")}</div>

      <div class="detail-row" style="margin-top:10px;"><strong>Recent Starts:</strong> ${esc(recent.starts ?? "")}</div>
      <div class="detail-row"><strong>Recent BF/Start:</strong> ${esc(recent.bfPerStart ?? "")}</div>
      <div class="detail-row"><strong>Recent K%:</strong> ${esc(recent.kPct ?? "")}</div>
      <div class="detail-row muted">Raw recent BF/Start: ${esc(recent.rawBfPerStart ?? "")}</div>
      <div class="detail-row muted">Raw recent K%: ${esc(recent.rawKPct ?? "")}</div>
    </div>
  `;
}

export function renderPitcherLines(data) {
  const lines = data?.lines || [];

  if (!lines.length) {
    els.pitcherLines.innerHTML = `
      <div class="detail-card">
        <h3>Underdog Lines</h3>
        <div class="muted">No pitcher strikeout line found.</div>
      </div>
    `;
    return;
  }

  els.pitcherLines.innerHTML = `
    <div class="detail-card">
      <h3>Underdog Lines</h3>
      ${lines.map((line) => `
        <div class="detail-row">
          <strong>${esc(line.displayStat || "")}:</strong>
          ${esc(line.line ?? "")}
          ${line.overOdds != null ? `| Higher: ${esc(line.overOdds)}` : ""}
          ${line.underOdds != null ? `| Lower: ${esc(line.underOdds)}` : ""}
        </div>
      `).join("")}
    </div>
  `;
}

export function renderPitcherGameLog(data) {
  const games = data?.games || [];
  const debug = data?.debug || {};

  if (!games.length) {
    els.pitcherGameLog.innerHTML = `
      <div class="detail-card">
        <h3>Recent Starts</h3>
        <div class="muted">No recent starts found.</div>
        <div class="detail-row">statsBlocks: ${esc(debug.statsBlocks ?? "")}</div>
        <div class="detail-row">splitsFound: ${esc(debug.splitsFound ?? "")}</div>
      </div>
    `;
    return;
  }

  els.pitcherGameLog.innerHTML = `
    <div class="detail-card">
      <h3>Recent Starts</h3>
      ${games.map((g) => `
        <div class="log-row">
          <div><strong>${esc(g.date || "")}</strong> vs ${esc(g.opponent || "Unknown")}</div>
          <div>${esc(gameStatText(g))}</div>
          <div class="muted">${esc(g.summary || "")}</div>
        </div>
      `).join("")}
    </div>
  `;
}