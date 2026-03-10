import { els } from "./dom.js";
import { state } from "./state.js";
import { api } from "./api.js";
import { yyyymmddFromDate } from "./utils.js";
import { clearGames, gameCard, openModal, openSide } from "./render.js";
import {
  loadRoster,
  loadPlayer,
  assessManualLine,
  trackCurrent,
  loadTracking,
} from "./features.js";

export const REFRESH_MS = 15000;
export const MAX_LOOKAHEAD_DAYS = 14;

export async function loadGames(){
  const today = new Date();
  els.status.textContent = "Loading…";
  clearGames();

  let chosenDate = null;
  let chosenEvents = null;

  for (let offset = 0; offset <= MAX_LOOKAHEAD_DAYS; offset++){
    const d = new Date(today);
    d.setDate(today.getDate() + offset);
    const dateStr = yyyymmddFromDate(d);

    const data = await api.scoreboard(dateStr);
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
    els.games.appendChild(
      gameCard(g, async (teamId, teamName) => loadRoster(teamId, teamName, loadPlayer))
    );
  }
}

export function wireUi(){
  els.refreshBtn.addEventListener("click", loadGames);
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
    els.refreshTrackBtn.addEventListener("click", () => loadTracking());
  }

  // ✅ NEW: show team picks panel is present (debug)
  if (els.teamPicksStatus){
    els.teamPicksStatus.textContent = "Team Picks ready — click a team, then click Top 2.";
  }
}