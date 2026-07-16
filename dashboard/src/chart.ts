import type { ChartData, ChartInstance, ChartMetric } from './types.js';

let instance: ChartInstance | null = null;
let currentMetric: ChartMetric = 'pkts';

export function initChart(canvas: HTMLCanvasElement): void {
  const parent = canvas.parentElement!;
  const w = parent.clientWidth;
  const h = parent.clientHeight;
  const dpr = window.devicePixelRatio;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';

  const ctx = canvas.getContext('2d')!;
  ctx.scale(dpr, dpr);

  instance = { ctx, w, h };
}

export function resizeChart(canvas: HTMLCanvasElement): void {
  if (!instance) return;
  const parent = canvas.parentElement!;
  const w = parent.clientWidth;
  const h = parent.clientHeight;
  const dpr = window.devicePixelRatio;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';

  instance.ctx = canvas.getContext('2d')!;
  instance.w = w;
  instance.h = h;
  instance.ctx.scale(dpr, dpr);
}

export function setChartMetric(metric: ChartMetric): void {
  currentMetric = metric;
}

export function getChartMetric(): ChartMetric {
  return currentMetric;
}

export function renderChart(data: ChartData): void {
  if (!instance) return;
  const { ctx, w, h } = instance;
  const pad = { top: 20, right: 16, bottom: 24, left: 48 };
  const pw = w - pad.left - pad.right;
  const ph = h - pad.top - pad.bottom;

  ctx.clearRect(0, 0, w, h);

  const isPkts = currentMetric === 'pkts';
  const n = data.labels.length;

  if (n < 2) {
    ctx.fillStyle = '#64748B';
    ctx.font = '11px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(data.labels.length === 0 ? 'No data — run the ML pipeline' : 'Collecting data…', w / 2, h / 2);
    return;
  }

  const values = isPkts ? data.pkts : data.anomaly;
  const maxVal = Math.max(...values, isPkts ? 10 : 0.3) * 1.15;
  const minVal = 0;

  function xPos(i: number): number {
    return pad.left + (i / (n - 1)) * pw;
  }

  function yPos(v: number): number {
    return pad.top + ph - ((v - minVal) / (maxVal - minVal)) * ph;
  }

  // Grid lines
  ctx.strokeStyle = '#1E293B';
  ctx.lineWidth = 1;
  const gridLines = isPkts ? 5 : 4;
  for (let i = 0; i <= gridLines; i++) {
    const y = pad.top + (i / gridLines) * ph;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(w - pad.right, y);
    ctx.stroke();

    ctx.fillStyle = '#64748B';
    ctx.font = '9px Inter, sans-serif';
    ctx.textAlign = 'right';
    const val = maxVal - (i / gridLines) * (maxVal - minVal);
    ctx.fillText(val.toFixed(isPkts ? 0 : 2), pad.left - 6, y + 3);
  }

  // Threshold line for anomaly chart
  if (!isPkts) {
    ctx.strokeStyle = 'rgba(239,68,68,0.4)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    const thrY = yPos(0.15);
    ctx.beginPath();
    ctx.moveTo(pad.left, thrY);
    ctx.lineTo(w - pad.right, thrY);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(239,68,68,0.6)';
    ctx.font = '9px Inter, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('threshold 0.15', pad.left + 4, thrY - 3);
  }

  // Data line
  ctx.beginPath();
  ctx.strokeStyle = isPkts ? '#3B82F6' : '#EF4444';
  ctx.lineWidth = 2;
  ctx.lineJoin = 'round';
  for (let i = 0; i < n; i++) {
    const x = xPos(i);
    const y = yPos(values[i]);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Fill under curve
  const lastX = xPos(n - 1);
  ctx.lineTo(lastX, pad.top + ph);
  ctx.lineTo(xPos(0), pad.top + ph);
  ctx.closePath();

  const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + ph);
  if (isPkts) {
    grad.addColorStop(0, 'rgba(59,130,246,0.12)');
    grad.addColorStop(1, 'rgba(59,130,246,0)');
  } else {
    grad.addColorStop(0, 'rgba(239,68,68,0.12)');
    grad.addColorStop(1, 'rgba(239,68,68,0)');
  }
  ctx.fillStyle = grad;
  ctx.fill();

  // X-axis labels
  ctx.fillStyle = '#64748B';
  ctx.font = '9px Inter, sans-serif';
  ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(n / 8));
  for (let i = 0; i < n; i += step) {
    ctx.fillText(data.labels[i], xPos(i), h - 4);
  }
}
