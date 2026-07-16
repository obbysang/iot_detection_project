import type { LogEvent, EventLevel } from './types.js';

const MAX_EVENTS = 500;

export function appendEvent(
  list: LogEvent[],
  t: string,
  level: EventLevel,
  msg: string,
): LogEvent[] {
  const evt: LogEvent = { t, level, msg };
  const updated = [...list, evt];
  if (updated.length > MAX_EVENTS) {
    return updated.slice(updated.length - MAX_EVENTS);
  }
  return updated;
}

export function renderEventElement(evt: LogEvent): HTMLDivElement {
  const div = document.createElement('div');
  div.className = 'event-entry';
  div.innerHTML = `
    <span class="evt-time">${evt.t}</span>
    <span class="evt-level ${evt.level}">${evt.level}</span>
    <span class="evt-msg">${evt.msg}</span>
  `;
  return div;
}

export function renderEventStream(container: HTMLElement, events: LogEvent[]): void {
  container.innerHTML = '';
  for (const evt of events) {
    container.appendChild(renderEventElement(evt));
  }
  container.scrollTop = container.scrollHeight;
}

export function appendEventToStream(
  container: HTMLElement,
  events: LogEvent[],
  evt: LogEvent,
): LogEvent[] {
  const updated = appendEvent(events, evt.t, evt.level, evt.msg);
  container.appendChild(renderEventElement(evt));
  if (container.children.length > MAX_EVENTS) {
    container.removeChild(container.firstChild!);
  }
  container.scrollTop = container.scrollHeight;
  return updated;
}
