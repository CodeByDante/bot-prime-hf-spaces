// Client-Side Engine for Hugging Face Static Space & Node environment
document.addEventListener('DOMContentLoaded', async () => {
  // Lista de 19 espacios incorporada
  const SPACES = [
    { id: "moderador-twisted", name: "moderador twisted", directUrl: "https://asdasdsasda-moderadortwisted.hf.space", spaceUrl: "https://huggingface.co/spaces/asdasdsasda/moderadortwisted", user: "asdasdsasda", repo: "moderadortwisted" },
    { id: "waifu-of-brody-bot", name: "Waifu of Brody bot", directUrl: "https://asdasdsasda-waifuofbrodybot.hf.space", spaceUrl: "https://huggingface.co/spaces/asdasdsasda/waifuofbrodybot", user: "asdasdsasda", repo: "waifuofbrodybot" },
    { id: "fastbeat-bot", name: "FastBeat Bot", directUrl: "https://brodyloyol-fastbeatbot.hf.space", spaceUrl: "https://huggingface.co/spaces/brodyloyol/fastbeatbot", user: "brodyloyol", repo: "fastbeatbot" },
    { id: "waifuofdante-b2", name: "waifuofdante b2", directUrl: "https://brodyloyol-waifuofdanteb2.hf.space", spaceUrl: "https://huggingface.co/spaces/brodyloyol/waifuofdanteb2", user: "brodyloyol", repo: "waifuofdanteb2" },
    { id: "waifuof-dante", name: "waifuof dante", directUrl: "https://brodyloyol-waifuofdantebot.hf.space", spaceUrl: "https://huggingface.co/spaces/brodyloyol/waifuofdantebot", user: "brodyloyol", repo: "waifuofdantebot" },
    { id: "code-by-dante", name: "code by dante", directUrl: "https://codebybrody-codebydante.hf.space", spaceUrl: "https://huggingface.co/spaces/codebybrody/codebydante", user: "codebybrody", repo: "codebydante" },
    { id: "twisted-brody-mangaflow", name: "Twisted Brody MangaFlow", directUrl: "https://codebybrody-twistedbrodymangaflow.hf.space", spaceUrl: "https://huggingface.co/spaces/codebybrody/twistedbrodymangaflow", user: "codebybrody", repo: "twistedbrodymangaflow" },
    { id: "brody-file-stream-bot", name: "brody file stream bot", directUrl: "https://codebydante-brodyfilestreambot.hf.space", spaceUrl: "https://huggingface.co/spaces/codebydante/brodyfilestreambot", user: "codebydante", repo: "brodyfilestreambot" },
    { id: "twisted-audio", name: "Twisted Audio", directUrl: "https://codebydante-twisted-audio.hf.space", spaceUrl: "https://huggingface.co/spaces/codebydante/twisted-audio", user: "codebydante", repo: "twisted-audio" },
    { id: "twisted-brody-mangaflow-bot-telegram", name: "Twisted Brody MangaFlow BOT TELEGRAM", directUrl: "https://codebydante-twistedbrodymangaflowbot.hf.space", spaceUrl: "https://huggingface.co/spaces/codebydante/twistedbrodymangaflowbot", user: "codebydante", repo: "twistedbrodymangaflowbot" },
    { id: "twistedstreamingbrody-peliculas-hd-bot", name: "twistedstreamingbrody peliculas HD bot", directUrl: "https://codebydante-twistedstreamingbrody.hf.space", spaceUrl: "https://huggingface.co/spaces/codebydante/twistedstreamingbrody", user: "codebydante", repo: "twistedstreamingbrody" },
    { id: "entity-of-brody-bot", name: "Entity of brody bot", directUrl: "https://danteloyola-entitydante.hf.space", spaceUrl: "https://huggingface.co/spaces/danteloyola/entitydante", user: "danteloyola", repo: "entitydante" },
    { id: "twistedtraductorbot", name: "@twistedtraductorbot", directUrl: "https://danteloyola-twistedtraductorbot.hf.space", spaceUrl: "https://huggingface.co/spaces/danteloyola/twistedtraductorbot", user: "danteloyola", repo: "twistedtraductorbot" },
    { id: "video-album-maker", name: "Video Album Maker", directUrl: "https://danteloyola-videoalbummaker.hf.space", spaceUrl: "https://huggingface.co/spaces/danteloyola/videoalbummaker", user: "danteloyola", repo: "videoalbummaker" },
    { id: "bot-unidor", name: "bot unidor", directUrl: "https://danteloyolasalvador-botunidor.hf.space", spaceUrl: "https://huggingface.co/spaces/danteloyolasalvador/botunidor", user: "danteloyolasalvador", repo: "botunidor" },
    { id: "user-bot-prime-twisted", name: "user bot prime twisted", directUrl: "https://danteloyolasalvador-userbotfilestream.hf.space", spaceUrl: "https://huggingface.co/spaces/danteloyolasalvador/userbotfilestream", user: "danteloyolasalvador", repo: "userbotfilestream" },
    { id: "convertidor-qh", name: "convertidor qh", directUrl: "https://gonzaloloyola-convertidorqh.hf.space", spaceUrl: "https://huggingface.co/spaces/gonzaloloyola/convertidorqh", user: "gonzaloloyola", repo: "convertidorqh" },
    { id: "miniaturas-pro-bot", name: "/Miniaturas Pro Bot", directUrl: "https://gonzaloloyola-miniaturasprobot.hf.space", spaceUrl: "https://huggingface.co/spaces/gonzaloloyola/miniaturasprobot", user: "gonzaloloyola", repo: "miniaturasprobot" },
    { id: "smartvideosplitterbot", name: "SmartVideoSplitterBot", directUrl: "https://gonzaloloyola-smartvideosplitterbot.hf.space", spaceUrl: "https://huggingface.co/spaces/gonzaloloyola/smartvideosplitterbot", user: "gonzaloloyola", repo: "smartvideosplitterbot" },
    { id: "bot-cronologico", name: "Bot Cronológico Pinger", directUrl: "https://codebydante-cronologico.static.hf.space", spaceUrl: "https://huggingface.co/spaces/codebydante/cronologico", user: "codebydante", repo: "cronologico" }
  ];

  // Estado
  let spacesState = SPACES.map(s => ({
    ...s,
    directStatus: { status: 'PENDING', latencyMs: 0, error: null },
    spaceStatus: { status: 'PENDING', latencyMs: 0, error: null },
    overallStatus: 'UNKNOWN'
  }));

  let cronEnabled = true;
  let intervalSeconds = 300;
  let secondsLeft = 300;
  let isRunning = false;
  let timerInterval = null;

  let logCounts = { general: 0, direct: 0, space: 0, alerts: 0 };

  // DOM Elements
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

  function logEvent(channel, level, message) {
    const timeStr = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.className = `log-line level-${level}`;
    line.innerHTML = `
      <span class="log-time">[${timeStr}]</span>
      <span class="log-channel">[${channel.toUpperCase()}]</span>
      <span class="log-msg">${escapeHtml(message)}</span>
    `;

    consoleBodies.general.appendChild(line.cloneNode(true));
    logCounts.general++;
    badgeGeneral.textContent = logCounts.general;

    if (channel === 'direct') {
      consoleBodies.direct.appendChild(line.cloneNode(true));
      logCounts.direct++;
      badgeDirect.textContent = logCounts.direct;
    } else if (channel === 'space') {
      consoleBodies.space.appendChild(line.cloneNode(true));
      logCounts.space++;
      badgeSpace.textContent = logCounts.space;
    } else if (channel === 'alerts' || level === 'warn' || level === 'error') {
      consoleBodies.alerts.appendChild(line.cloneNode(true));
      logCounts.alerts++;
      badgeAlerts.textContent = logCounts.alerts;
    }

    if (chkAutoScroll.checked) {
      Object.values(consoleBodies).forEach(b => b.scrollTop = b.scrollHeight);
    }
  }

  async function pingEndpoint(url) {
    const start = performance.now();
    try {
      // Intentar fetch no-cors / normal para visitar la página
      await fetch(url, { mode: 'no-cors', cache: 'no-cache' });
      const latencyMs = Math.round(performance.now() - start);
      return { ok: true, latencyMs, error: null };
    } catch (err) {
      const latencyMs = Math.round(performance.now() - start);
      return { ok: false, latencyMs, error: err.message };
    }
  }

  async function diagnoseSpace(index) {
    const s = spacesState[index];
    logEvent('general', 'info', `Iniciando diagnóstico para [${s.name}]...`);

    // 1. Visit App Directa (.hf.space)
    logEvent('direct', 'info', `Consultando App Directa: ${s.directUrl}`);
    const resDirect = await pingEndpoint(s.directUrl);
    s.directStatus = {
      status: resDirect.ok ? 'ONLINE' : 'OFFLINE',
      latencyMs: resDirect.latencyMs,
      error: resDirect.error
    };

    if (resDirect.ok) {
      logEvent('direct', 'success', `[App Directa] ${s.name} respondió OK en ${resDirect.latencyMs} ms`);
    } else {
      logEvent('direct', 'error', `[App Directa] Fallo en ${s.name}: ${resDirect.error}`);
      logEvent('alerts', 'warn', `Alerta en App Directa [${s.name}]: ${resDirect.error}`);
    }

    // 2. Visit Espacio HF (huggingface.co/spaces/...)
    logEvent('space', 'info', `Consultando Landing Espacio HF: ${s.spaceUrl}`);
    const resSpace = await pingEndpoint(s.spaceUrl);
    s.spaceStatus = {
      status: resSpace.ok ? 'ONLINE' : 'OFFLINE',
      latencyMs: resSpace.latencyMs,
      error: resSpace.error
    };

    if (resSpace.ok) {
      logEvent('space', 'success', `[Espacio HF] Landing de ${s.name} respondió OK en ${resSpace.latencyMs} ms`);
    } else {
      logEvent('space', 'error', `[Espacio HF] Fallo en landing de ${s.name}: ${resSpace.error}`);
      logEvent('alerts', 'warn', `Alerta en Espacio HF [${s.name}]: ${resSpace.error}`);
    }

    // Evaluar estado global
    if (resDirect.ok && resSpace.ok) {
      s.overallStatus = 'ONLINE';
      logEvent('general', 'success', `Diagnóstico COMPLETADO [${s.name}]: ONLINE (${resDirect.latencyMs}ms / ${resSpace.latencyMs}ms)`);
    } else if (resDirect.ok || resSpace.ok) {
      s.overallStatus = 'DEGRADED';
      logEvent('general', 'warn', `Diagnóstico PARCIAL [${s.name}]: DEGRADADO`);
      logEvent('alerts', 'warn', `Espacio [${s.name}] en estado DEGRADADO`);
    } else {
      s.overallStatus = 'OFFLINE';
      logEvent('general', 'error', `Diagnóstico FALLIDO [${s.name}]: OFFLINE`);
      logEvent('alerts', 'error', `CRÍTICO: Espacio [${s.name}] está OFFLINE`);
    }

    renderGrid();
    updateStats();
  }

  async function runCycle() {
    if (isRunning) return;
    isRunning = true;
    secondsLeft = intervalSeconds;

    logEvent('general', 'info', `=== INICIANDO CICLO DE DIAGNÓSTICO EN VIVO (${spacesState.length} ESPACIOS) ===`);

    for (let i = 0; i < spacesState.length; i++) {
      await diagnoseSpace(i);
      await new Promise(r => setTimeout(r, 200));
    }

    logEvent('general', 'success', `=== CICLO DE DIAGNÓSTICO COMPLETADO CON ÉXITO ===`);
    isRunning = false;
  }

  function renderGrid() {
    const q = searchInput.value.toLowerCase().trim();
    spacesGrid.innerHTML = '';

    const filtered = spacesState.filter(s =>
      s.name.toLowerCase().includes(q) ||
      s.user.toLowerCase().includes(q) ||
      s.directUrl.toLowerCase().includes(q)
    );

    filtered.forEach(s => {
      const card = document.createElement('div');
      card.className = 'space-card';

      let stClass = 'status-pending';
      let stLbl = 'PENDIENTE';
      if (s.overallStatus === 'ONLINE') { stClass = 'status-online'; stLbl = 'ONLINE'; }
      else if (s.overallStatus === 'DEGRADED') { stClass = 'status-degraded'; stLbl = 'DEGRADADO'; }
      else if (s.overallStatus === 'OFFLINE') { stClass = 'status-offline'; stLbl = 'OFFLINE'; }

      card.innerHTML = `
        <div class="space-card-header">
          <div>
            <div class="space-name">${escapeHtml(s.name)}</div>
            <div class="space-user">@${escapeHtml(s.user)} / ${escapeHtml(s.repo)}</div>
          </div>
          <span class="status-badge ${stClass}">${stLbl}</span>
        </div>

        <div class="space-details">
          <div class="detail-row">
            <span class="detail-label">⚡ App Directa (.hf.space):</span>
            <span class="detail-val ${s.directStatus.status === 'ONLINE' ? 'text-success' : s.directStatus.status === 'OFFLINE' ? 'text-danger' : ''}">${s.directStatus.latencyMs > 0 ? s.directStatus.latencyMs + ' ms' : '--'}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">🚀 Espacio HF (Landing):</span>
            <span class="detail-val ${s.spaceStatus.status === 'ONLINE' ? 'text-success' : s.spaceStatus.status === 'OFFLINE' ? 'text-danger' : ''}">${s.spaceStatus.latencyMs > 0 ? s.spaceStatus.latencyMs + ' ms' : '--'}</span>
          </div>
        </div>

        <div class="space-actions">
          <a href="${s.directUrl}" target="_blank" class="btn btn-secondary btn-xs">⚡ Directo</a>
          <a href="${s.spaceUrl}" target="_blank" class="btn btn-secondary btn-xs">🚀 Espacio</a>
          <button class="btn btn-outline btn-xs btn-single" data-id="${s.id}">🔍 Ping</button>
        </div>
      `;

      spacesGrid.appendChild(card);
    });

    document.querySelectorAll('.btn-single').forEach(b => {
      b.addEventListener('click', (e) => {
        const id = e.target.getAttribute('data-id');
        const idx = spacesState.findIndex(x => x.id === id);
        if (idx !== -1) diagnoseSpace(idx);
      });
    });
  }

  function updateStats() {
    statTotal.textContent = spacesState.length;
    let on = 0, deg = 0, off = 0, latSum = 0, latCnt = 0;
    spacesState.forEach(s => {
      if (s.overallStatus === 'ONLINE') on++;
      else if (s.overallStatus === 'DEGRADED') deg++;
      else if (s.overallStatus === 'OFFLINE') off++;

      if (s.directStatus.latencyMs > 0) {
        latSum += s.directStatus.latencyMs;
        latCnt++;
      }
    });

    statOnline.textContent = on;
    statDegraded.textContent = deg;
    statOffline.textContent = off;
    statLatency.textContent = latCnt > 0 ? `${Math.round(latSum / latCnt)} ms` : '0 ms';
  }

  function startTimer() {
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      if (!cronEnabled) {
        nextRunTimer.textContent = 'PAUSADO';
        return;
      }
      if (secondsLeft > 0) {
        secondsLeft--;
        const m = Math.floor(secondsLeft / 60).toString().padStart(2, '0');
        const sec = (secondsLeft % 60).toString().padStart(2, '0');
        nextRunTimer.textContent = `${m}:${sec}`;
      } else {
        runCycle();
      }
    }, 1000);
  }

  // Tabs
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const target = btn.getAttribute('data-tab');
      Object.keys(consoleBodies).forEach(tab => {
        if (tab === target) consoleBodies[tab].classList.add('active');
        else consoleBodies[tab].classList.remove('active');
      });
    });
  });

  // Controls
  btnRunNow.addEventListener('click', runCycle);

  btnToggleCron.addEventListener('click', () => {
    cronEnabled = !cronEnabled;
    cronStatusIcon.textContent = cronEnabled ? '⏸' : '▶';
    cronStatusText.textContent = cronEnabled ? 'Pausar Cron' : 'Reanudar Cron';
  });

  intervalSelect.addEventListener('change', (e) => {
    intervalSeconds = parseInt(e.target.value, 10);
    secondsLeft = intervalSeconds;
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

  searchInput.addEventListener('input', renderGrid);

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Init
  renderGrid();
  updateStats();
  startTimer();
  runCycle();
});
