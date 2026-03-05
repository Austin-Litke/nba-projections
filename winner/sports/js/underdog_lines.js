// winner/sports/js/underdog_lines.js

import { els } from "./dom.js";

function escapeHtml(s){
  return String(s)
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

function renderMuted(msg){
  if (!els.udBasicLines) return;
  els.udBasicLines.innerHTML = `<div class="muted">${escapeHtml(msg)}</div>`;
}

function renderLines(lines){
  if (!els.udBasicLines) return;

  if (!Array.isArray(lines) || lines.length === 0){
    els.udBasicLines.innerHTML = `<div class="muted">No active Points / Rebounds / Assists lines found.</div>`;
    return;
  }

  // Keep order PTS, REB, AST
  const order = { pts: 1, reb: 2, ast: 3 };
  const sorted = [...lines].sort((a,b) => (order[a.statKey]||99) - (order[b.statKey]||99));

  els.udBasicLines.innerHTML = sorted.map(l => {
    const stat = l.displayStat || (l.statKey || "").toUpperCase();
    const line = (typeof l.line === "number") ? l.line.toFixed(1) : "—";
    const over = (l.overOdds != null) ? String(l.overOdds) : "—";
    const under = (l.underOdds != null) ? String(l.underOdds) : "—";

    return `
      <div class="last5-row">
        <div class="left"><b>${escapeHtml(stat)}</b> • ${escapeHtml(line)}</div>
        <div class="right">O: ${escapeHtml(over)} / U: ${escapeHtml(under)}</div>
      </div>
    `;
  }).join("");
}

export async function loadUnderdogLinesForAthlete(athleteId){
  if (!els.udBasicLines) return;

  if (!athleteId){
    renderMuted("Click a player to load lines.");
    return;
  }

  renderMuted("Loading lines…");

  try{
    const res = await fetch(`/api/nba/underdog_lines?athleteId=${athleteId}`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok){
      renderMuted(`Could not load lines. (${data.error || ("HTTP " + res.status)})`);
      return;
    }

    renderLines(data.lines || []);
  } catch (e){
    renderMuted(`Could not load lines. (${e.message || e})`);
  }
}