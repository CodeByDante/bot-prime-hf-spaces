const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const path = require('path');
const fs = require('fs');

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

const PORT = process.env.PORT || 3000;
const SPACES_FILE = path.join(__dirname, 'spaces.json');

// Cargar espacios
let spaces = [];
try {
  const data = fs.readFileSync(SPACES_FILE, 'utf8');
  spaces = JSON.parse(data);
} catch (err) {
  console.error('Error al leer spaces.json:', err);
  spaces = [];
}

// Estado en memoria para diagnósticos
const spacesState = spaces.map(space => ({
  ...space,
  directStatus: { status: 'PENDING', statusCode: 0, latencyMs: 0, lastCheck: null, error: null },
  spaceStatus: { status: 'PENDING', statusCode: 0, latencyMs: 0, lastCheck: null, error: null },
  overallStatus: 'UNKNOWN'
}));

// Historial de logs en memoria (máximo 500)
const logHistory = [];
const MAX_LOG_HISTORY = 500;

// Configuración de ejecución cronológica
let cronConfig = {
  enabled: true,
  intervalSeconds: 300, // 5 minutos por defecto
  lastRun: null,
  nextRun: null,
  isRunningCycle: false
};

let cronTimer = null;

// Función para emitir logs vía WebSockets y guardar en memoria
function logEvent(channel, level, message, details = {}) {
  const logEntry = {
    id: Date.now() + Math.random().toString(36).substring(2, 7),
    timestamp: new Date().toISOString(),
    channel, // 'general' | 'direct' | 'space' | 'alerts'
    level,   // 'info' | 'success' | 'warn' | 'error'
    message,
    details
  };

  logHistory.push(logEntry);
  if (logHistory.length > MAX_LOG_HISTORY) {
    logHistory.shift();
  }

  // Transmitir a todos los clientes WebSocket
  const payload = JSON.stringify({ type: 'LOG', data: logEntry });
  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(payload);
    }
  });

  // Imprimir en consola de Node para depuración
  const levelSymbol = level === 'success' ? '✓' : level === 'error' ? '✗' : level === 'warn' ? '⚠' : 'ℹ';
  console.log(`[${logEntry.timestamp}] [${channel.toUpperCase()}] ${levelSymbol} ${message}`);
}

// Notificar actualización de estado global de espacios
function broadcastStateUpdate() {
  const payload = JSON.stringify({
    type: 'STATE_UPDATE',
    data: {
      spaces: spacesState,
      cronConfig: {
        ...cronConfig,
        nextRunSecondsLeft: cronConfig.nextRun ? Math.max(0, Math.round((cronConfig.nextRun - Date.now()) / 1000)) : 0
      },
      stats: computeStats()
    }
  });

  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(payload);
    }
  });
}

function computeStats() {
  const total = spacesState.length;
  let online = 0;
  let degraded = 0;
  let offline = 0;
  let totalLatency = 0;
  let latencyCount = 0;

  spacesState.forEach(s => {
    if (s.overallStatus === 'ONLINE') online++;
    else if (s.overallStatus === 'DEGRADED') degraded++;
    else if (s.overallStatus === 'OFFLINE') offline++;

    if (s.directStatus.latencyMs > 0) {
      totalLatency += s.directStatus.latencyMs;
      latencyCount++;
    }
  });

  const avgLatency = latencyCount > 0 ? Math.round(totalLatency / latencyCount) : 0;

  return {
    total,
    online,
    degraded,
    offline,
    avgLatency
  };
}

// Función HTTP ping con Timeout
async function pingUrl(url, timeoutMs = 12000) {
  const startTime = Date.now();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AntigravityCronBot/1.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
      },
      signal: controller.signal
    });

    clearTimeout(timeoutId);
    const latencyMs = Date.now() - startTime;
    return {
      ok: response.ok || (response.status >= 200 && response.status < 400),
      statusCode: response.status,
      statusText: response.statusText,
      latencyMs,
      error: response.ok ? null : `HTTP ${response.status} ${response.statusText}`
    };
  } catch (err) {
    clearTimeout(timeoutId);
    const latencyMs = Date.now() - startTime;
    let errMsg = err.message;
    if (err.name === 'AbortError') {
      errMsg = `Timeout superado (> ${timeoutMs / 1000}s)`;
    }
    return {
      ok: false,
      statusCode: 0,
      statusText: 'Error de Red / Timeout',
      latencyMs,
      error: errMsg
    };
  }
}

// Proceso completo de Diagnóstico para un espacio
async function diagnoseSpace(spaceIndex) {
  const space = spacesState[spaceIndex];
  const timeStr = new Date().toLocaleTimeString();

  logEvent('general', 'info', `Iniciando diagnóstico para [${space.name}]...`, { spaceId: space.id });

  // 1. Visitar App Directa (.hf.space)
  logEvent('direct', 'info', `Consultando App Directa: ${space.directUrl}`, { spaceId: space.id });
  const directResult = await pingUrl(space.directUrl);
  space.directStatus = {
    status: directResult.ok ? 'ONLINE' : 'OFFLINE',
    statusCode: directResult.statusCode,
    latencyMs: directResult.latencyMs,
    lastCheck: timeStr,
    error: directResult.error
  };

  if (directResult.ok) {
    logEvent('direct', 'success', `[App Directa] ${space.name} respondión OK en ${directResult.latencyMs} ms (HTTP ${directResult.statusCode})`, {
      spaceId: space.id,
      url: space.directUrl,
      latencyMs: directResult.latencyMs
    });
  } else {
    logEvent('direct', 'error', `[App Directa] Fallo en ${space.name}: ${directResult.error} (${directResult.latencyMs} ms)`, {
      spaceId: space.id,
      url: space.directUrl,
      error: directResult.error
    });
    logEvent('alerts', 'warn', `Alerta en App Directa de [${space.name}]: ${directResult.error}`, { spaceId: space.id });
  }

  // 2. Visitar Espacio de HF (huggingface.co/spaces/...)
  logEvent('space', 'info', `Consultando Espacio HF: ${space.spaceUrl}`, { spaceId: space.id });
  const spacePageResult = await pingUrl(space.spaceUrl);
  space.spaceStatus = {
    status: spacePageResult.ok ? 'ONLINE' : 'OFFLINE',
    statusCode: spacePageResult.statusCode,
    latencyMs: spacePageResult.latencyMs,
    lastCheck: timeStr,
    error: spacePageResult.error
  };

  if (spacePageResult.ok) {
    logEvent('space', 'success', `[Espacio HF] Landing de ${space.name} respondión OK en ${spacePageResult.latencyMs} ms (HTTP ${spacePageResult.statusCode})`, {
      spaceId: space.id,
      url: space.spaceUrl,
      latencyMs: spacePageResult.latencyMs
    });
  } else {
    logEvent('space', 'error', `[Espacio HF] Fallo en landing de ${space.name}: ${spacePageResult.error}`, {
      spaceId: space.id,
      url: space.spaceUrl,
      error: spacePageResult.error
    });
    logEvent('alerts', 'warn', `Alerta en Espacio HF de [${space.name}]: ${spacePageResult.error}`, { spaceId: space.id });
  }

  // Evaluar estado general
  if (directResult.ok && spacePageResult.ok) {
    space.overallStatus = 'ONLINE';
    logEvent('general', 'success', `Diagnóstico COMPLETADO [${space.name}]: ONLINE (Directo: ${directResult.latencyMs}ms | HF: ${spacePageResult.latencyMs}ms)`);
  } else if (directResult.ok || spacePageResult.ok) {
    space.overallStatus = 'DEGRADED';
    logEvent('general', 'warn', `Diagnóstico PARCIAL [${space.name}]: DEGRADADO (Directo: ${space.directStatus.status} | HF: ${space.spaceStatus.status})`);
    logEvent('alerts', 'warn', `Espacio [${space.name}] está en estado DEGRADADO`, { spaceId: space.id });
  } else {
    space.overallStatus = 'OFFLINE';
    logEvent('general', 'error', `Diagnóstico FALLIDO [${space.name}]: OFFLINE`);
    logEvent('alerts', 'error', `CRÍTICO: Espacio [${space.name}] se encuentra OFFLINE`, { spaceId: space.id });
  }

  broadcastStateUpdate();
}

// Ejecutar ciclo completo sobre los 19 espacios
async function runFullCronCycle(isManual = false) {
  if (cronConfig.isRunningCycle) {
    logEvent('general', 'warn', 'Un ciclo de diagnósticos ya se encuentra en ejecución.');
    return;
  }

  cronConfig.isRunningCycle = true;
  cronConfig.lastRun = new Date().toISOString();
  cronConfig.nextRun = Date.now() + cronConfig.intervalSeconds * 1000;

  const triggerType = isManual ? 'MANUAL' : 'CRONOLÓGICO PROGRAMADO';
  logEvent('general', 'info', `=== INICIANDO CICLO DE DIAGNÓSTICO (${triggerType}) DE ${spacesState.length} ESPACIOS ===`);

  for (let i = 0; i < spacesState.length; i++) {
    await diagnoseSpace(i);
    // Pequeño delay de 250ms entre diagnósticos para no saturar conexiones
    await new Promise(r => setTimeout(r, 250));
  }

  logEvent('general', 'success', `=== CICLO DE DIAGNÓSTICO FINALIZADO CON ÉXITO ===`);
  cronConfig.isRunningCycle = false;
  broadcastStateUpdate();
}

// Programador Cron en segundo plano
function startCronScheduler() {
  if (cronTimer) clearInterval(cronTimer);

  cronConfig.nextRun = Date.now() + cronConfig.intervalSeconds * 1000;

  cronTimer = setInterval(() => {
    if (cronConfig.enabled && !cronConfig.isRunningCycle) {
      runFullCronCycle(false);
    }
  }, cronConfig.intervalSeconds * 1000);
}

// WebSocket connection handler
wss.on('connection', (ws) => {
  logEvent('general', 'info', 'Nuevo cliente conectado al panel de diagnóstico en vivo.');

  // Enviar estado inicial y logs previos
  ws.send(JSON.stringify({
    type: 'INIT',
    data: {
      spaces: spacesState,
      cronConfig: {
        ...cronConfig,
        nextRunSecondsLeft: cronConfig.nextRun ? Math.max(0, Math.round((cronConfig.nextRun - Date.now()) / 1000)) : 0
      },
      stats: computeStats(),
      logs: logHistory
    }
  }));
});

// Middleware Express
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Endpoints REST
app.get('/api/spaces', (req, res) => {
  res.json({
    spaces: spacesState,
    stats: computeStats(),
    cronConfig
  });
});

app.get('/api/logs', (req, res) => {
  const channel = req.query.channel;
  if (channel) {
    return res.json(logHistory.filter(l => l.channel === channel || l.channel === 'general'));
  }
  res.json(logHistory);
});

app.post('/api/ping-all', (req, res) => {
  runFullCronCycle(true);
  res.json({ message: 'Ciclo de diagnóstico manual iniciado.' });
});

app.post('/api/ping-space/:id', async (req, res) => {
  const index = spacesState.findIndex(s => s.id === req.params.id);
  if (index === -1) {
    return res.status(404).json({ error: 'Espacio no encontrado' });
  }

  diagnoseSpace(index);
  res.json({ message: `Diagnóstico para ${spacesState[index].name} iniciado.` });
});

app.post('/api/config', (req, res) => {
  const { intervalSeconds, enabled } = req.body;
  if (typeof intervalSeconds === 'number' && intervalSeconds >= 30) {
    cronConfig.intervalSeconds = intervalSeconds;
  }
  if (typeof enabled === 'boolean') {
    cronConfig.enabled = enabled;
  }

  startCronScheduler();
  broadcastStateUpdate();

  logEvent('general', 'info', `Configuración actualizada: Intervalo ${cronConfig.intervalSeconds}s | Auto-Cron: ${cronConfig.enabled ? 'Activado' : 'Pausado'}`);
  res.json({ cronConfig });
});

// Iniciar servidor y ejecutar primer ciclo de diagnóstico tras 2 segundos
server.listen(PORT, () => {
  console.log(`\n======================================================`);
  console.log(`🤖 Bot Cronológico & Dashboard de Diagnósticos`);
  console.log(`🌐 Servidor iniciado en http://localhost:${PORT}`);
  console.log(`======================================================\n`);

  startCronScheduler();

  // Primer ciclo automático de diagnóstico
  setTimeout(() => {
    runFullCronCycle(false);
  }, 2000);
});
