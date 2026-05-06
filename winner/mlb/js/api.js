async function getJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(data.error || `Request failed: ${res.status}`);
  }

  return data;
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body || {}),
  });

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

  settle(payload) {
    return postJson("/api/mlb/settle", payload);
  },
  
  tracked() {
    return getJson("/api/mlb/tracked");
  },

  track(payload) {
    return postJson("/api/mlb/track", payload);
  },

  pitcher(pitcherId) {
    return getJson(`/api/mlb/pitcher?pitcherId=${encodeURIComponent(pitcherId)}`);
  },

  pitcherGameLog(pitcherId, limit = 5) {
    return getJson(
      `/api/mlb/pitcher_gamelog?pitcherId=${encodeURIComponent(pitcherId)}&limit=${encodeURIComponent(limit)}`
    );
  },

  settleAll() {
  return postJson("/api/mlb/settle_all", {});
  },

  pitcherProjection(pitcherId, limit = 5) {
    return getJson(
      `/api/mlb/pitcher_projection?pitcherId=${encodeURIComponent(pitcherId)}&limit=${encodeURIComponent(limit)}`
    );
  },

  pitcherLines(pitcherId) {
    return getJson(`/api/mlb/underdog_lines?pitcherId=${encodeURIComponent(pitcherId)}`);
  },

  lineup(gameId) {
    return getJson(`/api/mlb/lineup?gameId=${encodeURIComponent(gameId)}`);
  },
};




