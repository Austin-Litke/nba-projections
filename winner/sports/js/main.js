const els = {
  games: document.getElementById("games"),
  status: document.getElementById("status"),
  dateLabel: document.getElementById("dateLabel"),
  refreshBtn: document.getElementById("refreshBtn"),
  refreshLabel: document.getElementById("refreshLabel"),

  side: document.getElementById("side"),
  sideTitle: document.getElementById("sideTitle"),
  sideMeta: document.getElementById("sideMeta"),
  roster: document.getElementById("roster"),
  closeSideBtn: document.getElementById("closeSideBtn"),

  modal: document.getElementById("modal"),
  playerName: document.getElementById("playerName"),
  playerTeam: document.getElementById("playerTeam"),
  pts: document.getElementById("pts"),
  reb: document.getElementById("reb"),
  ast: document.getElementById("ast"),
  playerNote: document.getElementById("playerNote"),
  closeModalBtn: document.getElementById("closeModalBtn"),

  // last 5
  last5: document.getElementById("playerLast5"),

  // vs opponent this season
  vsOpp: document.getElementById("playerVsOpp"),

  // projection
  pPts: document.getElementById("pPts"),
  pReb: document.getElementById("pReb"),
  pAst: document.getElementById("pAst"),
  projNote: document.getElementById("projNote"),

  // manual line assess
  manualLine: document.getElementById("manualLine"),
  manualStat: document.getElementById("manualStat"),
  assessBtn: document.getElementById("assessBtn"),
  assessResult: document.getElementById("assessResult"),

  // tracking
  trackBtn: document.getElementById("trackBtn"),
  trackChart: document.getElementById("trackChart"),
  trackTable: document.getElementById("trackTable"),
};

const REFRESH_MS = 15000;
const MAX_LOOKAHEAD_DAYS = 14;

let currentAthleteId = null;
let currentOpponentTeamId = null;
let currentGameId = null;

// Stores the last assess response so Track can save it
let lastAssessment = null;

function escapeHtml(s){
  return String(s)
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

function fmtLocalTime(iso){
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour:"numeric", minute:"2-digit" });
}

function badgeFor(status){
  const s = (status || "").toLowerCase();
  if (s.includes("final")) return { text: "FINAL", cls: "final" };
  if (s.includes("in progress") || s.includes("halftime") || s.includes("end") || s.includes("q")) return { text: "LIVE", cls: "live" };
  return { text: "SCHEDULED", cls: "" };
}

function clearGames(){ els.games.innerHTML = ""; }
function clearRoster(){
  els.roster.innerHTML = "";
  els.sideMeta.textContent = "—";
}

function openModal(on){
  els.modal.classList.toggle("on", !!on);
}

function openSide(on){
  els.side.style.display = on ? "" : "none";
}

function gameCard(g){
  const comp = g.competitions?.[0];
  const statusText = comp?.status?.type?.detail || comp?.status?.type?.description || "Scheduled";
  const badge = badgeFor(statusText);

  const competitors = comp?.competitors || [];
  const away = competitors.find(c => c.homeAway === "away") || competitors[0];
  const home = competitors.find(c => c.homeAway === "home") || competitors[1];

  const awayTeam = away?.team || {};
  const homeTeam = home?.team || {};

  const awayName = awayTeam.displayName || awayTeam.shortDisplayName || "Away";
  const homeName = homeTeam.displayName || homeTeam.shortDisplayName || "Home";

  const awayScore = away?.score ?? "";
  const homeScore = home?.score ?? "";

  const awayId = awayTeam.id;
  const homeId = homeTeam.id;

  // game id for tracking (scoreboard usually has g.id)
  const gameId = g.id || comp?.id || g.uid || null;

  const startIso = comp?.date || g.date;
  const timeLabel = startIso ? fmtLocalTime(startIso) : "—";
  const note = comp?.venue?.fullName ? comp.venue.fullName : (g.name || "");

  const div = document.createElement("div");
  div.className = "game";

  div.innerHTML = `
    <div class="teams">
      <div class="team">
        <button class="teamBtn" data-teamid="${awayId || ""}" data-teamname="${escapeHtml(awayName)}">${escapeHtml(awayName)}</button>
        <div class="score">${awayScore}</div>
      </div>
      <div class="team">
        <button class="teamBtn" data-teamid="${homeId || ""}" data-teamname="${escapeHtml(homeName)}">${escapeHtml(homeName)}</button>
        <div class="score">${homeScore}</div>
      </div>
    </div>
    <div class="meta">
      <div class="badge ${badge.cls}">${badge.text}</div>
      <div class="time">${timeLabel}</div>
      <div class="note">${escapeHtml(note || "")}</div>
    </div>
  `;

  div.querySelectorAll(".teamBtn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const teamId = btn.dataset.teamid;
      const teamName = btn.dataset.teamname || "Team";
      if (!teamId) return;

      // opponent is the other team in this game
      const oppId = (String(teamId) === String(awayId)) ? homeId : awayId;

      await loadRoster(teamId, teamName, oppId, gameId);
    });
  });

  return div;
}

function yyyymmddFromDate(d){
  const y = d.getFullYear();
  const m = String(d.getMonth()+1).padStart(2,"0");
  const day = String(d.getDate()).padStart(2,"0");
  return `${y}${m}${day}`;
}

async function load(){
  const today = new Date();
  els.status.textContent = "Loading…";
  clearGames();

  let chosenDate = null;
  let chosenEvents = null;

  for (let offset = 0; offset <= MAX_LOOKAHEAD_DAYS; offset++){
    const d = new Date(today);
    d.setDate(today.getDate() + offset);
    const dateStr = yyyymmddFromDate(d);

    const res = await fetch(`/api/nba/scoreboard?date=${dateStr}`);
    if (!res.ok){
      els.status.textContent = `Could not load scores. (HTTP ${res.status})`;
      return;
    }

    const data = await res.json();
    const events = data.events || [];
    if (events.length){
      chosenDate = d;
      chosenEvents = events;
      break;
    }
  }

  if (!chosenEvents){
    els.dateLabel.textContent = `No games found in next ${MAX_LOOKAHEAD_DAYS} days`;
    els.status.textContent = `No NBA games found in next ${MAX_LOOKAHEAD_DAYS} days.`;
    return;
  }

  const displayDate = chosenDate.toLocaleDateString();
  els.dateLabel.textContent = `Date: ${displayDate}`;

  const isToday = (new Date().toDateString() === chosenDate.toDateString());
  els.status.textContent = isToday
    ? `Found ${chosenEvents.length} game(s) today.`
    : `No games today — showing next game day (${displayDate}), ${chosenEvents.length} game(s).`;

  for (const g of chosenEvents){
    els.games.appendChild(gameCard(g));
  }
}

async function loadRoster(teamId, teamName, opponentTeamId = null, gameId = null){
  currentOpponentTeamId = opponentTeamId;
  currentGameId = gameId;

  openSide(true);
  els.sideTitle.textContent = `${teamName} — Roster`;
  els.sideMeta.textContent = "Loading roster…";
  clearRoster();

  try{
    const res = await fetch(`/api/nba/roster?teamId=${teamId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

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

/* ----------------- Last 5 games ----------------- */

function renderLast5(games){
  if (!els.last5) return;

  if (!Array.isArray(games) || games.length === 0){
    els.last5.innerHTML = `<div class="muted">No recent games found.</div>`;
    return;
  }

  els.last5.innerHTML = games.map(g => {
    const date = g.date ?? "—";
    const opp = g.opponent ?? "—";
    const result = g.result ?? "";
    const score = g.score ? ` (${escapeHtml(g.score)})` : "";

    const min = (g.min ?? "—");
    const pts = (g.pts ?? "—");
    const reb = (g.reb ?? "—");
    const ast = (g.ast ?? "—");

    return `
      <div class="last5-row">
        <div class="left">${escapeHtml(date)} vs ${escapeHtml(opp)} ${escapeHtml(result)}${score}</div>
        <div class="right">${min} MIN • ${pts} PTS • ${reb} REB • ${ast} AST</div>
      </div>
    `;
  }).join("");
}

async function loadLast5(athleteId){
  if (!els.last5) return;
  els.last5.innerHTML = `<div class="muted">Loading last 5 games…</div>`;

  try{
    const res = await fetch(`/api/nba/player_gamelog?athleteId=${athleteId}&limit=5`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderLast5(data.games || []);
  } catch (e){
    els.last5.innerHTML = `<div class="muted">Could not load last 5 games. (${escapeHtml(e.message)})</div>`;
  }
}

/* ----------------- Vs Opponent (This Season) ----------------- */

function renderVsOpp(games){
  if (!els.vsOpp) return;

  if (!Array.isArray(games) || games.length === 0){
    els.vsOpp.innerHTML = `<div class="muted">No games vs opponent this season.</div>`;
    return;
  }

  els.vsOpp.innerHTML = games.map(g => {
    const date = g.date ?? "—";
    const opp = g.opponent ?? "—";
    const result = g.result ?? "";
    const score = g.score ? ` (${escapeHtml(g.score)})` : "";

    const min = (g.min ?? "—");
    const pts = (g.pts ?? "—");
    const reb = (g.reb ?? "—");
    const ast = (g.ast ?? "—");

    return `
      <div class="last5-row">
        <div class="left">${escapeHtml(date)} vs ${escapeHtml(opp)} ${escapeHtml(result)}${score}</div>
        <div class="right">${min} MIN • ${pts} PTS • ${reb} REB • ${ast} AST</div>
      </div>
    `;
  }).join("");
}

async function loadVsOpponent(athleteId){
  if (!els.vsOpp) return;

  els.vsOpp.innerHTML = `<div class="muted">Loading vs opponent…</div>`;

  if (!currentOpponentTeamId){
    els.vsOpp.innerHTML = `<div class="muted">No opponent selected. Click a game team first.</div>`;
    return;
  }

  try{
    const url = `/api/nba/player_vs_opponent?athleteId=${athleteId}&opponentTeamId=${currentOpponentTeamId}&limit=10`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderVsOpp(data.games || []);
  } catch (e){
    els.vsOpp.innerHTML = `<div class="muted">Could not load vs opponent. (${escapeHtml(e.message)})</div>`;
  }
}

/* ----------------- Projection ----------------- */

async function loadProjection(athleteId){
  // keep existing quick UI resets
  if (els.pPts) els.pPts.textContent = "—";
  if (els.pReb) els.pReb.textContent = "—";
  if (els.pAst) els.pAst.textContent = "—";
  if (els.projNote) els.projNote.textContent = "Loading projection…";

  // clear diagnostics
  const setDiag = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  setDiag("diagMinutes", "—");
  setDiag("diagMinutesStability", "");
  setDiag("diagOppAdj", "—");
  setDiag("diagNSamples", "—");
  setDiag("distPts", "PTS: —");
  setDiag("distReb", "REB: —");
  setDiag("distAst", "AST: —");
  setDiag("fairLine", "Fair line: —");
  setDiag("altLines", "Alts: —");

  try{
    const res = await fetch(`/api/nba/player_projection?athleteId=${athleteId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const p = data.projection || {};
    const dist = data.distribution || {};
    const meta = data.meta || {};

    // Show median projection in modal stats
    if (els.pPts) els.pPts.textContent = (typeof p.pts === "number") ? p.pts.toFixed(1) : "—";
    if (els.pReb) els.pReb.textContent = (typeof p.reb === "number") ? p.reb.toFixed(1) : "—";
    if (els.pAst) els.pAst.textContent = (typeof p.ast === "number") ? p.ast.toFixed(1) : "—";

    // proj note -> minutes + confidence
    const mins = (typeof meta.estMinutes === "number") ? (meta.estMinutes.toFixed(1) + " min") : (meta.minutesMu ? `${meta.minutesMu} min` : "—");
    const conf = meta.confidence || "—";
    if (els.projNote) els.projNote.textContent = `Projection (est ${mins}) • confidence: ${conf}`;

    // diagnostics
    setDiag("diagMinutes", `${meta.minutesMu ?? "—"} ± ${meta.minutesSd ?? "—"}`);
    setDiag("diagMinutesStability", `(${meta.minutesStability ?? "—"})`);
    setDiag("diagOppAdj", (meta.oppAdj && meta.oppAdj.pts) ? `pts:${meta.oppAdj.pts}` : "—");
    setDiag("diagNSamples", meta.nSamples ? `${meta.nSamples} runs` : "—");

    // distribution text
    const showDist = (stat, elId) => {
      const d = dist[stat] || {};
      if (d && d.p10 != null){
        const txt = `${stat.toUpperCase()}: p10 ${d.p10} — p25 ${d.p25} — p50 ${d.p50} — p75 ${d.p75} — p90 ${d.p90} (mean ${d.mean})`;
        setDiag(elId, txt);
      } else {
        setDiag(elId, `${stat.toUpperCase()}: —`);
      }
    };
    showDist("pts", "distPts");
    showDist("reb", "distReb");
    showDist("ast", "distAst");

  } catch (e){
    if (els.projNote) els.projNote.textContent = `Could not load projection. (${e.message})`;
  }
}

/* ----------------- Manual line assess ----------------- */

async function assessManualLine(){
  if (!currentAthleteId) return;

  const stat = (els.manualStat?.value || "pts").toLowerCase();
  const lineRaw = els.manualLine?.value;
  const line = parseFloat(lineRaw);

  if (!Number.isFinite(line)){
    if (els.assessResult) els.assessResult.textContent = "Enter a valid numeric line (ex: 25.5).";
    return;
  }

  if (els.assessResult) els.assessResult.textContent = "Calculating…";

  try{
    const res = await fetch(`/api/nba/assess_line`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ athleteId: currentAthleteId, stat, line })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const prob = data.probOver ?? data.prob ?? data.probability ?? null;
    const mean = (data.projectionP50 != null) ? data.projectionP50 : (data.mean ?? null);
    const std = (data.band && data.band.mean) ? data.band.mean : null;

    const pct = (prob == null) ? "—" : `${Math.round(prob * 100)}%`;
    const meanTxt = (mean == null) ? "—" : mean.toFixed(1);

    if (els.assessResult){
      els.assessResult.innerHTML =
        `<b>${pct}</b> chance to go OVER ${line.toFixed(1)} ${stat.toUpperCase()}<br/>
         Model median=${meanTxt}${data.band ? `<br/>Band(p10-p90): ${data.band.p10} - ${data.band.p90}` : ""}`;
    }

    // show fair line + alt lines + diagnostics
    const setDiag = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    setDiag("fairLine", `Fair line: ${data.fairLine ?? "—"}`);
    if (data.altLines && data.altLines.length){
      const parts = data.altLines.slice(0,7).map(a => `${a.line}: ${Math.round(a.pOver*100)}%`);
      setDiag("altLines", `Alts: ${parts.join(" • ")}`);
    } else {
      setDiag("altLines", "Alts: —");
    }

    // minutes diag if present
    if (data.meta){
      setDiag("diagMinutes", `${data.meta.minutesMu ?? "—"} ± ${data.meta.minutesSd ?? "—"}`);
      setDiag("diagMinutesStability", `(${data.meta.minutesStability ?? "—"})`);
      setDiag("diagOppAdj", data.meta.oppAdj ? `pts:${data.meta.oppAdj.pts}` : "—");
      setDiag("diagNSamples", data.meta.nSamples ? `${data.meta.nSamples} runs` : "—");
    }

  } catch (e){
    if (els.assessResult) els.assessResult.textContent = `Could not assess line. (${e.message})`;
  }
}
/* ----------------- Tracking (PER PLAYER) ----------------- */

async function trackCurrent(){
  if (!lastAssessment){
    alert("Run Assess first, then press Track.");
    return;
  }

  const res = await fetch("/api/nba/track_add", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(lastAssessment)
  });

  if (!res.ok){
    alert("Could not save track row.");
    return;
  }

  await refreshTrackingHistory(currentAthleteId);
}

async function refreshTrackingHistory(athleteId){
  if (!athleteId) return;

  // Refresh actuals on server (fills completed games)
  await fetch("/api/nba/track_refresh", {
    method:"POST",
    headers: {"Content-Type":"application/json"},
    body:"{}"
  });

  // Pull list
  const res = await fetch("/api/nba/track_list");
  const data = await res.json();
  const rows = data.rows || [];

  // Filter to this player only
  const mine = rows.filter(r => String(r.athleteId) === String(athleteId));

  renderTrackTable(mine);
  renderTrackChart(mine);
}

function renderTrackTable(rows){
  if (!els.trackTable) return;

  if (!rows.length){
    els.trackTable.innerHTML = `<div class="muted">No tracked picks for this player yet. Run Assess then Track.</div>`;
    return;
  }

  const show = rows.slice(0, 15);
  els.trackTable.innerHTML = show.map(r => {
    const date = new Date((r.ts||0)*1000).toLocaleString();
    const actual = (r.actual == null) ? "—" : Number(r.actual).toFixed(1);
    return `<div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,.08)">
      <b>${escapeHtml((r.playerName || "").trim() || "Player")}</b> • <b>${r.stat.toUpperCase()}</b> line ${r.line}
      • P(Over) ${Math.round(r.prob*100)}%
      • μ ${Number(r.mean).toFixed(1)}
      • actual ${actual}
      <div class="muted small">${escapeHtml(date)} • gameId ${escapeHtml(r.gameId || "—")}</div>
    </div>`;
  }).join("");
}

function renderTrackChart(rows){
  const c = els.trackChart;
  if (!c) return;
  const ctx = c.getContext("2d");
  ctx.clearRect(0,0,c.width,c.height);

  if (!rows.length){
    ctx.fillStyle = "rgba(255,255,255,.75)";
    ctx.fillText("No tracked picks for this player yet.", 10, 30);
    return;
  }

  const completed = rows.filter(r => r.actual != null).slice(0, 20).reverse();
  if (!completed.length){
    ctx.fillStyle = "rgba(255,255,255,.75)";
    ctx.fillText("Tracked picks exist, but no completed games yet (actual fills after games end).", 10, 30);
    return;
  }

  const pad = 20;
  const W = c.width - pad*2;
  const H = c.height - pad*2;

  const ys = completed.flatMap(r => [Number(r.mean), Number(r.actual)]);
  const yMin = Math.min(...ys) - 2;
  const yMax = Math.max(...ys) + 2;

  function x(i){ return pad + (completed.length === 1 ? 0 : (i/(completed.length-1))*W); }
  function y(v){ return pad + (1 - (v - yMin)/(yMax - yMin))*H; }

  // axes
  ctx.strokeStyle = "rgba(255,255,255,.18)";
  ctx.beginPath();
  ctx.moveTo(pad, pad);
  ctx.lineTo(pad, pad+H);
  ctx.lineTo(pad+W, pad+H);
  ctx.stroke();

  // mean line (blue-ish)
  ctx.strokeStyle = "rgba(120,200,255,.75)";
  ctx.beginPath();
  completed.forEach((r,i)=>{
    const xx = x(i), yy = y(Number(r.mean));
    if (i===0) ctx.moveTo(xx,yy); else ctx.lineTo(xx,yy);
  });
  ctx.stroke();

  // actual line (orange-ish)
  ctx.strokeStyle = "rgba(255,180,120,.75)";
  ctx.beginPath();
  completed.forEach((r,i)=>{
    const xx = x(i), yy = y(Number(r.actual));
    if (i===0) ctx.moveTo(xx,yy); else ctx.lineTo(xx,yy);
  });
  ctx.stroke();

  ctx.fillStyle = "rgba(255,255,255,.75)";
  ctx.fillText("Blue = projection (μ), Orange = actual", 10, c.height - 8);
}

/* ----------------- Player modal ----------------- */

async function loadPlayer(athleteId, name){
  currentAthleteId = athleteId;

  openModal(true);
  els.playerName.textContent = name;
  els.playerTeam.textContent = "Loading…";

  els.pts.textContent = "—";
  els.reb.textContent = "—";
  els.ast.textContent = "—";
  els.playerNote.textContent = "";

  if (els.assessResult) els.assessResult.textContent = "Enter a line and press Assess.";
  lastAssessment = null;

  // Load player-specific tracking history right away
  refreshTrackingHistory(athleteId);

  // Load last 5 + projection + vs opponent in parallel
  loadLast5(athleteId);
  loadProjection(athleteId);
  loadVsOpponent(athleteId);

  try{
    const res = await fetch(`/api/nba/player?athleteId=${athleteId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    els.playerName.textContent = data.name || name;
    els.playerTeam.textContent = data.team || "—";

    const avg = data.seasonAverages || {};
    const pts = avg.pts, reb = avg.reb, ast = avg.ast;

    els.pts.textContent = (typeof pts === "number") ? pts.toFixed(1) : "—";
    els.reb.textContent = (typeof reb === "number") ? reb.toFixed(1) : "—";
    els.ast.textContent = (typeof ast === "number") ? ast.toFixed(1) : "—";

    if (pts == null || reb == null || ast == null){
      els.playerNote.textContent = "Couldn’t find PTS/REB/AST in ESPN’s stats response for this player.";
    } else {
      els.playerNote.textContent = "Season per-game averages.";
    }
  } catch (e){
    els.playerTeam.textContent = "—";
    els.playerNote.textContent = `Could not load player stats. (${e.message})`;
  }
}

/* ----------------- Wire UI ----------------- */

document.getElementById("trackBtn")?.addEventListener("click", async () => {
  if (!currentAthleteId) return;

  const stat = (els.manualStat?.value || "pts").toLowerCase();
  const line = parseFloat(els.manualLine?.value);

  if (!Number.isFinite(line)){
    alert("Enter a line first (ex: 25.5) then click Track.");
    return;
  }

  // Use the most recent assess output in the UI by calling assess_line again
  try{
    const res = await fetch(`/api/nba/assess_line`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ athleteId: currentAthleteId, stat, line })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const payload = {
      athleteId: currentAthleteId,
      stat,
      line,
      probOver: data.probOver,
      fairLine: data.fairLine,
      projectionP50: data.projectionP50,
      opponentTeamId: data.meta?.opponentTeamId ?? null,
      // optional: later we can pass gameId automatically by selecting the matchup
      gameId: null,
      gameDate: null,
      meta: {
        minutesMu: data.meta?.minutesMu,
        minutesSd: data.meta?.minutesSd,
        minutesStability: data.meta?.minutesStability,
        ptsEngine: data.meta?.ptsEngine,
      }
    };

    const saveRes = await fetch(`/api/nba/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!saveRes.ok) throw new Error(`HTTP ${saveRes.status}`);
    const saved = await saveRes.json();

    alert(`Tracked! Saved id=${saved.saved?.id}`);
  } catch (e){
    alert(`Track failed: ${e.message}`);
  }
});

els.refreshBtn.addEventListener("click", load);
els.refreshLabel.textContent = `${Math.round(REFRESH_MS/1000)}s`;

els.closeSideBtn.addEventListener("click", () => openSide(false));
els.closeModalBtn.addEventListener("click", () => openModal(false));
els.modal.addEventListener("click", (e) => { if (e.target === els.modal) openModal(false); });

if (els.assessBtn){
  els.assessBtn.addEventListener("click", assessManualLine);
}
if (els.manualLine){
  els.manualLine.addEventListener("keydown", (e) => {
    if (e.key === "Enter") assessManualLine();
  });
}

if (els.trackBtn){
  els.trackBtn.addEventListener("click", trackCurrent);
}

load();
setInterval(load, REFRESH_MS);