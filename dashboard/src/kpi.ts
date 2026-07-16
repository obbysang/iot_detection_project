import type { KpiData } from './api.js';

export function updateKPIs(
  data: KpiData,
  elements: {
    throughput: HTMLElement;
    throughputSub: HTMLElement;
    flows: HTMLElement;
    flowsSub: HTMLElement;
    anomaly: HTMLElement;
    anomalySub: HTMLElement;
    anomalyCard: HTMLElement;
    detection: HTMLElement;
    detectionSub: HTMLElement;
    f1: HTMLElement;
    f1Sub: HTMLElement;
  },
): void {
  elements.throughput.textContent = String(data.avg_throughput_pkts);
  elements.throughputSub.textContent = `${(data.total_bytes / 1024).toFixed(0)} KB total`;
  elements.flows.textContent = String(data.active_flows);
  elements.flowsSub.textContent = `${data.flagged_flows} flagged`;
  elements.anomaly.textContent = data.avg_anomaly_score.toFixed(3);
  elements.anomalySub.textContent = data.avg_anomaly_score > 0.15 ? '⚠ ELEVATED' : 'threshold: 0.150';
  elements.anomalyCard.className = `kpi-card ${data.avg_anomaly_score > 0.15 ? 'accent-red' : ''}`;
  elements.detection.textContent = `${data.detection_rate}%`;
  elements.detectionSub.textContent = data.flagged_flows > 0
    ? `${data.flagged_flows} attacks detected`
    : 'last 5 min';

  const f1s = data.f1_scores;
  const modelKeys = Object.keys(f1s);
  if (modelKeys.length > 0) {
    const primary = modelKeys[0];
    const primaryScore = f1s[primary];
    elements.f1.textContent = primaryScore.toFixed(3);
    const parts = modelKeys.map((k) => {
      const short = k === 'random_forest' ? 'RF' : k === 'lstm' ? 'LSTM' : k === 'autoencoder' ? 'AE' : k;
      return `${short} ${f1s[k].toFixed(3)}`;
    });
    elements.f1Sub.textContent = parts.join(' · ');
  } else {
    elements.f1.textContent = '—';
    elements.f1Sub.textContent = 'No model data';
  }
}
