import type { Flow, EventLevel } from './types.js';

export interface KpiData {
  avg_throughput_pkts: number;
  total_bytes: number;
  active_flows: number;
  flagged_flows: number;
  avg_anomaly_score: number;
  detection_rate: number;
  f1_scores: Record<string, number>;
  pipeline_phase: string;
}

export interface FlowResponse {
  flows: Flow[];
  total: number;
  filtered: number;
}

export interface TimelineData {
  labels: string[];
  pkts: number[];
  anomaly: number[];
}

export interface ApiEvent {
  t: string;
  level: EventLevel;
  msg: string;
}

export interface EventsResponse {
  events: ApiEvent[];
}

export interface ModelEval {
  f1_score: number;
  roc_auc: number;
  false_positive_rate: number;
}

export interface ModelsResponse {
  models: Record<string, ModelEval>;
  available: string[];
}

export interface StatusData {
  pipeline_phase: string;
  models_available: string[];
  flows_count: number;
  evaluation_loaded: boolean;
  last_loaded: string | null;
  phase_history: Array<{ phase: string; timestamp: string }>;
}

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v) url.searchParams.set(k, v);
    }
  }
  const res = await fetch(url.toString());
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchStatus(): Promise<StatusData> {
  return apiGet<StatusData>('/api/status');
}

export async function fetchKpis(): Promise<KpiData> {
  return apiGet<KpiData>('/api/kpis');
}

export async function fetchFlows(opts?: {
  proto?: string;
  label?: string;
  search?: string;
  sort_col?: string;
  sort_dir?: string;
  limit?: number;
}): Promise<FlowResponse> {
  return apiGet<FlowResponse>('/api/flows', {
    proto: opts?.proto ?? '',
    label: opts?.label ?? '',
    search: opts?.search ?? '',
    sort_col: opts?.sort_col ?? 'total_packets',
    sort_dir: opts?.sort_dir ?? 'desc',
    limit: String(opts?.limit ?? 200),
  });
}

export async function fetchTimeline(): Promise<TimelineData> {
  return apiGet<TimelineData>('/api/flows/timeline');
}

export async function fetchEvents(limit = 100): Promise<EventsResponse> {
  return apiGet<EventsResponse>('/api/events', { limit: String(limit) });
}

export async function fetchModels(): Promise<ModelsResponse> {
  return apiGet<ModelsResponse>('/api/models');
}

/* ── Control API ── */

export interface ControlStatus {
  capture_running: boolean;
  pipeline_running: boolean;
}

export interface ActionResponse {
  status: string;
  pid?: number;
  message?: string;
  output?: string;
}

export async function startCapture(): Promise<ActionResponse> {
  return apiPost<ActionResponse>('/api/control/capture/start');
}

export async function stopCapture(): Promise<ActionResponse> {
  return apiPost<ActionResponse>('/api/control/capture/stop');
}

export async function startPipeline(): Promise<ActionResponse> {
  return apiPost<ActionResponse>('/api/control/pipeline/start');
}

export async function stopPipeline(): Promise<ActionResponse> {
  return apiPost<ActionResponse>('/api/control/pipeline/stop');
}

export async function runAttack(attackType: string): Promise<ActionResponse> {
  return apiPost<ActionResponse>(`/api/control/attack/${attackType}`);
}

export async function fetchControlStatus(): Promise<ControlStatus> {
  return apiGet<ControlStatus>('/api/control/status');
}

/* ── SSE ── */

export function connectEventStream(
  onEvent: (event: string, data: unknown) => void,
  onError?: (err: Event) => void,
): EventSource {
  const es = new EventSource('/api/events/stream');

  es.addEventListener('init', (e) => onEvent('init', JSON.parse(e.data)));
  es.addEventListener('phase', (e) => onEvent('phase', JSON.parse(e.data)));
  es.addEventListener('evaluation', (e) => onEvent('evaluation', JSON.parse(e.data)));
  es.addEventListener('heartbeat', (e) => onEvent('heartbeat', JSON.parse(e.data)));
  es.addEventListener('message', (e) => onEvent('message', JSON.parse(e.data)));

  es.onerror = (err) => {
    if (onError) onError(err);
  };

  return es;
}
