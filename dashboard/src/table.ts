import type { Flow, FilterState, SortState } from './types.js';

export function getProtoColor(proto: string): string {
  switch (proto) {
    case 'MQTT': return '#3B82F6';
    case 'HTTP': return '#22C55E';
    case 'SSH': return '#EAB308';
    case 'ICMP': return '#A855F7';
    default: return '#94A3B8';
  }
}

export function formatBytes(b: number): string {
  if (b < 1024) return `${b}B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)}KB`;
  return `${(b / 1024 / 1024).toFixed(1)}MB`;
}

export function filterFlows(flows: Flow[], filter: FilterState): Flow[] {
  return flows.filter(f => {
    if (filter.proto && f.proto !== filter.proto) return false;
    if (filter.label && f.label !== filter.label) return false;
    if (filter.search) {
      const q = filter.search.toLowerCase();
      if (
        !f.src_ip.includes(q) &&
        !f.dst_ip.includes(q) &&
        !String(f.src_port).includes(q) &&
        !String(f.dst_port).includes(q) &&
        !f.proto.toLowerCase().includes(q)
      ) return false;
    }
    return true;
  });
}

export function sortFlows(flows: Flow[], sort: SortState): Flow[] {
  const { col, asc } = sort;
  return [...flows].sort((a, b) => {
    let va: string | number = a[col];
    let vb: string | number = b[col];
    if (typeof va === 'string') {
      va = va.toLowerCase();
      vb = (vb as string).toLowerCase();
    }
    if (va < vb) return asc ? -1 : 1;
    if (va > vb) return asc ? 1 : -1;
    return 0;
  });
}

export function renderFlowRow(f: Flow): string {
  const cls = f.label !== 'NORMAL' ? 'attack-row' : '';
  const labelClass = f.label.toLowerCase().replace(' ', '_');
  return `<tr class="${cls}">
    <td class="text-mono">${f.src_ip}</td>
    <td class="num">${f.src_port}</td>
    <td class="text-mono">${f.dst_ip}</td>
    <td class="num">${f.dst_port}</td>
    <td><span class="proto-badge" style="color:${getProtoColor(f.proto)}">${f.proto}</span></td>
    <td class="num">${f.total_packets}</td>
    <td class="num">${formatBytes(f.total_bytes)}</td>
    <td class="num">${f.pkts_per_sec.toFixed(1)}</td>
    <td class="num">${f.bytes_per_sec.toFixed(0)}</td>
    <td class="num">${f.duration.toFixed(1)}s</td>
    <td class="num">${f.dst_ip_entropy.toFixed(2)}</td>
    <td><span class="label-badge ${labelClass}">${f.label.replace('_', ' ')}</span></td>
  </tr>`;
}

export function renderTable(
  tbody: HTMLElement,
  flows: Flow[],
  sort: SortState,
  filter: FilterState,
  countEl: HTMLElement,
): void {
  const filtered = filterFlows(flows, filter);
  const sorted = sortFlows(filtered, sort);

  tbody.innerHTML = sorted.map(renderFlowRow).join('');
  countEl.textContent = `${sorted.length} / ${flows.length} flows`;
}

export function updateSortHeaders(table: HTMLElement, sort: SortState): void {
  const headers = table.querySelectorAll<HTMLElement>('th[data-col]');
  headers.forEach(th => {
    th.classList.toggle('sorted', th.dataset.col === sort.col);
  });
}
