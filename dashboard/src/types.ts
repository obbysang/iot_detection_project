export type Protocol = 'MQTT' | 'HTTP' | 'SSH' | 'ICMP' | 'OTHER';

export type AttackLabel =
  | 'NORMAL'
  | 'RECON'
  | 'BRUTEFORCE'
  | 'C2_BEACON'
  | 'EXFIL_RANSOMWARE';

export type PipelinePhase =
  | 'BUILD'
  | 'RUNNING'
  | 'CAPTURING'
  | 'ATTACKING'
  | 'POST_CAPTURE'
  | 'FEATURE_EXTRACTION'
  | 'LABELING'
  | 'TRAINING'
  | 'EVALUATION';

export type EventLevel = 'info' | 'warn' | 'error' | 'ok' | 'attack';

export type ChartMetric = 'pkts' | 'anomaly';

export interface Flow {
  src_ip: string;
  src_port: number;
  dst_ip: string;
  dst_port: number;
  proto: Protocol;
  duration: number;
  total_packets: number;
  total_bytes: number;
  fwd_packets: number;
  bwd_packets: number;
  fwd_bytes: number;
  bwd_bytes: number;
  mean_pkt_len: number;
  std_pkt_len: number;
  mean_iat: number;
  std_iat: number;
  pkts_per_sec: number;
  bytes_per_sec: number;
  uncommon_port: number;
  dst_ip_entropy: number;
  label: AttackLabel;
}

export interface LogEvent {
  t: string;
  level: EventLevel;
  msg: string;
}

export interface ChartData {
  labels: string[];
  pkts: number[];
  anomaly: number[];
}

export interface SortState {
  col: keyof Flow;
  asc: boolean;
}

export interface FilterState {
  proto: Protocol | '';
  label: AttackLabel | '';
  search: string;
}

export interface AppState {
  phaseIdx: number;
  flows: Flow[];
  chartData: ChartData;
  events: LogEvent[];
  sort: SortState;
  filter: FilterState;
  chartMetric: ChartMetric;
  simInterval: ReturnType<typeof setInterval> | null;
  phaseTimer: ReturnType<typeof setInterval> | null;
}

export interface ChartInstance {
  ctx: CanvasRenderingContext2D;
  w: number;
  h: number;
}
