import type { Flow, LogEvent, ChartData, ChartMetric, SortState, FilterState, AttackLabel, Protocol } from './types.js';
import type { KpiData, ApiEvent } from './api.js';
import { fetchKpis, fetchFlows, fetchTimeline, fetchEvents, connectEventStream } from './api.js';
import { initChart, resizeChart, setChartMetric, getChartMetric, renderChart } from './chart.js';
import { appendEventToStream } from './events.js';
import { renderTable, updateSortHeaders } from './table.js';
import { updateKPIs } from './kpi.js';
import { initControls } from './controls.js';

const POLL_INTERVAL = 3000;
const CHART_INTERVAL = 5000;

interface AppState {
  phase: string;
  flows: Flow[];
  chartData: ChartData;
  events: LogEvent[];
  sort: SortState;
  filter: FilterState;
  chartMetric: ChartMetric;
  pollTimer: ReturnType<typeof setInterval> | null;
  chartTimer: ReturnType<typeof setInterval> | null;
  kpiData: KpiData | null;
}

const state: AppState = {
  phase: 'BUILD',
  flows: [],
  chartData: { labels: [], pkts: [], anomaly: [] },
  events: [],
  sort: { col: 'total_packets', asc: false },
  filter: { proto: '', label: '', search: '' },
  chartMetric: 'pkts',
  pollTimer: null,
  chartTimer: null,
  kpiData: null,
};

function get<T extends HTMLElement = HTMLElement>(id: string): T {
  return document.getElementById(id) as T;
}

const els = {
  phaseBadge: get<HTMLElement>('phaseBadge'),
  phaseLabel: get<HTMLElement>('phaseLabel'),
  clock: get<HTMLElement>('clock'),
  kpiThroughput: get<HTMLElement>('kpiThroughput'),
  kpiThroughputSub: get<HTMLElement>('kpiThroughputSub'),
  kpiFlows: get<HTMLElement>('kpiFlows'),
  kpiFlowsSub: get<HTMLElement>('kpiFlowsSub'),
  kpiAnomaly: get<HTMLElement>('kpiAnomaly'),
  kpiAnomalySub: get<HTMLElement>('kpiAnomalySub'),
  kpiAnomalyCard: get<HTMLElement>('kpiAnomaly'),
  kpiDetection: get<HTMLElement>('kpiDetection'),
  kpiDetectionSub: get<HTMLElement>('kpiDetectionSub'),
  kpiF1: get<HTMLElement>('kpiF1'),
  kpiF1Sub: get<HTMLElement>('kpiF1Sub'),
  chartCanvas: get<HTMLCanvasElement>('timeChart'),
  eventStream: get<HTMLElement>('eventStream'),
  evtCount: get<HTMLElement>('evtCount'),
  flowBody: get<HTMLElement>('flowBody'),
  flowCount: get<HTMLElement>('flowCount'),
  filterProto: get<HTMLSelectElement>('filterProto'),
  filterLabel: get<HTMLSelectElement>('filterLabel'),
  filterSearch: get<HTMLInputElement>('filterSearch'),
  chartToggle: get<HTMLElement>('chartToggle'),
  tableHead: get<HTMLElement>('flowTable'),
};

function updateClock(): void {
  const d = new Date();
  els.clock.textContent = d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
}

function setPhase(phase: string): void {
  state.phase = phase;
  els.phaseLabel.textContent = phase;
  els.phaseBadge.className = 'phase-badge';
  if (phase === 'ATTACKING') {
    els.phaseBadge.classList.add('attacking');
  } else if (['TRAINING', 'FEATURE_EXTRACTION', 'EVALUATION'].includes(phase)) {
    els.phaseBadge.classList.add('training');
  } else if (!['RUNNING', 'CAPTURING'].includes(phase)) {
    els.phaseBadge.classList.add('idle');
  }
}

function addEvent(level: 'info' | 'warn' | 'error' | 'ok' | 'attack', msg: string): void {
  const d = new Date();
  const t = d.toTimeString().slice(0, 8);
  const evt: LogEvent = { t, level, msg };
  state.events = appendEventToStream(els.eventStream, state.events, evt);
  els.evtCount.textContent = `${state.events.length} events`;
}

async function refreshKPIs(): Promise<void> {
  try {
    state.kpiData = await fetchKpis();
    const k = state.kpiData;
    updateKPIs(k, {
      throughput: els.kpiThroughput,
      throughputSub: els.kpiThroughputSub,
      flows: els.kpiFlows,
      flowsSub: els.kpiFlowsSub,
      anomaly: els.kpiAnomaly,
      anomalySub: els.kpiAnomalySub,
      anomalyCard: els.kpiAnomalyCard.parentElement!,
      detection: els.kpiDetection,
      detectionSub: els.kpiDetectionSub,
      f1: els.kpiF1,
      f1Sub: els.kpiF1Sub,
    });
  } catch {
    // silent — retry on next cycle
  }
}

async function refreshFlows(): Promise<void> {
  try {
    const resp = await fetchFlows({
      proto: state.filter.proto,
      label: state.filter.label,
      search: state.filter.search,
      sort_col: state.sort.col,
      sort_dir: state.sort.asc ? 'asc' : 'desc',
    });
    state.flows = resp.flows as Flow[];
    renderTable(els.flowBody, state.flows, state.sort, state.filter, els.flowCount);
  } catch {
    // silent
  }
}

async function refreshChart(): Promise<void> {
  try {
    const data = await fetchTimeline();
    state.chartData = data as ChartData;
    renderChart(state.chartData);
  } catch {
    // silent
  }
}

async function refreshEvents(): Promise<void> {
  try {
    const resp = await fetchEvents(50);
    const newEvents: LogEvent[] = (resp.events as ApiEvent[]).map((e) => ({
      t: formatTime(e.t),
      level: e.level,
      msg: e.msg,
    }));
    if (newEvents.length > 0) {
      const existingSet = new Set(state.events.map((e) => e.t + e.level + e.msg));
      const toAdd = newEvents.filter((e) => !existingSet.has(e.t + e.level + e.msg));
      for (const evt of toAdd) {
        state.events = appendEventToStream(els.eventStream, state.events, evt);
      }
      els.evtCount.textContent = `${state.events.length} events`;
    }
  } catch {
    // silent
  }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toTimeString().slice(0, 8);
  } catch {
    return iso;
  }
}

async function pollAll(): Promise<void> {
  await Promise.all([refreshKPIs(), refreshFlows(), refreshEvents()]);
}

async function init(): Promise<void> {
  updateClock();
  setInterval(updateClock, 1000);

  initChart(els.chartCanvas);

  try {
    const status = await (await fetch('/api/status')).json();
    setPhase(status.pipeline_phase);
  } catch {
    setPhase('BUILD');
  }

  addEvent('info', 'Dashboard connected');
  addEvent('info', `Pipeline · ${state.phase}`);

  connectEventStream(
    (event, data) => {
      const d = data as { phase?: string; timestamp?: string };
      if (event === 'phase' && d.phase) {
        setPhase(d.phase);
        addEvent('info', `Pipeline · → ${d.phase}`);
      }
      if (event === 'evaluation') {
        addEvent('ok', 'ML evaluation results updated');
        refreshKPIs();
      }
    },
    () => {
      // SSE connection lost — will reconnect automatically
    },
  );

  initControls(addEvent);

  await pollAll();

  state.pollTimer = setInterval(pollAll, POLL_INTERVAL);
  state.chartTimer = setInterval(refreshChart, CHART_INTERVAL);

  /* ─── Event Listeners ─── */

  els.tableHead.querySelector('thead')?.addEventListener('click', (e: MouseEvent) => {
    const th = (e.target as HTMLElement).closest('th[data-col]') as HTMLElement | null;
    if (!th || !th.dataset.col) return;
    const col = th.dataset.col as keyof Flow;
    if (state.sort.col === col) {
      state.sort.asc = !state.sort.asc;
    } else {
      state.sort.col = col;
      state.sort.asc = false;
    }
    updateSortHeaders(els.tableHead, state.sort);
    refreshFlows();
  });

  els.chartToggle.addEventListener('click', () => {
    const next: ChartMetric = getChartMetric() === 'pkts' ? 'anomaly' : 'pkts';
    setChartMetric(next);
    els.chartToggle.textContent = next === 'pkts' ? 'pkts/s' : 'anomaly score';
    renderChart(state.chartData);
  });

  els.filterProto.addEventListener('change', () => {
    state.filter.proto = els.filterProto.value as Protocol | '';
    refreshFlows();
  });
  els.filterLabel.addEventListener('change', () => {
    state.filter.label = els.filterLabel.value as AttackLabel | '';
    refreshFlows();
  });
  els.filterSearch.addEventListener('input', () => {
    state.filter.search = els.filterSearch.value;
    refreshFlows();
  });

  let resizeTimer: ReturnType<typeof setTimeout> | null = null;
  window.addEventListener('resize', () => {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      resizeChart(els.chartCanvas);
      renderChart(state.chartData);
    }, 100);
  });
}

document.addEventListener('DOMContentLoaded', init);
