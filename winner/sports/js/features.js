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

export async function loadRoster(teamId, teamName, loadPlayer){
  openSide(true);
  els.sideTitle.textContent = `${teamName} — Roster`;
  els.sideMeta.textContent = "Loading roster…";
  clearRoster();

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

    els.sideMeta.textContent = `${athletes.length} players — click a player`;

    for (const p of athletes){
      const id = p.id || p.athlete?.id;
      const fullName = p.fullName || p.displayName || p.athlete?.displayName || "Player";
      const pos = p.position?.abbreviation || p.athlete?.position?.abbreviation || "";
      const jersey = p.jersey || p.athlete?.jersey || "";

      const row = document.createElement("div");
      row.className = "player";
      row.innerHTML = `
        <div>
          <div class="pName">${escapeHtml(fullName)}</div>
          <div class="pMeta">${escapeHtml([pos, jersey ? `#${jersey}` : ""].filter(Boolean).join(" • "))}</div>
        </div>
        <div class="pMeta">➜</div>
      `;

      row.addEventListener("click", async () => {
        if (!id) return;
        await loadPlayer(id, fullName);
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
    const data = await api.projection(athleteId, state.currentOpponentTeamId);
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

  // ✅ NEW: auto-fill gameId from state if input empty
  const gameIdFromBox = (els.trackGameId?.value || "").trim();
  const gameId = gameIdFromBox || state.currentGameId || null;

  try{
    const assessPayload = { athleteId: state.currentAthleteId, stat, line };
    if (state.currentOpponentTeamId) assessPayload.opponentTeamId = Number(state.currentOpponentTeamId);

    const assess = await api.assessLine(assessPayload);

    const payload = {
      athleteId: state.currentAthleteId,
      stat,
      line,
      probOver: assess.probOver,
      fairLine: assess.fairLine,
      projectionP50: assess.projectionP50,
      opponentTeamId: assess.meta?.opponentTeamId ?? (state.currentOpponentTeamId ? Number(state.currentOpponentTeamId) : null),

      // ✅ IMPORTANT: now usually non-null
      gameId,

      // optional nice-to-have
      gameDate: state.currentGameDateIso || null,

      meta: {
        minutesMu: assess.meta?.minutesMu,
        minutesSd: assess.meta?.minutesSd,
        minutesStability: assess.meta?.minutesStability,
        ptsEngine: assess.meta?.ptsEngine,
        nSamples: assess.meta?.nSamples,
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

  // ✅ NEW: auto-fill the trackGameId input with current selected game
  if (els.trackGameId){
    els.trackGameId.value = state.currentGameId ? String(state.currentGameId) : "";
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