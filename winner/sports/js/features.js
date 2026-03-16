// winner/sports/js/features.js
import { els } from "./dom.js";
import { state } from "./state.js";
import { api } from "./api.js";
import { loadUnderdogLinesForAthlete } from "./underdog_lines.js";
import {
  escapeHtml,
  parseAmericanOdds,
  impliedProbFromAmerican,
  netPayoutPerDollar,
  kellyFraction
} from "./utils.js";
import {
  openModal, openSide,
  clearRoster,
  renderGameList,
  renderExplanationFromAssess,
  renderTrackingTable,
} from "./render.js";

/* =========================
   TEAM PICKS (Top 2)
========================= */

let teamPicksWired = false;

function setTeamPicksStatus(msg){
  if (els.teamPicksStatus) els.teamPicksStatus.textContent = msg;
}
function setTeamPicksResults(html){
  if (els.teamPicksResults) els.teamPicksResults.innerHTML = html;
}

function fmtOdds(n){
  if (n == null) return "—";
  const v = Number(n);
  if (!Number.isFinite(v)) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

function asyncPool(limit, items, iteratorFn){
  let i = 0;
  const results = [];
  const workers = new Array(Math.max(1, limit)).fill(0).map(async () => {
    while (i < items.length){
      const idx = i++;
      results[idx] = await iteratorFn(items[idx], idx);
    }
  });
  return Promise.all(workers).then(() => results);
}

async function fetchJsonWithTimeout(url, ms = 8000){
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try{
    const res = await fetch(url, { signal: ctrl.signal });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  } finally {
    clearTimeout(t);
  }
}

async function postJsonWithTimeout(url, payload, ms = 12000){
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try{
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type":"application/json" },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  } finally {
    clearTimeout(t);
  }
}

async function getUdLines(athleteId){
  const data = await fetchJsonWithTimeout(`/api/nba/underdog_lines?athleteId=${athleteId}`, 8000);
  return Array.isArray(data.lines) ? data.lines : [];
}

async function assessLine(athleteId, stat, line){
  const payload = { athleteId, stat, line };
  if (state.currentOpponentTeamId) payload.opponentTeamId = Number(state.currentOpponentTeamId);
  if (state.currentGameId) payload.gameId = String(state.currentGameId);
  return postJsonWithTimeout(`/api/nba/assess_line`, payload, 12000);
}

function renderPickSection(title, picks){
  if (!picks.length){
    return `
      <div class="player-section">
        <h3>${escapeHtml(title)}</h3>
        <div class="muted small">No picks found.</div>
      </div>
    `;
  }

  const rows = picks.map(p => {
    const evTxt = (p.evPerDollar == null) ? "—" : (p.evPerDollar >= 0 ? `+${p.evPerDollar.toFixed(3)}` : p.evPerDollar.toFixed(3));
    const edgeTxt = (p.edgeVsImplied == null) ? "—" : `${(p.edgeVsImplied >= 0 ? "+" : "")}${(p.edgeVsImplied*100).toFixed(1)}%`;
    const probTxt = (typeof p.prob === "number") ? `${Math.round(p.prob*100)}%` : "—";

    return `
      <div class="last5-row">
        <div class="left">
          <b>${escapeHtml(p.name)}</b><br/>
          ${escapeHtml(p.side)} ${escapeHtml(p.line.toFixed(1))} ${escapeHtml(p.stat.toUpperCase())}
          <span class="muted small"> • proj p50 ${escapeHtml(p.projP50.toFixed(1))}</span>
        </div>
        <div class="right">
          <div><span class="muted small">P</span> ${escapeHtml(probTxt)}</div>
          <div><span class="muted small">Odds</span> ${escapeHtml(fmtOdds(p.odds))}</div>
          <div><span class="muted small">Edge</span> ${escapeHtml(edgeTxt)}</div>
          <div><span class="muted small">EV/$</span> ${escapeHtml(evTxt)}</div>
        </div>
      </div>
    `;
  }).join("");

  return `
    <div class="player-section">
      <h3>${escapeHtml(title)}</h3>
      ${rows}
    </div>
  `;
}

function renderTeamPicks(topOverall, topOver){
  const html =
    `<div class="muted small">DEBUG NEW RENDER</div>` +
    renderPickSection("Top 2 Overall", topOverall) +
    renderPickSection("Best Over", topOver);

  setTeamPicksResults(html);
}

async function computeTopPicksTop2(){
  // immediate feedback so you know the click fired
  const roster = Array.isArray(state.currentRosterAthletes) ? state.currentRosterAthletes : [];
  setTeamPicksStatus(`Clicked • rosterCount=${roster.length} • fetching lines…`);
  setTeamPicksResults(`<div class="muted small">Working…</div>`);

  if (!roster.length){
    setTeamPicksStatus("Pick a team first (open a roster), then click Top 2.");
    setTeamPicksResults("");
    return;
  }

  if (els.teamPicksBtn) els.teamPicksBtn.disabled = true;

  try{
    // 1) Fetch lines for each athlete (skip slow/failing players)
    const lineRows = await asyncPool(4, roster, async (p) => {
      try{
        const lines = await getUdLines(p.id);
        return { p, lines };
      } catch (e){
        return { p, lines: [], err: e?.message || String(e) };
      }
    });

    let totalLines = 0;
    const jobs = [];
    for (const row of lineRows){
      const lines = row.lines || [];
      for (const l of lines){
        if (!l?.statKey || typeof l?.line !== "number") continue;
        
        if (String(l.statKey).toLowerCase() !== "pts") continue;
        jobs.push({ player: row.p, lineObj: l });
        totalLines += 1;
      }
    }

    if (!jobs.length){
      setTeamPicksStatus(
        `No usable UD PTS/REB/AST lines for this roster. (Tip: confirm /api/nba/underdog_lines works for a few players.)`
      );
      setTeamPicksResults("");
      return;
    }

    setTeamPicksStatus(`Found ${jobs.length} lines • assessing…`);

    // 2) Assess each job (skip slow/failing assessments)
    const assessed = await asyncPool(3, jobs, async (job) => {
      const { player, lineObj } = job;
      const stat = lineObj.statKey;
      const line = lineObj.line;

      try{
        const a = await assessLine(player.id, stat, line);

        const probOver = (typeof a.probOver === "number") ? a.probOver : null;
        if (probOver == null) return null;

        const projP50 = (typeof a.projectionP50 === "number")
          ? a.projectionP50
          : (typeof a.fairLine === "number" ? a.fairLine : line);

        // pick best side via EV if odds exist, otherwise fallback score
        const overOdds = lineObj.overOdds;
        const underOdds = lineObj.underOdds;

        function scoreSide(prob, odds){
          let evPerDollar = null;
          let edgeVsImplied = null;

          if (odds != null && Number.isFinite(Number(odds))){
            const implied = impliedProbFromAmerican(Number(odds));
            const payout = netPayoutPerDollar(Number(odds));
            if (implied != null && payout != null){
              evPerDollar = (prob * payout) - (1 - prob);
              edgeVsImplied = prob - implied;
            }
          }

          const score = (evPerDollar != null) ? evPerDollar : (prob - 0.5);

          return { evPerDollar, edgeVsImplied, score };
        }

        const over = scoreSide(probOver, overOdds);
        const under = scoreSide(1 - probOver, underOdds);

        const pickOver = over.score >= under.score;

        return {
          athleteId: player.id,
          name: player.name,
          stat,
          line,
          side: pickOver ? "OVER" : "UNDER",
          prob: pickOver ? probOver : (1 - probOver),
          odds: pickOver ? (overOdds ?? null) : (underOdds ?? null),
          evPerDollar: pickOver ? over.evPerDollar : under.evPerDollar,
          edgeVsImplied: pickOver ? over.edgeVsImplied : under.edgeVsImplied,
          projP50,
          score: pickOver ? over.score : under.score
        };
      } catch {
        return null;
      }
    });

      const allPicks = assessed
        .filter(Boolean)
        .sort((a,b) => (b.score ?? -999) - (a.score ?? -999));

      const topOverall = allPicks.slice(0, 2);

      const topOver = allPicks
        .filter(p => p.side === "OVER")
        .slice(0, 1);

      setTeamPicksStatus(
        `Top ${topOverall.length} overall • best over ${topOver.length ? "found" : "not found"} • ${state.currentTeamName || "team"} • opponent ${state.currentOpponentTeamId || "—"}`
      );

      renderTeamPicks(topOverall, topOver);
  } catch (e){
    setTeamPicksStatus(`Team picks failed: ${e?.message || e}`);
    setTeamPicksResults("");
  } finally {
    if (els.teamPicksBtn) els.teamPicksBtn.disabled = false;
  }
}

function wireTeamPicks(){
  if (teamPicksWired) return;
  if (!els.teamPicksBtn || !els.teamPicksStatus || !els.teamPicksResults) return;

  teamPicksWired = true;
  els.teamPicksBtn.textContent = "Top 2";
  els.teamPicksBtn.addEventListener("click", () => {
    computeTopPicksTop2();
  });
}

/* =========================
   EXISTING WORKING FEATURES
========================= */

export async function loadRoster(teamId, teamName, loadPlayer){
  openSide(true);
  els.sideTitle.textContent = `${teamName} — Roster`;
  els.sideMeta.textContent = "Loading roster…";
  clearRoster();

  // set context for team picks
  state.currentTeamId = teamId;
  state.currentTeamName = teamName;
  state.currentRosterAthletes = [];

  wireTeamPicks();
  setTeamPicksStatus(`Click “Top 2” to rank picks for ${teamName}.`);
  setTeamPicksResults("");

  try{
    const data = await api.roster(teamId);

    let athletes = [];
    if (Array.isArray(data.athletes)){
      if (data.athletes.length && Array.isArray(data.athletes[0]?.items)){
        for (const group of data.athletes){
          for (const it of (group.items || [])) athletes.push(it);
        }
      } else {
        athletes = data.athletes;
      }
    }

    if (!athletes.length){
      els.sideMeta.textContent = "Roster not found (ESPN format changed).";
      return;
    }

    // normalize roster first
    const normalized = athletes.map(p => {
      const id = p.id || p.athlete?.id;
      const fullName = p.fullName || p.displayName || p.athlete?.displayName || "Player";
      const pos = p.position?.abbreviation || p.athlete?.position?.abbreviation || "";
      const jersey = p.jersey || p.athlete?.jersey || "";

      return id ? {
        id: String(id),
        name: fullName,
        pos,
        jersey,
      } : null;
    }).filter(Boolean);

    // only keep players who have active lines
    const withLines = await asyncPool(4, normalized, async (p) => {
      try{
        const lines = await getUdLines(p.id);
        const usable = Array.isArray(lines) && lines.length > 0;
        return usable ? { ...p, lines } : null;
      } catch {
        return null;
      }
    });

    const filtered = withLines.filter(Boolean);

    if (!filtered.length){
      els.sideMeta.textContent = "No active Underdog lines found for this team.";
      state.currentRosterAthletes = [];
      return;
    }

    els.sideMeta.textContent = `${filtered.length} players with active lines — click a player`;

    state.currentRosterAthletes = filtered.map(p => ({
      id: p.id,
      name: p.name,
    }));

    for (const p of filtered){
      const row = document.createElement("div");
      row.className = "player";
      row.innerHTML = `
        <div>
          <div class="pName">${escapeHtml(p.name)}</div>
          <div class="pMeta">${escapeHtml([p.pos, p.jersey ? `#${p.jersey}` : ""].filter(Boolean).join(" • "))}</div>
        </div>
        <div class="pMeta">➜</div>
      `;

      row.addEventListener("click", async () => {
        await loadPlayer(p.id, p.name);
      });

      els.roster.appendChild(row);
    }
  } catch (e){
    els.sideMeta.textContent = `Could not load roster. (${e.message})`;
  }
}
export async function loadLast5(athleteId){
  if (!els.last5) return;
  els.last5.innerHTML = `<div class="muted">Loading last 5 games…</div>`;
  try{
    const data = await api.gamelog(athleteId, 5);
    renderGameList(els.last5, data.games || []);
  } catch (e){
    els.last5.innerHTML = `<div class="muted">Could not load last 5 games. (${escapeHtml(e.message)})</div>`;
  }
}

export async function loadVsOpponent(athleteId){
  if (!els.vsOpp) return;
  if (!state.currentOpponentTeamId){
    els.vsOpp.innerHTML = `<div class="muted">Pick an opponent by clicking a game/team.</div>`;
    return;
  }
  els.vsOpp.innerHTML = `<div class="muted">Loading vs opponent…</div>`;
  try{
    const data = await api.vsOpponent(athleteId, state.currentOpponentTeamId, 25);
    renderGameList(els.vsOpp, data.games || []);
  } catch (e){
    els.vsOpp.innerHTML = `<div class="muted">Could not load vs opponent. (${escapeHtml(e.message)})</div>`;
  }
}

export async function loadProjection(athleteId){
  if (els.pPts) els.pPts.textContent = "—";
  if (els.pReb) els.pReb.textContent = "—";
  if (els.pAst) els.pAst.textContent = "—";
  if (els.projNote) els.projNote.textContent = "Loading projection…";

  try{
    const data = await api.projection(athleteId, state.currentOpponentTeamId, state.currentGameId);
    const p = data.projection || {};
    const meta = data.meta || {};

    if (els.pPts) els.pPts.textContent = (typeof p.pts === "number") ? p.pts.toFixed(1) : "—";
    if (els.pReb) els.pReb.textContent = (typeof p.reb === "number") ? p.reb.toFixed(1) : "—";
    if (els.pAst) els.pAst.textContent = (typeof p.ast === "number") ? p.ast.toFixed(1) : "—";

    const mins = (typeof meta.estMinutes === "number") ? meta.estMinutes.toFixed(1) : "—";
    const conf = meta.confidence || "—";
    const engine = meta.ptsEngine ? ` • pts engine: ${meta.ptsEngine}` : "";
    if (els.projNote) els.projNote.textContent = `Projection (est ${mins} min) • confidence: ${conf}${engine}`;
  } catch (e){
    if (els.projNote) els.projNote.textContent = `Could not load projection. (${e.message})`;
  }
}

export async function assessManualLine(){
  if (!state.currentAthleteId) return;

  const stat = (els.manualStat?.value || "pts").toLowerCase();
  const lineRaw = els.manualLine?.value;
  const line = parseFloat(lineRaw);

  if (!Number.isFinite(line)){
    if (els.assessResult) els.assessResult.textContent = "Enter a valid numeric line (ex: 25.5).";
    return;
  }

  if (els.assessResult) els.assessResult.textContent = "Calculating…";
  if (els.explainBody) els.explainBody.textContent = "Calculating model details…";

  try{
    const payload = { athleteId: state.currentAthleteId, stat, line };
    if (state.currentOpponentTeamId) payload.opponentTeamId = Number(state.currentOpponentTeamId);
    if (state.currentGameId) payload.gameId = String(state.currentGameId);

    const data = await api.assessLine(payload);

    const prob = (typeof data.probOver === "number") ? data.probOver : null;
    const odds = parseAmericanOdds(els.manualOdds?.value);
    const implied = (odds != null) ? impliedProbFromAmerican(odds) : null;
    const payout = (odds != null) ? netPayoutPerDollar(odds) : null;

    let evPerDollar = null;
    let edgeVsImplied = null;
    let kelly = null;

    if (odds != null && prob != null && payout != null){
      evPerDollar = (prob * payout) - (1 - prob);
      if (implied != null) edgeVsImplied = prob - implied;
      kelly = kellyFraction(prob, odds);
    }

    const pct = (prob == null) ? "—" : `${Math.round(prob * 100)}%`;

    const p50 = (typeof data.projectionP50 === "number") ? data.projectionP50.toFixed(1) : "—";
    const band = data.band ? `p10 ${data.band.p10} • p50 ${data.band.p50} • p90 ${data.band.p90}` : "";

    if (els.assessResult){
      const oddsTxt = (odds == null) ? "—" : (odds > 0 ? `+${odds}` : `${odds}`);
      const impliedTxt = (implied == null) ? "—" : `${Math.round(implied * 1000)/10}%`;
      const edgeTxt = (edgeVsImplied == null) ? "—" : `${(edgeVsImplied >= 0 ? "+" : "")}${Math.round(edgeVsImplied * 1000)/10}%`;
      const evTxt = (evPerDollar == null) ? "—" : `${(evPerDollar >= 0 ? "+" : "")}${evPerDollar.toFixed(3)}`;
      const kellyTxt = (kelly == null) ? "—" : `${Math.round(kelly * 1000)/10}%`;

      els.assessResult.innerHTML =
        `<b>${pct}</b> chance to go OVER ${line.toFixed(1)} ${stat.toUpperCase()}<br/>
        median=${p50}${band ? `<br/>${escapeHtml(band)}` : ""}<br/>
        fair line=${data.fairLine ?? "—"} • samples=${data.meta?.nSamples ?? "—"}<br/><br/>
        Odds=${escapeHtml(oddsTxt)} • implied=${escapeHtml(impliedTxt)} • edge=${escapeHtml(edgeTxt)}<br/>
        EV per $1=${escapeHtml(evTxt)} • Kelly=${escapeHtml(kellyTxt)} (suggest 1/2 Kelly)`;
    }

    renderExplanationFromAssess(stat, data);
  } catch (e){
    if (els.assessResult) els.assessResult.textContent = `Could not assess line. (${e.message})`;
    if (els.explainBody) els.explainBody.textContent = `No explanation available. (${e.message})`;
  }
}

export async function loadTracking(){
  const athleteId = state.currentAthleteId;
  if (!athleteId) return;
  if (els.trackMeta) els.trackMeta.textContent = "Loading tracked predictions…";

  try{
    const data = await api.tracked(athleteId);
    const preds = data.predictions || [];

    renderTrackingTable(preds, async (id, btn) => {
      btn.textContent = "…";
      try{
        await api.settle(id);
        await loadTracking();
      } catch (e){
        alert(`Settle failed: ${e.message}`);
      } finally {
        btn.textContent = "Settle";
      }
    });

    const settled = preds.filter(p => p.settledAt && p.actual != null);
    const over = settled.filter(p => p.result === "over").length;
    const under = settled.filter(p => p.result === "under").length;

    if (els.trackMeta){
      els.trackMeta.textContent = `${preds.length} tracked • settled: ${settled.length} (OVER ${over} / UNDER ${under})`;
    }
  } catch (e){
    if (els.trackMeta) els.trackMeta.textContent = `Could not load tracking. (${e.message})`;
  }
}

export async function trackCurrent(){
  if (!state.currentAthleteId) return;

  const stat = (els.manualStat?.value || "pts").toLowerCase();
  const line = parseFloat(els.manualLine?.value);

  if (!Number.isFinite(line)){
    alert("Enter a line first (ex: 25.5), then Track.");
    return;
  }

  const typedGameId = (els.trackGameId?.value || "").trim();
  const gameId = typedGameId || state.currentGameId || null;
  const gameDate = state.currentGameDateIso || null;

  try{
    const assessPayload = { athleteId: state.currentAthleteId, stat, line };
    if (state.currentOpponentTeamId) assessPayload.opponentTeamId = Number(state.currentOpponentTeamId);

    const assessRes = await api.assessLine(assessPayload);

    const payload = {
      athleteId: state.currentAthleteId,
      stat,
      line,
      probOver: assessRes.probOver,
      fairLine: assessRes.fairLine,
      projectionP50: assessRes.projectionP50,
      opponentTeamId: assessRes.meta?.opponentTeamId ?? (state.currentOpponentTeamId ? Number(state.currentOpponentTeamId) : null),
      gameId,
      gameDate,
      meta: {
        minutesMu: assessRes.meta?.minutesMu,
        minutesSd: assessRes.meta?.minutesSd,
        minutesStability: assessRes.meta?.minutesStability,
        ptsEngine: assessRes.meta?.ptsEngine,
        nSamples: assessRes.meta?.nSamples,
      }
    };

    await api.track(payload);
    await loadTracking();
  } catch (e){
    alert(`Track failed: ${e.message}`);
  }
}

export async function loadPlayer(athleteId, name){
  state.currentAthleteId = athleteId;

  openModal(true);
  els.playerName.textContent = name;
  els.playerTeam.textContent = "Loading…";

  els.pts.textContent = "—";
  els.reb.textContent = "—";
  els.ast.textContent = "—";
  els.playerNote.textContent = "";

  if (els.assessResult) els.assessResult.textContent = "Enter a line and press Assess.";
  if (els.explainBody) els.explainBody.textContent = "Assess a line to see edge + model inputs.";

  if (els.trackGameId){
    els.trackGameId.value = state.currentGameId || "";
  }

  loadLast5(athleteId);
  loadProjection(athleteId);
  loadTracking();
  loadVsOpponent(athleteId);
  loadUnderdogLinesForAthlete(athleteId);

  try{
    const data = await api.player(athleteId);

    els.playerName.textContent = data.name || name;
    els.playerTeam.textContent = data.team || "—";

    const avg = data.seasonAverages || {};
    const pts = avg.pts, reb = avg.reb, ast = avg.ast;

    els.pts.textContent = (typeof pts === "number") ? pts.toFixed(1) : "—";
    els.reb.textContent = (typeof reb === "number") ? reb.toFixed(1) : "—";
    els.ast.textContent = (typeof ast === "number") ? ast.toFixed(1) : "—";

    els.playerNote.textContent =
      (pts == null || reb == null || ast == null)
        ? "Couldn’t find PTS/REB/AST in ESPN’s stats response for this player."
        : "Season per-game averages.";
  } catch (e){
    els.playerTeam.textContent = "—";
    els.playerNote.textContent = `Could not load player stats. (${e.message})`;
  }
}