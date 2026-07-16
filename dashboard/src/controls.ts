import {
  startCapture, stopCapture, startPipeline, stopPipeline,
  runAttack, fetchControlStatus,
} from './api.js';

interface ControlState {
  captureRunning: boolean;
  pipelineRunning: boolean;
  attacking: boolean;
}

const state: ControlState = {
  captureRunning: false,
  pipelineRunning: false,
  attacking: false,
};

let pollTimer: ReturnType<typeof setInterval> | null = null;

export function initControls(addEvent: (level: string, msg: string) => void): void {
  const container = document.getElementById('controlPanel');
  if (!container) return;

  container.innerHTML = `
    <div class="ctrl-group">
      <span class="ctrl-label">Capture</span>
      <button class="ctrl-btn" id="ctrlCapture" data-action="capture">● Start</button>
    </div>
    <div class="ctrl-group">
      <span class="ctrl-label">Pipeline</span>
      <button class="ctrl-btn" id="ctrlPipeline" data-action="pipeline">● Start</button>
    </div>
    <div class="ctrl-divider"></div>
    <span class="ctrl-label">Run Attack</span>
    <button class="ctrl-btn attack" data-attack="recon">↯ Recon</button>
    <button class="ctrl-btn attack" data-attack="bruteforce">↯ Brute Force</button>
    <button class="ctrl-btn attack" data-attack="beacon">↯ C2 Beacon</button>
    <button class="ctrl-btn attack" data-attack="exfil">↯ Exfil</button>
  `;

  const captureBtn = document.getElementById('ctrlCapture') as HTMLButtonElement;
  const pipelineBtn = document.getElementById('ctrlPipeline') as HTMLButtonElement;
  const attackBtns = container.querySelectorAll<HTMLButtonElement>('.ctrl-btn.attack');

  captureBtn.addEventListener('click', async () => {
    captureBtn.disabled = true;
    try {
      if (state.captureRunning) {
        const res = await stopCapture();
        if (res.status === 'stopped') {
          state.captureRunning = false;
          captureBtn.textContent = '● Start';
          captureBtn.className = 'ctrl-btn';
          addEvent('info', 'Capture stopped');
        }
      } else {
        const res = await startCapture();
        if (res.status === 'started' || res.status === 'already_running') {
          state.captureRunning = true;
          captureBtn.textContent = '■ Stop';
          captureBtn.className = 'ctrl-btn running';
          addEvent('info', 'Capture started');
        }
        if (res.status === 'error') {
          addEvent('error', `Capture failed: ${res.message}`);
        }
      }
    } finally {
      captureBtn.disabled = false;
    }
  });

  pipelineBtn.addEventListener('click', async () => {
    pipelineBtn.disabled = true;
    try {
      if (state.pipelineRunning) {
        const res = await stopPipeline();
        if (res.status === 'stopped') {
          state.pipelineRunning = false;
          pipelineBtn.textContent = '● Start';
          pipelineBtn.className = 'ctrl-btn';
          addEvent('info', 'Pipeline stopped');
        }
      } else {
        const res = await startPipeline();
        if (res.status === 'started' || res.status === 'already_running') {
          state.pipelineRunning = true;
          pipelineBtn.textContent = '■ Stop';
          pipelineBtn.className = 'ctrl-btn running';
          addEvent('info', 'Pipeline started');
        }
        if (res.status === 'error') {
          addEvent('error', `Pipeline failed: ${res.message}`);
        }
      }
    } finally {
      pipelineBtn.disabled = false;
    }
  });

  attackBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
      if (state.attacking) return;
      const attackType = btn.dataset.attack!;
      btn.disabled = true;
      state.attacking = true;
      const origText = btn.textContent;
      btn.textContent = '…';
      addEvent('warn', `Attack · ${attackType} started`);
      try {
        const res = await runAttack(attackType);
        btn.textContent = origText;
        if (res.status === 'completed') {
          addEvent('attack', `Attack · ${attackType} completed`);
        } else {
          addEvent('error', `Attack · ${attackType}: ${res.message || res.status}`);
        }
      } catch {
        btn.textContent = origText;
        addEvent('error', `Attack · ${attackType} request failed`);
      } finally {
        state.attacking = false;
        attackBtns.forEach(b => { b.disabled = false; });
      }
    });
  });

  const poll = async () => {
    try {
      const status = await fetchControlStatus();
      if (status.capture_running !== state.captureRunning) {
        state.captureRunning = status.capture_running;
        captureBtn.textContent = status.capture_running ? '■ Stop' : '● Start';
        captureBtn.className = status.capture_running ? 'ctrl-btn running' : 'ctrl-btn';
        addEvent('info', `Capture ${status.capture_running ? 'detected running' : 'stopped'}`);
      }
      if (status.pipeline_running !== state.pipelineRunning) {
        state.pipelineRunning = status.pipeline_running;
        pipelineBtn.textContent = status.pipeline_running ? '■ Stop' : '● Start';
        pipelineBtn.className = status.pipeline_running ? 'ctrl-btn running' : 'ctrl-btn';
        addEvent('info', `Pipeline ${status.pipeline_running ? 'detected running' : 'stopped'}`);
      }
    } catch {
      // silent — retry next cycle
    }
  };

  pollTimer = setInterval(poll, 5000);
  poll();
}

export function destroyControls(): void {
  if (pollTimer !== null) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}
