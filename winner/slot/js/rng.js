export function sleep(ms){ return new Promise(r => setTimeout(r, ms)); }

export function clampInt(n, min, max){
  n = Math.floor(Number(n));
  if (!Number.isFinite(n)) return min;
  return Math.max(min, Math.min(max, n));
}
