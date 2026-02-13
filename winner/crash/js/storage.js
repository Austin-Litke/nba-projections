export const store = {
  saveNum(key, val) { localStorage.setItem(key, String(val)); },
  loadNum(key, fallback) {
    const v = Number(localStorage.getItem(key));
    return Number.isFinite(v) && v >= 0 ? v : fallback;
  }
};