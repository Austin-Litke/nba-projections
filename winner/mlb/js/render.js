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

  els.scoreboardOut.innerHTML = games.map((g) => {
    const startTimeHtml = g?.startTime
      ? `<div class="game-time">${esc(g.startTime)}</div>`
      : "";

    return `
      <div class="game-card">
        <div class="game-top">
          <div class="game-status">${esc(g?.status?.detailed || "Unknown")}</div>
          <div class="game-date">
            ${esc(g?.officialDate || "")}
            ${startTimeHtml}
          </div>
        </div>

        ${teamLine("Away", g.away)}
        ${teamLine("Home", g.home)}

        <div class="game-meta">
          Venue: ${esc(g?.venue?.name || "Unknown")}
        </div>
      </div>
    `;
  }).join("");
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
  const oppEnv = projectionData?.opponentEnvironment || {};
  const lineData = lineForPitcher(projectionData, linesData);
  const sim = projectionData?.simulation || {};

  let lineHtml = `
    <div class="detail-row muted" style="margin-top:10px;">
      No strikeout line available yet for edge calculation.
    </div>
  `;

  if (lineData) {
    lineHtml = `
      <div class="detail-row" style="margin-top:10px;"><strong>Line:</strong> ${esc(lineData.line)}</div>
      <div class="detail-row"><strong>Edge:</strong> ${esc(lineData.edge)}</div>
      <div class="detail-row">
        <strong>Lean:</strong>
        <span class="${esc(lineData.leanClass)}">${esc(lineData.lean)}</span>
      </div>
      <div class="detail-row muted">
        Higher: ${esc(lineData.overOdds ?? "")} | Lower: ${esc(lineData.underOdds ?? "")}
      </div>
    `;
  }

  const oppSource = oppEnv?.source ? ` | Source: ${esc(oppEnv.source)}` : "";
  const splitLabel = oppEnv?.pitcherHand ? `vs ${oppEnv.pitcherHand}` : "overall";

  els.pitcherProjection.innerHTML = `
    <div class="detail-card">
      <h3>Phase 4 Projection</h3>
      <div class="detail-row"><strong>Projected Ks:</strong> ${esc(p.strikeouts ?? "")}</div>
      <div class="detail-row"><strong>Expected BF:</strong> ${esc(p.expectedBattersFaced ?? "")}</div>
      <div class="detail-row"><strong>Base BF:</strong> ${esc(p.baseExpectedBattersFaced ?? "")}</div>
      <div class="detail-row"><strong>Workload Adj:</strong> ${esc(p.workload?.adjustment ?? "")}</div>
      <div class="detail-row"><strong>Workload Risk:</strong> ${esc(p.workload?.risk ?? "")}</div>
      <div class="detail-row"><strong>Workload Volatility:</strong> ${esc(p.workload?.volatility ?? "")}</div>
      <div class="detail-row muted">
        Workload notes: ${esc((p.workload?.reasons || []).join(", "))}
      </div>

      <div class="detail-row" style="margin-top:10px;"><strong>Simulation Mean:</strong> ${esc(sim.mean ?? "")}</div>
      <div class="detail-row"><strong>Median:</strong> ${esc(sim.median ?? "")}</div>
      <div class="detail-row"><strong>Range:</strong> P10 ${esc(sim.p10 ?? "")} | P90 ${esc(sim.p90 ?? "")}</div>
      <div class="detail-row"><strong>Over Prob:</strong> ${sim.probOver != null ? esc(Math.round(sim.probOver * 100) + "%") : ""}</div>
      <div class="detail-row"><strong>Under Prob:</strong> ${sim.probUnder != null ? esc(Math.round(sim.probUnder * 100) + "%") : ""}</div>
      <div class="detail-row"><strong>Prob Lean:</strong> ${esc(sim.lean ?? "")}</div>

      <div class="detail-row" style="margin-top:10px;"><strong>Over Implied:</strong> ${sim.overImplied != null ? esc(Math.round(sim.overImplied * 100) + "%") : ""}</div>
      <div class="detail-row"><strong>Under Implied:</strong> ${sim.underImplied != null ? esc(Math.round(sim.underImplied * 100) + "%") : ""}</div>
      <div class="detail-row"><strong>Over EV:</strong> ${sim.overEV != null ? esc(sim.overEV.toFixed(2)) : ""}</div>
      <div class="detail-row"><strong>Under EV:</strong> ${sim.underEV != null ? esc(sim.underEV.toFixed(2)) : ""}</div>
      <div class="detail-row"><strong>EV Lean:</strong> ${esc(sim.evLean ?? "")}</div>


      <div class="detail-row"><strong>Blended K%:</strong> ${esc(p.kPct ?? "")}</div>
      <div class="detail-row"><strong>Adjusted K%:</strong> ${esc(p.adjustedKPct ?? "")}</div>
      <div class="detail-row"><strong>Role:</strong> ${esc(p.role ?? "")}</div>
      <div class="detail-row"><strong>Confidence:</strong> ${esc(p.confidence ?? "")}</div>
      <div class="detail-row"><strong>Model:</strong> ${esc(p.modelVersion ?? "")}</div>

      <div class="detail-row" style="margin-top:10px;"><strong>Opponent:</strong> ${esc(matchup.opponentTeam ?? "Unknown")}</div>
      <div class="detail-row"><strong>Opponent Adj:</strong> ${esc(meta.opponentAdjustment ?? "")}</div>
      <div class="detail-row"><strong>Opponent K%:</strong> ${esc(oppEnv.kRate ?? "")}</div>
      <div class="detail-row"><strong>Split:</strong> ${esc(splitLabel)}</div>
      <div class="detail-row"><strong>Team Adj:</strong> ${esc(oppEnv.teamAdjustment ?? "")}</div>
      <div class="detail-row"><strong>Lineup Adj:</strong> ${esc(oppEnv.lineupAdjustment ?? "")}</div>
      <div class="detail-row"><strong>Lineup K%:</strong> ${esc(oppEnv.lineupKRate ?? "")}</div>
      <div class="detail-row muted">
        League Avg K%: ${esc(oppEnv.leagueAvgKRate ?? "")}${oppSource}
        ${oppEnv.lineupSource ? ` | Lineup Source: ${esc(oppEnv.lineupSource)}` : ""}
      </div>

      ${
        oppEnv.source === "lineup_override"
          ? `
            <div class="detail-row lean-over">
              Using posted lineup adjustment.
            </div>
          `
          : `
            <div class="detail-row lean-neutral">
              Lineup not available — using team vs-hand fallback.
            </div>
          `
      }

      ${lineHtml}

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

export function renderPitcherLineup(lineupData, projectionData) {
  const matchup = projectionData?.matchup || {};
  const opponentTeam = matchup.opponentTeam || "";

  const away = lineupData?.away || {};
  const home = lineupData?.home || {};

  let opponentBlock = null;

  if (away.team === opponentTeam) {
    opponentBlock = away;
  } else if (home.team === opponentTeam) {
    opponentBlock = home;
  }

  if (!opponentBlock) {
    els.pitcherLineup.innerHTML = `
      <div class="detail-card">
        <h3>Opponent Lineup</h3>
        <div class="muted">Could not match opponent lineup.</div>
      </div>
    `;
    return;
  }

  const batters = opponentBlock.batters || [];
  const env = opponentBlock.lineupEnvironment || {};

  if (!batters.length) {
    els.pitcherLineup.innerHTML = `
      <div class="detail-card">
        <h3>Opponent Lineup</h3>
        <div class="muted">Lineup not posted yet for ${esc(opponentTeam)}.</div>
      </div>
    `;
    return;
  }

  els.pitcherLineup.innerHTML = `
    <div class="detail-card">
      <h3>Opponent Lineup: ${esc(opponentTeam)}</h3>
      <div class="detail-row"><strong>Lineup K%:</strong> ${esc(env.lineupKRate ?? "")}</div>
      <div class="detail-row"><strong>Lineup Adj:</strong> ${esc(env.adjustment ?? "")}</div>
      <div class="detail-row muted">
        League K%: ${esc(env.leagueKRate ?? "")}
        ${env.source ? `| Source: ${esc(env.source)}` : ""}
      </div>

      ${(env.hitters?.length ? env.hitters : batters).map((b, idx) => `
        <div class="log-row">
          <div>
            <strong>${idx + 1}. ${esc(b.name || "Unknown")}</strong>
            ${b.position ? ` — ${esc(b.position)}` : ""}
          </div>
          <div class="muted">
            K%: ${esc(b.kRate ?? "")}
            | Raw K%: ${esc(b.rawKRate ?? "")}
            | PA: ${esc(b.plateAppearances ?? "")}
            | Wt: ${esc(b.spotWeight ?? "")}
            | Sample: ${esc(b.sampleWeight ?? "")}
            | K: ${esc(b.seasonStrikeOuts ?? "")}
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderEvBuckets(metrics) {
  const buckets = metrics?.evBuckets || {};

  const labels = {
    "0-5": "0% to 5%",
    "5-10": "5% to 10%",
    "10-20": "10% to 20%",
    "20-40": "20% to 40%",
    "40+": "40%+",
  };

  const order = ["0-5", "5-10", "10-20", "20-40", "40+"];

  return `
    <div style="margin-top:10px;"><strong>EV Buckets</strong></div>
    ${order.map((bucket) => {
      const row = buckets[bucket];

      if (!row || !row.count) {
        return `
          <div class="muted">
            ${esc(labels[bucket] || bucket)}: no settled picks
          </div>
        `;
      }

      return `
        <div class="muted">
          ${esc(labels[bucket] || bucket)}:
          ${esc(row.record || "0-0-0")}
          ${
            row.winRate != null
              ? ` | Win Rate: ${esc(Math.round(row.winRate * 100) + "%")}`
              : ""
          }
          ${
            row.units != null
              ? ` | Units: ${esc(Number(row.units).toFixed(2))}`
              : ""
          }
          ${
            row.roi != null
              ? ` | ROI: ${esc(Math.round(row.roi * 100) + "%")}`
              : ""
          }
          ${
            row.averageEV != null
              ? ` | Avg EV: ${esc(Number(row.averageEV).toFixed(2))}`
              : ""
          }
        </div>
      `;
    }).join("")}
  `;
}


function renderEvBucketsBySide(metrics) {
  const data = metrics?.evBucketsBySide || {};

  const labels = {
    "0-5": "0% to 5%",
    "5-10": "5% to 10%",
    "10-20": "10% to 20%",
    "20-40": "20% to 40%",
    "40+": "40%+",
  };

  const order = ["0-5", "5-10", "10-20", "20-40", "40+"];

  const renderSide = (side) => {
    const buckets = data[side] || {};

    return `
      <div style="margin-top:8px;"><strong>${esc(side.toUpperCase())}</strong></div>
      ${order.map((bucket) => {
        const row = buckets[bucket];

        if (!row || !row.count) {
          return `
            <div class="muted">
              ${esc(labels[bucket] || bucket)}: no settled picks
            </div>
          `;
        }

        return `
          <div class="muted">
            ${esc(labels[bucket] || bucket)}:
            ${esc(row.record || "0-0-0")}
            ${
              row.winRate != null
                ? ` | Win Rate: ${esc(Math.round(row.winRate * 100) + "%")}`
                : ""
            }
            ${
              row.units != null
                ? ` | Units: ${esc(Number(row.units).toFixed(2))}`
                : ""
            }
            ${
              row.roi != null
                ? ` | ROI: ${esc(Math.round(row.roi * 100) + "%")}`
                : ""
            }
            ${
              row.averageEV != null
                ? ` | Avg EV: ${esc(Number(row.averageEV).toFixed(2))}`
                : ""
            }
          </div>
        `;
      }).join("")}
    `;
  };

  return `
    <div style="margin-top:10px;"><strong>EV Buckets by Side</strong></div>
    ${renderSide("over")}
    ${renderSide("under")}
  `;
}

function renderLineBuckets(metrics) {
  const buckets = metrics?.lineBuckets || {};
  const order = ["3.5", "4.5", "5.5", "6.5+"];

  return `
    <div style="margin-top:10px;"><strong>Line Number Performance</strong></div>
    ${order.map((bucket) => {
      const row = buckets[bucket];

      if (!row || !row.count) {
        return `
          <div class="muted">
            ${esc(bucket)} Ks: no settled picks
          </div>
        `;
      }

      return `
        <div class="muted">
          ${esc(bucket)} Ks:
          ${esc(row.record || "0-0-0")}
          ${
            row.winRate != null
              ? ` | Win Rate: ${esc(Math.round(row.winRate * 100) + "%")}`
              : ""
          }
          ${
            row.units != null
              ? ` | Units: ${esc(Number(row.units).toFixed(2))}`
              : ""
          }
          ${
            row.roi != null
              ? ` | ROI: ${esc(Math.round(row.roi * 100) + "%")}`
              : ""
          }
          ${
            row.averageEV != null
              ? ` | Avg EV: ${esc(Number(row.averageEV).toFixed(2))}`
              : ""
          }
        </div>
      `;
    }).join("")}
  `;
}


export function renderTracked(data) {
  const predictions = data?.predictions || [];
  const filter = els.trackedFilter?.value || "all";
  const sort = els.trackedSort?.value || "newest";
  const metrics = data?.metrics || {};
  const counts = data?.counts || {};

  if (!predictions.length) {
    els.trackedOut.innerHTML = `<div class="muted">No tracked picks yet.</div>`;
    return;
  }

  const metricsHtml = `
    <div class="detail-card">
      <h3>Rolling Record</h3>
      <div class="muted">
        Total: ${esc(counts.total ?? 0)}
        | Pending: ${esc(counts.pending ?? 0)}
        | Settled: ${esc(counts.settled ?? 0)}
        | +EV: ${esc(counts.plusEV ?? 0)}
      </div>

      <div><strong>Record:</strong> ${esc(metrics.record || "0-0-0")}</div>
      <div><strong>Win Rate:</strong> ${
        metrics.winRate != null ? esc(Math.round(metrics.winRate * 100) + "%") : ""
      }</div>
      <div><strong>Units:</strong> ${esc(metrics.units ?? 0)}</div>
      <div><strong>ROI:</strong> ${
        metrics.roi != null ? esc(Math.round(metrics.roi * 100) + "%") : ""
      }</div>

      <div style="margin-top:8px;"><strong>Avg EV:</strong> ${
        metrics.averageEV != null ? esc(metrics.averageEV.toFixed(2)) : ""
      }</div>
      <div><strong>Avg Probability:</strong> ${
        metrics.averageProbability != null ? esc(Math.round(metrics.averageProbability * 100) + "%") : ""
      }</div>

      <div style="margin-top:8px;"><strong>Over Record:</strong> ${esc(metrics.overRecord || "0-0")}</div>
      <div><strong>Under Record:</strong> ${esc(metrics.underRecord || "0-0")}</div>
      <div><strong>+EV Record:</strong> ${esc(metrics.plusEVRecord || "0-0")}</div>

      <div style="margin-top:10px;"><strong>Calibration</strong></div>
      ${Object.entries(metrics.calibration || {}).map(([bucket, row]) => `
        <div class="muted">
          ${esc(bucket)}%:
          ${esc(row.record || "0-0-0")}
          ${
            row.winRate != null
              ? ` | Win Rate: ${esc(Math.round(row.winRate * 100) + "%")}`
              : ""
          }
        </div>
      `).join("")}


      ${renderEvBuckets(metrics)}
      ${renderEvBucketsBySide(metrics)}
      ${renderLineBuckets(metrics)}

      <div class="muted" style="margin-top:8px;">
        Settled Picks: ${esc(metrics.settled ?? 0)}
      </div>
    </div>
  `;

  const filteredPredictions = predictions.filter((p) => {
    const isSettled = p.settled === true || p.result;
    const sim = p.simulation || {};
    const side = (p.side || "").toLowerCase();

    const chosenEV =
      side === "over"
        ? sim.overEV
        : side === "under"
          ? sim.underEV
          : null;

    if (filter === "pending") return !isSettled;
    if (filter === "settled") return isSettled;
    if (filter === "plus_ev") return chosenEV != null && chosenEV > 0;

    return true;
  });

  const chosenEVForPick = (p) => {
    const side = (p.side || "").toLowerCase();
    const sim = p.simulation || {};

    if (side === "over") return sim.overEV ?? -999;
    if (side === "under") return sim.underEV ?? -999;
    return -999;
  };

  const chosenProbForPick = (p) => {
    const side = (p.side || "").toLowerCase();
    const sim = p.simulation || {};

    if (side === "over") return sim.probOver ?? -999;
    if (side === "under") return sim.probUnder ?? -999;
    return -999;
  };

  filteredPredictions.sort((a, b) => {
    const aSettled = a.settled === true || a.result;
    const bSettled = b.settled === true || b.result;

    if (sort === "highest_ev") {
      return chosenEVForPick(b) - chosenEVForPick(a);
    }

    if (sort === "highest_prob") {
      return chosenProbForPick(b) - chosenProbForPick(a);
    }

    if (sort === "pending_first") {
      return Number(aSettled) - Number(bSettled);
    }

    if (sort === "settled_first") {
      return Number(bSettled) - Number(aSettled);
    }

    return String(b.createdAt || "").localeCompare(String(a.createdAt || ""));
  });

  const filterHtml = `
    <div class="muted" style="margin:8px 0;">
      Showing ${esc(filteredPredictions.length)} pick(s) for filter: ${esc(filter)} | Sort: ${esc(sort)}
    </div>
  `;

  const cardsHtml = filteredPredictions.map((p) => {
    const isSettled = p.settled === true || p.result;
    const side = p.side || "";
    const sim = p.simulation || {};

    const chosenProb =
      side.toLowerCase() === "over"
        ? sim.probOver
        : side.toLowerCase() === "under"
          ? sim.probUnder
          : null;

    const chosenEV =
      side.toLowerCase() === "over"
        ? sim.overEV
        : side.toLowerCase() === "under"
          ? sim.underEV
          : null;

    const statusHtml = isSettled
      ? `
        <div class="detail-row">
          <strong>Status:</strong> Settled
          | <strong>Result:</strong> ${esc(p.result || "")}
          | <strong>Actual Ks:</strong> ${esc(p.actual ?? "")}
        </div>
      `
      : `
        <div class="detail-row">
          <strong>Status:</strong> Pending
        </div>
        <button
          class="settle-btn"
          data-id="${esc(p.id)}"
          data-game="${esc(p.matchup?.gameId ?? "")}"
          data-pitcher="${esc(p.pitcher?.id ?? "")}"
        >
          Settle
        </button>
      `;

    const clvHtml = p.clv
      ? `
        <div class="detail-row">
          <strong>CLV:</strong> ${esc(p.clv.clvSide || "")}
          | Original: ${esc(p.clv.originalLine ?? "")}
          | Current: ${esc(p.clv.currentLine ?? "")}
          | Move: ${esc(p.clv.lineMove ?? "")}
        </div>
        <div class="muted">
          Current Odds — Over: ${esc(p.clv.currentOverOdds ?? "")}
          | Under: ${esc(p.clv.currentUnderOdds ?? "")}
        </div>
      `
      : `<div class="muted">CLV not updated yet.</div>`;

    return `
      <div class="detail-card">
        ${statusHtml}

        <button
          class="clv-btn"
          data-id="${esc(p.id)}"
          data-pitcher-name="${esc(p.pitcher?.fullName || "")}"
          data-side="${esc(p.side || "")}"
          data-line="${esc(p.line ?? "")}"
        >
          Update CLV
        </button>

        <h3 style="margin-bottom:6px;">
          ${esc(p.pitcher?.fullName || "Unknown Pitcher")}
        </h3>

        <div class="detail-row">
          <strong>Opponent:</strong> ${esc(p.matchup?.opponentTeam || "")}
        </div>

        <div class="detail-row">
          <strong>Pick:</strong> ${esc(side)} ${esc(p.line ?? "")} Ks
        </div>

        <div class="detail-row">
          <strong>Projection:</strong> ${esc(p.projection?.strikeouts ?? "")}
        </div>

        <div class="detail-row">
          <strong>Model Prob:</strong>
          ${chosenProb != null ? esc(Math.round(chosenProb * 100) + "%") : ""}
        </div>

        <div class="detail-row">
          <strong>EV:</strong>
          ${chosenEV != null ? esc(chosenEV.toFixed(2)) : ""}
        </div>

        <div class="detail-row">
          <strong>EV Lean:</strong> ${esc(sim.evLean || "")}
        </div>

        ${clvHtml}

        <div class="muted" style="margin-top:8px;">
          Over: ${esc(Math.round((sim.probOver || 0) * 100))}%
          | Under: ${esc(Math.round((sim.probUnder || 0) * 100))}%
        </div>

        <div class="muted">
          Over EV: ${sim.overEV != null ? esc(sim.overEV.toFixed(2)) : ""}
          | Under EV: ${sim.underEV != null ? esc(sim.underEV.toFixed(2)) : ""}
        </div>

        <div class="muted">
          Tracked: ${esc(p.createdAt || "")}
        </div>

        ${
          p.settledAt
            ? `<div class="muted">Settled: ${esc(p.settledAt)}</div>`
            : ""
        }
      </div>
    `;
  }).join("");

  els.trackedOut.innerHTML = metricsHtml + filterHtml + cardsHtml;
}


export function renderBestPicks(data) {
  const predictions = data?.predictions || [];

  const pendingPlusEV = predictions
    .filter((p) => !(p.settled === true || p.result))
    .map((p) => {
      const side = (p.side || "").toLowerCase();
      const sim = p.simulation || {};

      const chosenEV =
        side === "over"
          ? sim.overEV
          : side === "under"
            ? sim.underEV
            : null;

      const chosenProb =
        side === "over"
          ? sim.probOver
          : side === "under"
            ? sim.probUnder
            : null;

      return {
        ...p,
        chosenEV,
        chosenProb,
      };
    })
    .filter((p) => p.chosenEV != null && p.chosenEV > 0)
    .sort((a, b) => b.chosenEV - a.chosenEV)
    .slice(0, 5);

  if (!pendingPlusEV.length) {
    els.bestPicksOut.innerHTML = `<div class="muted">No pending +EV picks right now.</div>`;
    return;
  }

  els.bestPicksOut.innerHTML = pendingPlusEV.map((p, idx) => `
    <div class="detail-card">
      <h3>#${idx + 1} ${esc(p.pitcher?.fullName || "Unknown Pitcher")}</h3>

      <div class="detail-row">
        <strong>Pick:</strong> ${esc(p.side || "")} ${esc(p.line ?? "")} Ks
      </div>

      <div class="detail-row">
        <strong>Opponent:</strong> ${esc(p.matchup?.opponentTeam || "")}
      </div>

      <div class="detail-row">
        <strong>Projection:</strong> ${esc(p.projection?.strikeouts ?? "")}
      </div>

      <div class="detail-row">
        <strong>Model Prob:</strong>
        ${p.chosenProb != null ? esc(Math.round(p.chosenProb * 100) + "%") : ""}
      </div>

      <div class="detail-row">
        <strong>EV:</strong>
        ${p.chosenEV != null ? esc(p.chosenEV.toFixed(2)) : ""}
      </div>

      <div class="detail-row">
        <strong>EV Lean:</strong> ${esc(p.simulation?.evLean || "")}
      </div>

      <div class="muted">
        Tracked: ${esc(p.createdAt || "")}
      </div>
    </div>
  `).join("");
}


export function renderAutoBestPicks(data, trackedData = null) {
  const picks = data?.picks || [];
  const tracked = trackedData?.predictions || [];

  const filter = els.bestPicksFilter?.value || "all";
  const sort = els.bestPicksSort?.value || "highest_ev";

  const trackedKeys = new Set(
    tracked.map((p) => {
      const pitcherId = p.pitcher?.id;
      const gameId = p.matchup?.gameId;
      const side = p.side;
      const line = p.line;
      return `${pitcherId}|${gameId}|${side}|${line}`;
    })
  );

  let visiblePicks = picks.map((p, originalIndex) => {
    const key = `${p.pitcher?.id}|${p.matchup?.gameId}|${p.side}|${p.line}`;
    return {
      ...p,
      originalIndex,
      alreadyTracked: trackedKeys.has(key),
    };
  });

  if (filter === "strong_ev") {
    visiblePicks = visiblePicks.filter((p) => (p.ev ?? 0) >= 0.15);
  }

  if (filter === "untracked") {
    visiblePicks = visiblePicks.filter((p) => !p.alreadyTracked);
  }

  visiblePicks.sort((a, b) => {
    if (sort === "highest_prob") {
      return (b.probability ?? -999) - (a.probability ?? -999);
    }

    return (b.ev ?? -999) - (a.ev ?? -999);
  });

  if (!visiblePicks.length) {
    els.bestPicksOut.innerHTML = `
      <div class="muted">
        No auto picks match this filter.
      </div>
    `;
    return;
  }

  els.bestPicksOut.innerHTML = `
    <div class="muted">
      Scanned ${esc(data.pitchersScanned ?? "")} pitcher(s)
      | Found ${esc(data.count ?? picks.length)} +EV play(s)
      | Showing ${esc(visiblePicks.length)}
      | Date: ${esc(data.date || "")}
    </div>

    ${visiblePicks.map((p, idx) => `
      <div class="detail-card">
        <h3>#${idx + 1} ${esc(p.pitcher?.fullName || "Unknown Pitcher")}</h3>

        ${
          p.alreadyTracked
            ? `<div class="detail-row lean-neutral"><strong>Already tracked</strong></div>`
            : `
              <button class="track-auto-btn" data-index="${esc(picks.indexOf(p))}">
                Track This Pick
              </button>
            `
        }

        <div class="detail-row">
          <strong>Pick:</strong> ${esc(p.side || "")} ${esc(p.line ?? "")} Ks
        </div>

        <div class="detail-row">
          <strong>Opponent:</strong> ${esc(p.matchup?.opponentTeam || "")}
        </div>

        <div class="detail-row">
          <strong>Projection:</strong> ${esc(p.projection?.strikeouts ?? "")}
        </div>

        <div class="detail-row">
          <strong>Probability:</strong>
          ${p.probability != null ? esc(Math.round(p.probability * 100) + "%") : ""}
        </div>

        <div class="detail-row">
          <strong>EV:</strong> ${p.ev != null ? esc(p.ev.toFixed(2)) : ""}
        </div>

        <div class="detail-row">
          <strong>EV Lean:</strong> ${esc(p.simulation?.evLean || "")}
        </div>

        <div class="muted">
          Over: ${esc(Math.round((p.simulation?.probOver || 0) * 100))}%
          | Under: ${esc(Math.round((p.simulation?.probUnder || 0) * 100))}%
        </div>

        <div class="muted">
          Team Adj: ${esc(p.opponentEnvironment?.teamAdjustment ?? "")}
          | Lineup Adj: ${esc(p.opponentEnvironment?.lineupAdjustment ?? "")}
          | Source: ${esc(p.opponentEnvironment?.source || "")}
        </div>
      </div>
    `).join("")}
  `;
}

