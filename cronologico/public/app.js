document.addEventListener('DOMContentLoaded', () => {
  // Estado local
  let spacesState = [];
  let cronConfigState = { enabled: true, intervalSeconds: 300, nextRunSecondsLeft: 0 };
  let logCounts = { general: 0, direct: 0, space: 0, alerts: 0 };
  let ws = null;
  let countdownTimer = null;
  let secondsLeft = 0;

  // Elementos DOM
  const spacesGrid = document.getElementById('spacesGrid');
  const statTotal = document.getElementById('statTotal');
  const statOnline = document.getElementById('statOnline');
  const statDegraded = document.getElementById('statDegraded');
  const statOffline = document.getElementById('statOffline');
  const statLatency = document.getElementById('statLatency');
  const nextRunTimer = document.getElementById('nextRunTimer');
  
  const searchInput = document.getElementById('searchInput');
  const intervalSelect = document.getElementById('intervalSelect');
  const btnRunNow = document.getElementById('btnRunNow');
  const btnToggleCron = document.getElementById('btnToggleCron');
  const cronStatusIcon = document.getElementById('cronStatusIcon');
  const cronStatusText = document.getElementById('cronStatusText');
  const btnClearConsoles = document.getElementById('btnClearConsoles');
  const chkAutoScroll = document.getElementById('chkAutoScroll');
  const wsConnectionStatus = document.getElementById('wsConnectionStatus');

  const tabBtns = document.querySelectorAll('.tab-btn');
  const consoleBodies = {
    general: document.getElementById('console-general'),
    direct: document.getElementById('console-direct'),
    space: document.getElementById('console-space'),
    alerts: document.getElementById('console-alerts')
  };

  const badgeGeneral = document.getElementById('badgeGeneral');
  const badgeDirect = document.getElementById('badgeDirect');
  const badgeSpace = document.getElementById('badgeSpace');
  const badgeAlerts = document.getElementById('badgeAlerts');

  // Conectar WebSockets
  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      wsConnectionStatus.textContent = '● CONECTADO EN VIVO';
      wsConnectionStatus.style.color = 'var(--color-online)';
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);

        if (payload.type === 'INIT') {
          spacesState = payload.data.spaces;
          cronConfigState = payload.data.cronConfig;
          updateStats(payload.data.stats);
          renderSpacesGrid();

          // Renderizar logs históricos
          if (payload.data.logs && Array.isArray(payload.data.logs)) {
            payload.data.logs.forEach(log => appendLog(log));
          }

          startCountdown(cronConfigState.nextRunSecondsLeft);
        } 
        else if (payload.type === 'STATE_UPDATE') {
          spacesState = payload.data.spaces;
          cronConfigState = payload.data.cronConfig;
          updateStats(payload.data.stats);
          renderSpacesGrid();
          startCountdown(cronConfigState.nextRunSecondsLeft);
        }
        else if (payload.type === 'LOG') {
          appendLog(payload.data);
        }
      } catch (err) {
        console.error('Error parseando WebSocket payload:', err);
      }
    };

    ws.onclose = () => {
      wsConnectionStatus.textContent = '○ DESCONECTADO (Reconectando...)';
      wsConnectionStatus.style.color = 'var(--color-offline)';
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
      console.error('WebSocket Error:', err);
    };
  }

  // Renderizar Grid de Espacios
  function renderSpacesGrid() {
    const query = searchInput.value.toLowerCase().trim();
    spacesGrid.innerHTML = '';

    const filtered = spacesState.filter(s => 
      s.name.toLowerCase().includes(query) ||
      s.user.toLowerCase().includes(query) ||
      s.directUrl.toLowerCase().includes(query)
    );

    if (filtered.length === 0) {
      spacesGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-dim); padding: 40px;">No se encontraron espacios que coincidan con "${query}"</div>`;
      return;
    }

    filtered.forEach(s => {
      const card = document.createElement('div');
      card.className = 'space-card';
      
      let statusClass = 'status-pending';
      let statusLabel = 'Pendiente';
      if (s.overallStatus === 'ONLINE') {
        statusClass = 'status-online';
        statusLabel = 'ONLINE';
      } else if (s.overallStatus === 'DEGRADED') {
        statusClass = 'status-degraded';
        statusLabel = 'DEGRADADO';
      } else if (s.overallStatus === 'OFFLINE') {
        statusClass = 'status-offline';
        statusLabel = 'OFFLINE';
      }

      const directLatencyStr = s.directStatus.latencyMs > 0 ? `${s.directStatus.latencyMs} ms` : '--';
      const spaceLatencyStr = s.spaceStatus.latencyMs > 0 ? `${s.spaceStatus.latencyMs} ms` : '--';

      card.innerHTML = `
        <div class="space-card-header">
          <div>
            <div class="space-name">${escapeHtml(s.name)}</div>
            <div class="space-user">@${escapeHtml(s.user)} / ${escapeHtml(s.repo)}</div>
          </div>
          <span class="status-badge ${statusClass}">${statusLabel}</span>
        </div>

        <div class="space-details">
          <div class="detail-row">
            <span class="detail-label">⚡ App Directa (.hf.space):</span>
            <span class="detail-val ${s.directStatus.status === 'ONLINE' ? 'text-success' : s.directStatus.status === 'OFFLINE' ? 'text-danger' : ''}">${directLatencyStr} ${s.directStatus.statusCode ? `(${s.directStatus.statusCode})` : ''}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">🚀 Espacio HF (Landing):</span>
            <span class="detail-val ${s.spaceStatus.status === 'ONLINE' ? 'text-success' : s.spaceStatus.status === 'OFFLINE' ? 'text-danger' : ''}">${spaceLatencyStr} ${s.spaceStatus.statusCode ? `(${s.spaceStatus.statusCode})` : ''}</span>
          </div>
        </div>

        <div class="space-actions">
          <a href="${s.directUrl}" target="_blank" class="btn btn-secondary btn-xs">⚡ Directo</a>
          <a href="${s.spaceUrl}" target="_blank" class="btn btn-secondary btn-xs">🚀 Espacio</a>
          <button class="btn btn-outline btn-xs btn-ping-single" data-id="${s.id}">🔍 Ping</button>
        </div>
      `;

      spacesGrid.appendChild(card);
    });

    // Event listener para ping individual
    document.querySelectorAll('.btn-ping-single').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = e.target.getAttribute('data-id');
        fetch(`/api/ping-space/${id}`, { method: 'POST' });
      });
    });
  }

  // Actualizar estadísticas globales
  function updateStats(stats) {
    if (!stats) return;
    statTotal.textContent = stats.total;
    statOnline.textContent = stats.online;
    statDegraded.textContent = stats.degraded;
    statOffline.textContent = stats.offline;
    statLatency.textContent = `${stats.avgLatency} ms`;
  }

  // Agregar entrada de Log a las consolas correspondientes
  function appendLog(log) {
    const timeFormatted = new Date(log.timestamp).toLocaleTimeString();
    
    // Crear elemento de línea de log
    const logLine = document.createElement('div');
    logLine.className = `log-line level-${log.level}`;
    logLine.innerHTML = `
      <span class="log-time">[${timeFormatted}]</span>
      <span class="log-channel">[${log.channel.toUpperCase()}]</span>
      <span class="log-msg">${escapeHtml(log.message)}</span>
    `;

    // 1. Siempre agregar a Consola General
    consoleBodies.general.appendChild(logLine.cloneNode(true));
    logCounts.general++;
    badgeGeneral.textContent = logCounts.general;

    // 2. Agregar a consola específica de canal
    if (log.channel === 'direct' && consoleBodies.direct) {
      consoleBodies.direct.appendChild(logLine.cloneNode(true));
      logCounts.direct++;
      badgeDirect.textContent = logCounts.direct;
    } 
    else if (log.channel === 'space' && consoleBodies.space) {
      consoleBodies.space.appendChild(logLine.cloneNode(true));
      logCounts.space++;
      badgeSpace.textContent = logCounts.space;
    } 
    else if ((log.channel === 'alerts' || log.level === 'warn' || log.level === 'error') && consoleBodies.alerts) {
      consoleBodies.alerts.appendChild(logLine.cloneNode(true));
      logCounts.alerts++;
      badgeAlerts.textContent = logCounts.alerts;
    }

    // Auto-scroll si está activado
    if (chkAutoScroll.checked) {
      Object.values(consoleBodies).forEach(body => {
        body.scrollTop = body.scrollHeight;
      });
    }
  }

  // Manejo de la cuenta regresiva del Cron
  function startCountdown(sec) {
    secondsLeft = sec;
    if (countdownTimer) clearInterval(countdownTimer);

    updateTimerDisplay();
    countdownTimer = setInterval(() => {
      if (secondsLeft > 0) {
        secondsLeft--;
        updateTimerDisplay();
      }
    }, 1000);
  }

  function updateTimerDisplay() {
    if (!cronConfigState.enabled) {
      nextRunTimer.textContent = 'PAUSADO';
      nextRunTimer.style.color = 'var(--color-degraded)';
      return;
    }
    nextRunTimer.style.color = 'var(--accent-cyan)';
    const m = Math.floor(secondsLeft / 60).toString().padStart(2, '0');
    const s = (secondsLeft % 60).toString().padStart(2, '0');
    nextRunTimer.textContent = `${m}:${s}`;
  }

  // Cambio de pestañas en consolas
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const targetTab = btn.getAttribute('data-tab');
      Object.keys(consoleBodies).forEach(tab => {
        if (tab === targetTab) {
          consoleBodies[tab].classList.add('active');
        } else {
          consoleBodies[tab].classList.remove('active');
        }
      });
    });
  });

  // Event Listeners para Controles
  btnRunNow.addEventListener('click', () => {
    fetch('/api/ping-all', { method: 'POST' });
  });

  btnToggleCron.addEventListener('click', () => {
    cronConfigState.enabled = !cronConfigState.enabled;
    fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: cronConfigState.enabled })
    });

    if (cronConfigState.enabled) {
      cronStatusIcon.textContent = '⏸';
      cronStatusText.textContent = 'Pausar Cron';
    } else {
      cronStatusIcon.textContent = '▶';
      cronStatusText.textContent = 'Reanudar Cron';
    }
  });

  intervalSelect.addEventListener('change', (e) => {
    const val = parseInt(e.target.value, 10);
    fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intervalSeconds: val })
    });
  });

  btnClearConsoles.addEventListener('click', () => {
    Object.keys(consoleBodies).forEach(tab => {
      consoleBodies[tab].innerHTML = `<div class="log-welcome">--- CONSOLA ${tab.toUpperCase()} REINICIADA ---</div>`;
      logCounts[tab] = 0;
    });
    badgeGeneral.textContent = '0';
    badgeDirect.textContent = '0';
    badgeSpace.textContent = '0';
    badgeAlerts.textContent = '0';
  });

  searchInput.addEventListener('input', renderSpacesGrid);

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Iniciar WebSocket
  connectWebSocket();
});
