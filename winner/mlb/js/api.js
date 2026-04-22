async function getJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(data.error || `Request failed: ${res.status}`);
  }

  return data;
}
export const api = {
  health() {
    return getJson("/api/mlb/health");
  },

  scoreboard(date = "") {
    const qs = date ? `?date=${encodeURIComponent(date)}` : "";
    return getJson(`/api/mlb/scoreboard${qs}`);
  },

  pitcher(pitcherId) {
    return getJson(`/api/mlb/pitcher?pitcherId=${encodeURIComponent(pitcherId)}`);
  },

  pitcherGameLog(pitcherId, limit = 5) {
    return getJson(
      `/api/mlb/pitcher_gamelog?pitcherId=${encodeURIComponent(pitcherId)}&limit=${encodeURIComponent(limit)}`
    );
  },

  pitcherProjection(pitcherId, limit = 5) {
    return getJson(
      `/api/mlb/pitcher_projection?pitcherId=${encodeURIComponent(pitcherId)}&limit=${encodeURIComponent(limit)}`
    );
  },

  pitcherLines(pitcherId) {
    return getJson(`/api/mlb/underdog_lines?pitcherId=${encodeURIComponent(pitcherId)}`);
  },
};