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

  // vs opp
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

  // tracking ui
  trackGameId: document.getElementById("trackGameId"),
  trackBtn: document.getElementById("trackBtn"),
  refreshTrackBtn: document.getElementById("refreshTrackBtn"),
  trackRows: document.getElementById("trackRows"),
  trackMeta: document.getElementById("trackMeta"),
  trackChart: document.getElementById("trackChart"),
};

const REFRESH_MS = 15000;
const MAX_LOOKAHEAD_DAYS = 14;

let currentAthleteId = null;
let currentOpponentTeamId = null; // we can set this when you add opponent selection later

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
      await loadRoster(teamId, teamName);
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

async function loadRoster(teamId, teamName){
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

function renderGameList(targetEl, games){
  if (!targetEl) return;

  if (!Array.isArray(games) || games.length === 0){
    targetEl.innerHTML = `<div class="muted">No games found.</div>`;
    return;
  }

  targetEl.innerHTML = games.map(g => {
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
    renderGameList(els.last5, data.games || []);
  } catch (e){
    els.last5.innerHTML = `<div class="muted">Could not load last 5 games. (${escapeHtml(e.message)})</div>`;
  }
}

/* ----------------- Vs Opponent (This Season) ----------------- */

async function loadVsOpponent(athleteId, opponentTeamId){
  if (!els.vsOpp) return;
  if (!opponentTeamId){
    els.vsOpp.innerHTML = `<div class="muted">Pick an opponent to show this.</div>`;
    return;
  }

  els.vsOpp.innerHTML = `<div class="muted">Loading vs opponent…</div>`;
  try{
    const res = await fetch(`/api/nba/player_vs_opponent?athleteId=${athleteId}&opponentTeamId=${opponentTeamId}&limit=25`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderGameList(els.vsOpp, data.games || []);
  } catch (e){
    els.vsOpp.innerHTML = `<div class="muted">Could not load vs opponent. (${escapeHtml(e.message)})</div>`;
  }
}

/* ----------------- Projection ----------------- */

async function loadProjection(athleteId){
  if (els.pPts) els.pPts.textContent = "—";
  if (els.pReb) els.pReb.textContent = "—";
  if (els.pAst) els.pAst.textContent = "—";
  if (els.projNote) els.projNote.textContent = "Loading projection…";

  try{
    // if you later set currentOpponentTeamId, you can append it here
    const url = currentOpponentTeamId
      ? `/api/nba/player_projection?athleteId=${athleteId}&opponentTeamId=${currentOpponentTeamId}`
      : `/api/nba/player_projection?athleteId=${athleteId}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
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
    const payload = { athleteId: currentAthleteId, stat, line };
    if (currentOpponentTeamId) payload.opponentTeamId = currentOpponentTeamId;

    const res = await fetch(`/api/nba/assess_line`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const prob = (typeof data.probOver === "number") ? data.probOver : null;
    const pct = (prob == null) ? "—" : `${Math.round(prob * 100)}%`;

    const p50 = (typeof data.projectionP50 === "number") ? data.projectionP50.toFixed(1) : "—";
    const band = data.band ? `p10 ${data.band.p10} • p50 ${data.band.p50} • p90 ${data.band.p90}` : "";

    if (els.assessResult){
      els.assessResult.innerHTML =
        `<b>${pct}</b> chance to go OVER ${line.toFixed(1)} ${stat.toUpperCase()}<br/>
         median=${p50}${band ? `<br/>${escapeHtml(band)}` : ""}<br/>
         fair line=${data.fairLine ?? "—"} • samples=${data.meta?.nSamples ?? "—"}`;
    }
  } catch (e){
    if (els.assessResult) els.assessResult.textContent = `Could not assess line. (${e.message})`;
  }
}

/* ----------------- Tracking ----------------- */

function _fmtDateShort(iso){
  try{
    const d = new Date(iso);
    return d.toLocaleDateString();
  } catch {
    return "—";
  }
}

function drawTrackingChart(rows){
  const c = els.trackChart;
  if (!c) return;
  const ctx = c.getContext("2d");
  if (!ctx) return;

  // clear
  ctx.clearRect(0, 0, c.width, c.height);

  const data = rows
    .filter(r => typeof r.projectionP50 === "number")
    .slice(-10); // last 10

  if (!data.length){
    ctx.fillText("No tracked data yet.", 10, 20);
    return;
  }

  const pad = 18;
  const W = c.width, H = c.height;
  const chartW = W - pad * 2;
  const chartH = H - pad * 2;

  // range based on proj & actual if exists
  let maxV = 0;
  for (const r of data){
    maxV = Math.max(maxV, r.projectionP50 || 0, (r.actual ?? 0));
  }
  maxV = Math.max(5, maxV);

  // axes
  ctx.globalAlpha = 0.9;
  ctx.beginPath();
  ctx.moveTo(pad, pad);
  ctx.lineTo(pad, H - pad);
  ctx.lineTo(W - pad, H - pad);
  ctx.stroke();

  // plot points
  const step = chartW / Math.max(1, data.length - 1);

  // projection line
  ctx.beginPath();
  data.forEach((r, i) => {
    const x = pad + i * step;
    const y = (H - pad) - (chartH * (r.projectionP50 / maxV));
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // actual dots (if settled)
  data.forEach((r, i) => {
    if (r.actual == null) return;
    const x = pad + i * step;
    const y = (H - pad) - (chartH * (r.actual / maxV));
    ctx.beginPath();
    ctx.arc(x, y, 3.5, 0, Math.PI * 2);
    ctx.fill();
  });

  ctx.globalAlpha = 1.0;
  ctx.fillText("Line: projection (line) • actual (dots)", pad, 14);
}

function renderTrackingTable(preds){
  if (!els.trackRows) return;

  if (!Array.isArray(preds) || preds.length === 0){
    els.trackRows.innerHTML = `<tr><td colspan="8" class="muted">No tracked rows yet.</td></tr>`;
    drawTrackingChart([]);
    return;
  }

  // newest first
  const rows = [...preds].sort((a,b) => String(b.createdAt).localeCompare(String(a.createdAt)));

  els.trackRows.innerHTML = rows.map(r => {
    const date = _fmtDateShort(r.createdAt);
    const stat = (r.stat || "").toUpperCase();
    const line = (typeof r.line === "number") ? r.line.toFixed(1) : "—";
    const p = (typeof r.probOver === "number") ? `${Math.round(r.probOver * 100)}%` : "—";
    const proj = (typeof r.projectionP50 === "number") ? r.projectionP50.toFixed(1) : "—";
    const actual = (r.actual == null) ? "—" : Number(r.actual).toFixed(0);

    let res = "—";
    let pillCls = "";
    if (r.result === "over"){ res = "OVER"; pillCls = "over"; }
    if (r.result === "under"){ res = "UNDER"; pillCls = "under"; }

    const canSettle = !r.settledAt && r.gameId;

    return `
      <tr>
        <td>${escapeHtml(date)}</td>
        <td>${escapeHtml(stat)}</td>
        <td>${escapeHtml(line)}</td>
        <td>${escapeHtml(p)}</td>
        <td>${escapeHtml(proj)}</td>
        <td>${escapeHtml(actual)}</td>
        <td>${res === "—" ? "—" : `<span class="trackPill ${pillCls}">${res}</span>`}</td>
        <td>
          ${canSettle
            ? `<button class="trackBtnSmall" data-settle="${r.id}">Settle</button>`
            : (r.gameId ? `<span class="muted small">done</span>` : `<span class="muted small">needs gameId</span>`)
          }
        </td>
      </tr>
    `;
  }).join("");

  // wire settle buttons
  els.trackRows.querySelectorAll("[data-settle]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = parseInt(btn.getAttribute("data-settle"), 10);
      if (!Number.isFinite(id)) return;

      btn.textContent = "…";
      try{
        const res = await fetch(`/api/nba/settle`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({ id })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        await loadTracking(currentAthleteId);
      } catch (e){
        alert(`Settle failed: ${e.message}`);
      } finally {
        btn.textContent = "Settle";
      }
    });
  });

  drawTrackingChart(rows);
}

async function loadTracking(athleteId){
  if (!athleteId) return;
  if (els.trackMeta) els.trackMeta.textContent = "Loading tracked predictions…";

  try{
    const res = await fetch(`/api/nba/tracked?athleteId=${athleteId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const preds = data.predictions || [];
    renderTrackingTable(preds);

    // simple summary in meta
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

async function trackCurrent(){
  if (!currentAthleteId) return;

  const stat = (els.manualStat?.value || "pts").toLowerCase();
  const line = parseFloat(els.manualLine?.value);

  if (!Number.isFinite(line)){
    alert("Enter a line first (ex: 25.5), then Track.");
    return;
  }

  // optional gameId helps settling
  const gameId = (els.trackGameId?.value || "").trim() || null;

  try{
    // get latest assess results (prob, fair line, p50)
    const assessRes = await fetch(`/api/nba/assess_line`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ athleteId: currentAthleteId, stat, line, opponentTeamId: currentOpponentTeamId ?? undefined })
    });
    const assess = await assessRes.json();
    if (!assessRes.ok) throw new Error(assess.error || `HTTP ${assessRes.status}`);

    const payload = {
      athleteId: currentAthleteId,
      stat,
      line,
      probOver: assess.probOver,
      fairLine: assess.fairLine,
      projectionP50: assess.projectionP50,
      opponentTeamId: assess.meta?.opponentTeamId ?? null,
      gameId,
      gameDate: null,
      meta: {
        minutesMu: assess.meta?.minutesMu,
        minutesSd: assess.meta?.minutesSd,
        minutesStability: assess.meta?.minutesStability,
        ptsEngine: assess.meta?.ptsEngine,
        nSamples: assess.meta?.nSamples,
      }
    };

    const saveRes = await fetch(`/api/nba/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const saved = await saveRes.json();
    if (!saveRes.ok) throw new Error(saved.error || `HTTP ${saveRes.status}`);

    await loadTracking(currentAthleteId);
  } catch (e){
    alert(`Track failed: ${e.message}`);
  }
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

  // reset gameId input
  if (els.trackGameId) els.trackGameId.value = "";

  // Load last 5 + projection + tracking
  loadLast5(athleteId);
  loadProjection(athleteId);
  loadTracking(athleteId);

  // opponent list: still manual for now
  loadVsOpponent(athleteId, currentOpponentTeamId);

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
if (els.refreshTrackBtn){
  els.refreshTrackBtn.addEventListener("click", () => loadTracking(currentAthleteId));
}

load();
setInterval(load, REFRESH_MS);