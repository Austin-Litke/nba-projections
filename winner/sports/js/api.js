const API_BASE = "https://nba-projections.onrender.com";

async function getJson(url) {
  const res = await fetch(`${API_BASE}${url}`, { cache: "no-store" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function postJson(url, payload) {
  const res = await fetch(`${API_BASE}${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

export const api = {
  scoreboard: (dateStr) => getJson(`/api/nba/scoreboard?date=${dateStr}`),
  roster: (teamId) => getJson(`/api/nba/roster?teamId=${teamId}`),
  player: (athleteId) => getJson(`/api/nba/player?athleteId=${athleteId}`),
  gamelog: (athleteId, limit = 5) =>
    getJson(`/api/nba/player_gamelog?athleteId=${athleteId}&limit=${limit}`),
  vsOpponent: (athleteId, oppId, limit = 25) =>
    getJson(`/api/nba/player_vs_opponent?athleteId=${athleteId}&opponentTeamId=${oppId}&limit=${limit}`),

  projection: (athleteId, oppId = null, gameId = null) => {
    const base = `/api/nba/player_projection?athleteId=${athleteId}`;
    const withOpp = oppId ? `${base}&opponentTeamId=${oppId}` : base;
    return getJson(gameId ? `${withOpp}&gameId=${gameId}` : withOpp);
  },

  assessLine: (payload) => postJson(`/api/nba/assess_line`, payload),
  tracked: (athleteId) => getJson(`/api/nba/tracked?athleteId=${athleteId}`),
  track: (payload) => postJson(`/api/nba/track`, payload),
  settle: (id) => postJson(`/api/nba/settle`, { id }),
};