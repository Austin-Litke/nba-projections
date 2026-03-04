import { els } from "./dom.js";
import { state } from "./state.js";
import { escapeHtml, fmtLocalTime, badgeFor, fmtDateShort } from "./utils.js";

export function clearGames(){ els.games.innerHTML = ""; }
export function clearRoster(){ els.roster.innerHTML = ""; els.sideMeta.textContent = "—"; }

export function openModal(on){ els.modal.classList.toggle("on", !!on); }
export function openSide(on){ els.side.style.display = on ? "" : "none"; }

export function gameCard(g, onTeamClick){
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
        <button class="teamBtn"
          data-teamid="${awayId || ""}"
          data-teamname="${escapeHtml(awayName)}"
          data-opponentid="${homeId || ""}"
        >${escapeHtml(awayName)}</button>
        <div class="score">${awayScore}</div>
      </div>
      <div class="team">
        <button class="teamBtn"
          data-teamid="${homeId || ""}"
          data-teamname="${escapeHtml(homeName)}"
          data-opponentid="${awayId || ""}"
        >${escapeHtml(homeName)}</button>
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

      state.currentOpponentTeamId =
        (btn.dataset.opponentid && String(btn.dataset.opponentid).trim())
          ? String(btn.dataset.opponentid).trim()
          : null;

      await onTeamClick(teamId, teamName);
    });
  });

  return div;
}

export function renderGameList(targetEl, games){
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

export function renderExplanationFromAssess(stat, assess){
  if (!els.explainBody) return;

  const line = (typeof assess.line === "number") ? assess.line : null;
  const pOver = (typeof assess.probOver === "number") ? assess.probOver : null;
  const fair = (typeof assess.fairLine === "number") ? assess.fairLine : null;
  const p50 = (typeof assess.projectionP50 === "number") ? assess.projectionP50 : null;

  const meta = assess.meta || {};
  const minsMu = (typeof meta.minutesMu === "number") ? meta.minutesMu : null;
  const minsSd = (typeof meta.minutesSd === "number") ? meta.minutesSd : null;
  const minsStab = meta.minutesStability || null;
  const oppAdj = meta.oppAdj || null;
  const ptsEngine = meta.ptsEngine || null;
  const n = meta.nSamples ?? null;

  let edgeOver = null;
  if (pOver != null) edgeOver = pOver - 0.5;

  const statUp = String(stat || "").toUpperCase();
  const parts = [];
  parts.push(`<b>${statUp}</b> model details:`);

  if (line != null && pOver != null){
    const pct = Math.round(pOver * 100);
    parts.push(`• P(Over ${line.toFixed(1)}) = <b>${pct}%</b>`);
  }
  if (fair != null) parts.push(`• Fair line (median) ≈ <b>${Number(fair).toFixed(1)}</b>`);
  if (edgeOver != null){
    const e = Math.round(edgeOver * 100);
    const tag = e >= 0 ? `Over edge +${e}% vs 50/50` : `Under edge ${e}% vs 50/50`;
    parts.push(`• Edge indicator: <b>${escapeHtml(tag)}</b>`);
  }
  if (p50 != null) parts.push(`• Projection (P50) = <b>${p50.toFixed(1)}</b>`);

  if (minsMu != null && minsSd != null){
    parts.push(`• Minutes ~ N(${minsMu.toFixed(1)}, ${minsSd.toFixed(1)}) • stability: ${escapeHtml(minsStab || "—")}`);
  }
  if (oppAdj && typeof oppAdj === "object"){
    const pts = (typeof oppAdj.pts === "number") ? oppAdj.pts.toFixed(3) : "—";
    const reb = (typeof oppAdj.reb === "number") ? oppAdj.reb.toFixed(3) : "—";
    const ast = (typeof oppAdj.ast === "number") ? oppAdj.ast.toFixed(3) : "—";
    parts.push(`• Opponent adj (pts/reb/ast): ${pts} / ${reb} / ${ast}`);
  }
  if (ptsEngine) parts.push(`• PTS engine: ${escapeHtml(String(ptsEngine))}`);
  if (n != null) parts.push(`• Monte Carlo samples: ${escapeHtml(String(n))}`);

  els.explainBody.innerHTML = parts.join("<br/>");
}

export function drawTrackingChart(rows){
  const c = els.trackChart;
  if (!c) return;
  const ctx = c.getContext("2d");
  if (!ctx) return;

  ctx.clearRect(0, 0, c.width, c.height);

  const data = rows
    .filter(r => typeof r.projectionP50 === "number")
    .slice(-10);

  if (!data.length){
    ctx.fillText("No tracked data yet.", 10, 20);
    return;
  }

  const pad = 18;
  const W = c.width, H = c.height;
  const chartW = W - pad * 2;
  const chartH = H - pad * 2;

  let maxV = 0;
  for (const r of data){
    maxV = Math.max(maxV, r.projectionP50 || 0, (r.actual ?? 0));
  }
  maxV = Math.max(5, maxV);

  ctx.globalAlpha = 0.9;
  ctx.beginPath();
  ctx.moveTo(pad, pad);
  ctx.lineTo(pad, H - pad);
  ctx.lineTo(W - pad, H - pad);
  ctx.stroke();

  const step = chartW / Math.max(1, data.length - 1);

  ctx.beginPath();
  data.forEach((r, i) => {
    const x = pad + i * step;
    const y = (H - pad) - (chartH * (r.projectionP50 / maxV));
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

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

export function renderTrackingTable(preds, onSettleClick){
  if (!els.trackRows) return;

  if (!Array.isArray(preds) || preds.length === 0){
    els.trackRows.innerHTML = `<tr><td colspan="8" class="muted">No tracked rows yet.</td></tr>`;
    drawTrackingChart([]);
    return;
  }

  const rows = [...preds].sort((a,b) => String(b.createdAt).localeCompare(String(a.createdAt)));

  els.trackRows.innerHTML = rows.map(r => {
    const date = fmtDateShort(r.createdAt);
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

  els.trackRows.querySelectorAll("[data-settle]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = parseInt(btn.getAttribute("data-settle"), 10);
      if (!Number.isFinite(id)) return;
      await onSettleClick(id, btn);
    });
  });

  drawTrackingChart(rows);
}