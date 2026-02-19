export function weightedPick(weightsMap) {
  let total = 0;
  for (const w of Object.values(weightsMap)) total += w;
  let r = Math.random() * total;
  for (const [k, w] of Object.entries(weightsMap)) {
    r -= w;
    if (r <= 0) return k;
  }
  return Object.keys(weightsMap)[0];
}
