export function escapeHtml(s){
  return String(s)
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

export function fmtLocalTime(iso){
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour:"numeric", minute:"2-digit" });
}

export function badgeFor(status){
  const s = (status || "").toLowerCase();
  if (s.includes("final")) return { text: "FINAL", cls: "final" };
  if (s.includes("in progress") || s.includes("halftime") || s.includes("end") || s.includes("q")) {
    return { text: "LIVE", cls: "live" };
  }
  return { text: "SCHEDULED", cls: "" };
}

export function yyyymmddFromDate(d){
  const y = d.getFullYear();
  const m = String(d.getMonth()+1).padStart(2,"0");
  const day = String(d.getDate()).padStart(2,"0");
  return `${y}${m}${day}`;
}

export function fmtDateShort(iso){
  try{
    const d = new Date(iso);
    return d.toLocaleDateString();
  } catch {
    return "—";
  }
}
export function parseAmericanOdds(raw){
  if (raw == null) return null;
  const s = String(raw).trim().replace(/\s+/g,"");
  if (!s) return null;

  if (!(s.startsWith("+") || s.startsWith("-"))) return null;

  const n = parseInt(s, 10);
  if (!Number.isFinite(n) || n === 0) return null;
  if (Math.abs(n) < 100) return null;
  return n;
}

export function impliedProbFromAmerican(odds){
  if (!Number.isFinite(odds) || odds === 0) return null;
  if (odds < 0){
    const a = Math.abs(odds);
    return a / (a + 100);
  } else {
    return 100 / (odds + 100);
  }
}

export function netPayoutPerDollar(odds){
  if (!Number.isFinite(odds) || odds === 0) return null;
  if (odds < 0){
    return 100 / Math.abs(odds);
  } else {
    return odds / 100;
  }
}

export function kellyFraction(pWin, odds){
  const b = netPayoutPerDollar(odds);
  if (b == null) return null;

  const p = Number(pWin);
  if (!Number.isFinite(p) || p <= 0 || p >= 1) return null;

  const q = 1 - p;
  const f = (p*b - q) / b;

  return Math.max(0, Math.min(f, 1));
}