import { store } from "./storage.js";

const BANKROLL_KEY = "winner_bankroll";
const DEFAULT_BANKROLL = 1000;

const $ = (id) => document.getElementById(id);

const els = {
  bankroll: $("bankroll"),
  resetBtn: $("resetBtn"),
  status: $("status"),
  cv: $("cv"),
  betInput: $("betInput"),
  maxBtn: $("maxBtn"),
  dropBtn: $("dropBtn"),
  history: $("history"),
  chips: Array.from(document.querySelectorAll(".chip")),
  riskBtns: Array.from(document.querySelectorAll(".riskBtn")),
};

const ctx = els.cv.getContext("2d");

// ---------- money helpers ----------
function getBankroll(){ return store.loadNum(BANKROLL_KEY, DEFAULT_BANKROLL); }
function setBankroll(v){ store.saveNum(BANKROLL_KEY, Math.max(0, Math.floor(v))); }
function fmtMoney(v){ return `$${Math.floor(Number(v)||0).toLocaleString()}`; }
function refreshBankroll(){ els.bankroll.textContent = fmtMoney(getBankroll()); }

function clamp(n,a,b){ return Math.max(a, Math.min(b,n)); }
function rand(a,b){ return a + Math.random()*(b-a); }

// ---------- board config ----------
const W = els.cv.width;
const H = els.cv.height;

const board = {
  pegR: 6,
  ballR: 8,
  gravity: 900,      // px/s^2
  bounce: 0.55,      // energy retention
  friction: 0.995,   // per tick
  rows: 12,
  topY: 90,
  rowGap: 40,
  colGap: 42,
  leftPad: 44,
  rightPad: 44,
  floorY: H - 88,
};

let risk = "mid";

// bins count = rows + 1 (classic plinko)
function multipliersForRisk(r){
  // 13 bins (rows=12 => bins=13)
  // Tuned to be harder to profit:
  // - Low: small edge, still “friendly”
  // - Mid: noticeably harder
  // - High: mostly losing unless you hit edges

  if (r === "low")  return [3.0, 1.8, 1.3, 1.1, 0.9, 0.7, 0.5, 0.7, 0.9, 1.1, 1.3, 1.8, 3.0];
  if (r === "mid")  return [6.0, 3.0, 1.6, 1.2, 0.7, 0.4, 0.2, 0.4, 0.7, 1.2, 1.6, 3.0, 6.0];
  // high
  return            [18.0, 7.0, 3.0, 1.2, 0.5, 0.2, 0.05, 0.2, 0.5, 1.2, 3.0, 7.0, 18.0];
}

let multipliers = multipliersForRisk(risk);

// peg positions
let pegs = [];
function buildPegs(){
  pegs = [];
  for (let row=0; row<board.rows; row++){
    const y = board.topY + row * board.rowGap;
    const cols = row + 1;
    const rowWidth = (cols-1) * board.colGap;
    const startX = (W - rowWidth)/2;
    for (let c=0; c<cols; c++){
      pegs.push({ x: startX + c*board.colGap, y });
    }
  }
}
buildPegs();

// bins
function binCount(){ return board.rows + 1; }
function binWidth(){ return (W - board.leftPad - board.rightPad) / binCount(); }
function binIndexForX(x){
  const bw = binWidth();
  const i = Math.floor((x - board.leftPad) / bw);
  return clamp(i, 0, binCount()-1);
}

// ---------- ball sim ----------
let ball = null; // {x,y,vx,vy,bet,alive}
let lastT = performance.now();
let running = true;

function readBet(){
  const v = Number(els.betInput.value);
  if (!Number.isFinite(v)) return 1;
  return Math.floor(clamp(v, 1, 1_000_000));
}

function dropBall(){
  if (ball) return; // one at a time for now

  const bet = readBet();
  const bank = getBankroll();
  if (bet > bank){
    els.status.textContent = "Not enough bankroll for that bet.";
    return;
  }

  setBankroll(bank - bet);
  refreshBankroll();

  // small random start so it feels different
  const startX = W/2 + rand(-20, 20);
  ball = {
    x: startX,
    y: 40,
    vx: rand(-30, 30),
    vy: 0,
    bet,
    alive: true
  };

  els.status.textContent = "Ball dropped…";
}

function settleBall(){
  if (!ball) return;

  const i = binIndexForX(ball.x);
  const m = multipliers[i] ?? 0;
  const payout = Math.floor(ball.bet * m);

  setBankroll(getBankroll() + payout);
  refreshBankroll();

  const good = payout >= ball.bet;
  const label = `${m.toFixed(2)}×`;

  addHistory({
    mult: m,
    payout,
    bet: ball.bet,
    bin: i,
    label,
    good
  });

  els.status.textContent = good
    ? `Hit ${label}! You won ${fmtMoney(payout)}.`
    : `Hit ${label}. You got ${fmtMoney(payout)}.`;

  ball = null;
}

const history = [];
function addHistory(h){
  history.unshift(h);
  while(history.length > 12) history.pop();
  renderHistory();
}

function renderHistory(){
  els.history.innerHTML = "";
  for (const h of history){
    const div = document.createElement("div");
    div.className = `hItem ${h.good ? "hGood" : "hBad"}`;
    div.innerHTML = `
      <div><b>${h.label}</b> bin</div>
      <div class="muted small">Bet ${fmtMoney(h.bet)} → ${fmtMoney(h.payout)}</div>
    `;
    els.history.appendChild(div);
  }
}

// ---------- physics step ----------
function step(dt){
  if (!ball) return;

  // integrate
  ball.vy += board.gravity * dt;
  ball.x += ball.vx * dt;
  ball.y += ball.vy * dt;

  // walls
  const left = board.leftPad + board.ballR;
  const right = W - board.rightPad - board.ballR;

  if (ball.x < left){
    ball.x = left;
    ball.vx = Math.abs(ball.vx) * board.bounce * 2;
  } else if (ball.x > right){
    ball.x = right;
    ball.vx = -Math.abs(ball.vx) * board.bounce * 2;
  }

  // peg collisions
  for (const p of pegs){
    const dx = ball.x - p.x;
    const dy = ball.y - p.y;
    const dist = Math.hypot(dx, dy);
    const minDist = board.ballR + board.pegR;

    if (dist < minDist){
      // push ball out
      const nx = dx / (dist || 1);
      const ny = dy / (dist || 1);
      const overlap = (minDist - dist);
      ball.x += nx * overlap;
      ball.y += ny * overlap;

      // reflect velocity on normal
      const vn = ball.vx * nx + ball.vy * ny;
      if (vn < 0){
        ball.vx -= (1 + board.bounce) * vn * nx;
        ball.vy -= (1 + board.bounce) * vn * ny;

        // tiny random to prevent same path
        ball.vx += rand(-10, 10);

      }
    }
  }

  // friction
  ball.vx *= Math.pow(board.friction, dt*60);

  // floor / settle zone
  if (ball.y >= board.floorY){
    ball.y = board.floorY;
    // if it's basically stopped, settle into a bin
    if (Math.abs(ball.vy) < 80){
      settleBall();
    } else {
      ball.vy = -Math.abs(ball.vy) * 0.25;
      ball.vx *= 0.85;
    }
  }
}

// ---------- drawing ----------
function draw(){
  ctx.clearRect(0,0,W,H);

  // background
  ctx.fillStyle = "rgba(0,0,0,0.10)";
  ctx.fillRect(0,0,W,H);

  // pegs
  for (const p of pegs){
    ctx.beginPath();
    ctx.arc(p.x, p.y, board.pegR, 0, Math.PI*2);
    ctx.fillStyle = "rgba(233,238,252,0.80)";
    ctx.fill();
  }

  // bins + multipliers
  const bw = binWidth();
  const by = board.floorY + 24;
  for (let i=0; i<binCount(); i++){
    const x0 = board.leftPad + i*bw;
    const x1 = x0 + bw;

    // bin divider line
    ctx.strokeStyle = "rgba(255,255,255,0.14)";
    ctx.beginPath();
    ctx.moveTo(x0, board.floorY);
    ctx.lineTo(x0, H-24);
    ctx.stroke();

    // multiplier label
    const m = multipliers[i];
    ctx.fillStyle = "rgba(233,238,252,0.85)";
    ctx.font = "bold 14px system-ui";
    ctx.textAlign = "center";
    ctx.fillText(`${m.toFixed(2)}×`, (x0+x1)/2, by);
  }
  // last divider
  ctx.strokeStyle = "rgba(255,255,255,0.14)";
  ctx.beginPath();
  ctx.moveTo(board.leftPad + binCount()*bw, board.floorY);
  ctx.lineTo(board.leftPad + binCount()*bw, H-24);
  ctx.stroke();

  // floor line
  ctx.strokeStyle = "rgba(255,255,255,0.18)";
  ctx.beginPath();
  ctx.moveTo(board.leftPad, board.floorY);
  ctx.lineTo(W-board.rightPad, board.floorY);
  ctx.stroke();

  // ball
  if (ball){
    ctx.beginPath();
    ctx.arc(ball.x, ball.y, board.ballR, 0, Math.PI*2);
    ctx.fillStyle = "rgba(122,162,255,0.95)";
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.35)";
    ctx.stroke();
  }
}

// ---------- loop ----------
function loop(now){
  const dt = clamp((now - lastT) / 1000, 0, 0.033);
  lastT = now;

  step(dt);
  draw();

  if (running) requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

// ---------- UI wiring ----------
function setRisk(r){
  risk = r;
  multipliers = multipliersForRisk(r);

  els.riskBtns.forEach(b => b.classList.toggle("on", b.dataset.risk === r));
  els.status.textContent = `Risk set to ${r.toUpperCase()}.`;
}

els.riskBtns.forEach(btn => {
  btn.addEventListener("click", () => setRisk(btn.dataset.risk));
});

els.chips.forEach(btn => {
  btn.addEventListener("click", () => {
    const chip = Number(btn.dataset.chip);
    els.betInput.value = String(readBet() + chip);
  });
});

els.maxBtn.addEventListener("click", () => {
  els.betInput.value = String(getBankroll());
});

els.dropBtn.addEventListener("click", dropBall);

els.resetBtn.addEventListener("click", () => {
  setBankroll(DEFAULT_BANKROLL);
  refreshBankroll();
  els.status.textContent = "Bankroll reset to $1000.";
});

// init bankroll
if (!Number.isFinite(Number(localStorage.getItem(BANKROLL_KEY)))){
  setBankroll(getBankroll());
}
refreshBankroll();
