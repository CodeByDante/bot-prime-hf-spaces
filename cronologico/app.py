import os
import json
import time
import asyncio
import aiohttp
import gradio as gr
from datetime import datetime

# Cargar la lista de los 19 espacios
SPACES_FILE = os.path.join(os.path.dirname(__file__), "spaces.json")
with open(SPACES_FILE, "r", encoding="utf-8") as f:
    SPACES_DATA = json.load(f)

# Estado global de diagnósticos
spaces_state = []
for item in SPACES_DATA:
    spaces_state.append({
        "id": item["id"],
        "name": item["name"],
        "directUrl": item["directUrl"],
        "spaceUrl": item["spaceUrl"],
        "user": item["user"],
        "repo": item["repo"],
        "direct_status": "PENDIENTE",
        "direct_latency": "--",
        "space_status": "PENDIENTE",
        "space_latency": "--",
        "overall_status": "DESCONOCIDO",
        "last_check": "--"
    })

logs_history = {
    "general": [],
    "direct": [],
    "space": [],
    "alerts": []
}

def add_log(channel, level, msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] [{channel.upper()}] [{level.upper()}] {msg}"
    
    logs_history["general"].append(entry)
    if len(logs_history["general"]) > 300:
        logs_history["general"].pop(0)

    if channel in logs_history:
        logs_history[channel].append(entry)
        if len(logs_history[channel]) > 300:
            logs_history[channel].pop(0)

    if level in ["WARN", "ERROR"] and channel != "alerts":
        logs_history["alerts"].append(entry)
        if len(logs_history["alerts"]) > 300:
            logs_history["alerts"].pop(0)

async def ping_url(session, url, timeout_sec=12):
    start = time.time()
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_sec), headers={"User-Agent": "HF-Gradio-Pinger/1.0"}) as resp:
            latency_ms = int((time.time() - start) * 1000)
            ok = resp.status < 400
            return ok, resp.status, latency_ms, None
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        return False, 0, latency_ms, str(e)

async def run_diagnostics_cycle():
    add_log("general", "INFO", "=== INICIANDO CICLO DE DIAGNÓSTICO EN HUGGING FACE SPACES ===")
    async with aiohttp.ClientSession() as session:
        for space in spaces_state:
            # 1. Direct App Ping (.hf.space)
            add_log("direct", "INFO", f"Visitando App Directa: {space['directUrl']}")
            d_ok, d_code, d_lat, d_err = await ping_url(session, space['directUrl'])
            space['direct_latency'] = f"{d_lat} ms"
            if d_ok:
                space['direct_status'] = "ONLINE"
                add_log("direct", "SUCCESS", f"[Directo OK] {space['name']} -> {d_lat}ms (HTTP {d_code})")
            else:
                space['direct_status'] = "OFFLINE"
                add_log("direct", "ERROR", f"[Directo FALLO] {space['name']} -> {d_err or d_code}")

            # 2. HF Space Landing Ping (huggingface.co/spaces/...)
            add_log("space", "INFO", f"Visitando Landing Espacio: {space['spaceUrl']}")
            s_ok, s_code, s_lat, s_err = await ping_url(session, space['spaceUrl'])
            space['space_latency'] = f"{s_lat} ms"
            if s_ok:
                space['space_status'] = "ONLINE"
                add_log("space", "SUCCESS", f"[Landing OK] {space['name']} -> {s_lat}ms (HTTP {s_code})")
            else:
                space['space_status'] = "OFFLINE"
                add_log("space", "ERROR", f"[Landing FALLO] {space['name']} -> {s_err or s_code}")

            # Evaluar Estado General
            space['last_check'] = datetime.now().strftime("%H:%M:%S")
            if d_ok and s_ok:
                space['overall_status'] = "ONLINE"
                add_log("general", "SUCCESS", f"Diagnóstico OK: {space['name']} (Directo: {d_lat}ms | Landing: {s_lat}ms)")
            elif d_ok or s_ok:
                space['overall_status'] = "DEGRADADO"
                add_log("general", "WARN", f"Diagnóstico PARCIAL: {space['name']} (DEGRADADO)")
            else:
                space['overall_status'] = "OFFLINE"
                add_log("general", "ERROR", f"Diagnóstico CRÍTICO: {space['name']} (OFFLINE)")

            await asyncio.sleep(0.2)

    add_log("general", "SUCCESS", "=== CICLO DE DIAGNÓSTICO COMPLETADO ===")

def manual_ping_trigger():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_diagnostics_cycle())
    return get_logs("general"), get_logs("direct"), get_logs("space"), get_logs("alerts"), render_table()

def get_logs(channel):
    return "\n".join(logs_history.get(channel, []))

def render_table():
    headers = ["Bot / Espacio", "Estado Global", "App Directa (.hf.space)", "Landing Espacio HF", "Última Revisión"]
    rows = []
    for s in spaces_state:
        status_symbol = "🟢 ONLINE" if s['overall_status'] == "ONLINE" else "🟡 DEGRADADO" if s['overall_status'] == "DEGRADADO" else "🔴 OFFLINE"
        rows.append([
            f"{s['name']}\n(@{s['user']})",
            status_symbol,
            f"{s['direct_status']} ({s['direct_latency']})",
            f"{s['space_status']} ({s['space_latency']})",
            s['last_check']
        ])
    return rows

# Gradio Interface Building
custom_css = """
.gradio-container { background-color: #0b0f19 !important; color: #f8fafc !important; }
h1 { color: #00f2fe !important; text-shadow: 0 0 10px rgba(0,242,254,0.3); }
.tab-nav button { font-weight: bold !important; font-size: 1rem !important; }
textarea { font-family: 'Fira Code', monospace !important; background-color: #050811 !important; color: #38bdf8 !important; }
"""

with gr.Blocks(title="Bot Cronológico HF Spaces", css=custom_css) as demo:
    gr.Markdown(
        """
        # 🤖 Bot Cronológico - Monitoreo & Diagnósticos HF Spaces
        ### Visita periódica y diagnóstico de salud para 19 Espacios de Hugging Face
        *Visita tanto la App Directa (`.hf.space`) como la Landing Page del Espacio (`huggingface.co/spaces/...`)*
        """
    )

    with gr.Row():
        btn_run = gr.Button("⚡ Ejecutar Diagnóstico Manual Ahora", variant="primary")

    with gr.Row():
        status_table = gr.Dataframe(
            headers=["Bot / Espacio", "Estado Global", "App Directa (.hf.space)", "Landing Espacio HF", "Última Revisión"],
            value=render_table(),
            interactive=False
        )

    gr.Markdown("### 🖥️ Consolas de Diagnósticos Múltiples")
    with gr.Tabs():
        with gr.TabItem("🖥️ Consola General"):
            log_gen = gr.TextArea(label="Logs de Diagnóstico General", value=get_logs("general"), lines=14, interactive=False)
        with gr.TabItem("⚡ Consola App Directa (.hf.space)"):
            log_dir = gr.TextArea(label="Logs de Respuestas Backend Directas", value=get_logs("direct"), lines=14, interactive=False)
        with gr.TabItem("🚀 Consola Espacio HF (Landing)"):
            log_spc = gr.TextArea(label="Logs de Páginas de Espacios HF", value=get_logs("space"), lines=14, interactive=False)
        with gr.TabItem("⚠️ Consola de Alertas & Errores"):
            log_alt = gr.TextArea(label="Alertas, Errores y Degradaciones", value=get_logs("alerts"), lines=14, interactive=False)

    btn_run.click(
        fn=manual_ping_trigger,
        inputs=[],
        outputs=[log_gen, log_dir, log_spc, log_alt, status_table]
    )

    demo.load(
        fn=manual_ping_trigger,
        inputs=[],
        outputs=[log_gen, log_dir, log_spc, log_alt, status_table]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
