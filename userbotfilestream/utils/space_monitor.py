import os
import sys
import time
import json
import socket
import ssl
import asyncio
import aiohttp
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOGS_DIR = os.path.join(BASE_DIR, "logs", "diagnostics")
STATE_PATH = os.path.join(BASE_DIR, "logs", "monitor_state.json")

os.makedirs(LOGS_DIR, exist_ok=True)

class SpaceMonitor:
    def __init__(self):
        self.telegram_client = None
        self.monitored_spaces = []
        self.check_interval = 180  # segundos (3 min por defecto)
        self.history = {}  # { url: { "status": ..., "last_check": ..., "latency_ms": ..., "history": [...] } }
        self.previous_states = {}  # { url: status_code_string }
        self.load_config()
        self.load_state()

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.monitored_spaces = cfg.get("monitored_spaces", [
                        "https://huggingface.co/spaces/danteloyolasalvador/userbotFileStream"
                    ])
                    self.check_interval = int(cfg.get("check_interval_seconds", 180))
            except Exception as e:
                print(f"[SpaceMonitor] Error al cargar config.json: {e}")

    def load_state(self):
        if os.path.exists(STATE_PATH):
            try:
                with open(STATE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.history = data.get("history", {})
                    self.previous_states = data.get("previous_states", {})
            except Exception as e:
                print(f"[SpaceMonitor] Error al cargar monitor_state.json: {e}")

    def save_state(self):
        try:
            with open(STATE_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "history": self.history,
                    "previous_states": self.previous_states,
                    "last_update": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[SpaceMonitor] Error al guardar monitor_state.json: {e}")

    def set_telegram_client(self, client):
        self.telegram_client = client
        print("[SpaceMonitor] Cliente de Telegram vinculado exitosamente.")

    def parse_hf_url(self, url: str):
        """ Extrae owner y repo_name de una URL de Hugging Face """
        match = re.search(r"huggingface\.co/spaces/([^/]+)/([^/]+)", url)
        if match:
            return match.group(1), match.group(2)
        # O si se ingresó directamente la URL directa app: https://owner-repo.hf.space
        match_direct = re.search(r"https://([^-]+)-([^.]+)\.hf\.space", url)
        if match_direct:
            return match_direct.group(1), match_direct.group(2)
        return None, None

    async def check_dns(self, hostname: str):
        """ Comprobación DNS """
        try:
            loop = asyncio.get_running_loop()
            res = await loop.getaddrinfo(hostname, 80, family=socket.AF_INET)
            ip = res[0][4][0] if res else None
            return True, ip, "DNS Correcto"
        except Exception as e:
            return False, None, f"Error DNS: {e}"

    async def check_ssl(self, hostname: str):
        """ Comprobación SSL """
        try:
            ctx = ssl.create_default_context()
            conn = asyncio.open_connection(hostname, 443, ssl=ctx)
            reader, writer = await asyncio.wait_for(conn, timeout=10)
            writer.close()
            await writer.wait_closed()
            return True, "SSL Certificado Válido"
        except Exception as e:
            return False, f"Error SSL: {e}"

    async def check_hf_api(self, owner: str, space_name: str):
        """ Consulta la API de Hugging Face para obtener el runtime status real """
        api_url = f"https://huggingface.co/api/spaces/{owner}/{space_name}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        runtime = data.get("runtime", {})
                        stage = runtime.get("stage", "UNKNOWN")
                        hardware = runtime.get("hardware", {}).get("current", "cpu-basic")
                        gc_status = runtime.get("gcStatus", "unknown")
                        raw_error = runtime.get("rawError", None)
                        return {
                            "stage": stage,
                            "hardware": hardware,
                            "gc_status": gc_status,
                            "raw_error": raw_error
                        }
        except Exception as e:
            print(f"[SpaceMonitor] Error al consultar API de HF: {e}")
        return None

    async def check_http(self, target_url: str):
        """ Realiza la petición HTTP y mide el tiempo de respuesta """
        start_time = time.time()
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SpaceMonitor/1.0'}
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(target_url, headers=headers) as resp:
                    latency = round((time.time() - start_time) * 1000, 2)
                    text = await resp.text()
                    is_hf_sleeping = "space is sleeping" in text.lower() or resp.status == 503
                    return {
                        "ok": resp.status == 200,
                        "status_code": resp.status,
                        "latency_ms": latency,
                        "headers": dict(resp.headers),
                        "is_sleeping": is_hf_sleeping,
                        "error": None
                    }
        except asyncio.TimeoutError:
            latency = round((time.time() - start_time) * 1000, 2)
            return {
                "ok": False,
                "status_code": 408,
                "latency_ms": latency,
                "headers": {},
                "is_sleeping": False,
                "error": "Timeout (Excedido límite de 15s)"
            }
        except Exception as e:
            latency = round((time.time() - start_time) * 1000, 2)
            return {
                "ok": False,
                "status_code": 0,
                "latency_ms": latency,
                "headers": {},
                "is_sleeping": False,
                "error": str(e)
            }

    async def diagnose_space(self, url: str):
        """ Diagnóstico completo de una Space """
        owner, space_name = self.parse_hf_url(url)
        direct_url = f"https://{owner}-{space_name}.hf.space" if owner and space_name else url
        hostname = f"{owner}-{space_name}.hf.space" if owner and space_name else url.split("//")[-1].split("/")[0]

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Prueba DNS
        dns_ok, ip, dns_msg = await self.check_dns(hostname)

        # 2. Prueba SSL
        ssl_ok, ssl_msg = await self.check_ssl(hostname) if dns_ok else (False, "N/A por fallo DNS")

        # 3. Consulta API de Hugging Face
        hf_api_info = await self.check_hf_api(owner, space_name) if owner and space_name else None

        # 4. Prueba HTTP en la app directa
        http_info = await self.check_http(direct_url)

        # Clasificación de Estado
        category = "🟢 Funcionando"
        code = "RUNNING"
        details = "Espacio respondiendo correctamente y sin errores."

        stage = hf_api_info.get("stage") if hf_api_info else None

        if not dns_ok:
            category = "🔴 DNS Error"
            code = "DNS_FAILURE"
            details = f"Fallo al resolver el dominio {hostname}. Detalle: {dns_msg}"
        elif not ssl_ok and "N/A" not in ssl_msg:
            category = "🔴 SSL Error"
            code = "SSL_FAILURE"
            details = f"Problema con el certificado SSL/HTTPS. Detalle: {ssl_msg}"
        elif stage == "PAUSED" or http_info["is_sleeping"]:
            category = "🟡 Sleeping"
            code = "SLEEPING"
            details = "El Space fue pausado por inactividad de 48h de Hugging Face. Requiere petición HTTP para despertar."
        elif stage == "BUILD_ERROR":
            category = "🔴 Build Failed"
            code = "BUILD_ERROR"
            details = f"Fallo al construir la imagen Docker en Hugging Face. Raw Error: {hf_api_info.get('raw_error')}"
        elif stage == "RUNTIME_ERROR" or http_info["status_code"] == 500:
            category = "🔴 Runtime Error"
            code = "RUNTIME_ERROR"
            details = f"Error de ejecución interna (Crash / OOM Killer / Excepción no capturada en Python). Status: {http_info['status_code']}"
        elif http_info["status_code"] == 503:
            category = "🔴 503 Service Unavailable"
            code = "503_SERVICE_UNAVAILABLE"
            details = "Servidor no disponible. Posible reinicio de la instancia o sobrecarga."
        elif http_info["error"] and "Timeout" in http_info["error"]:
            category = "🔴 Timeout"
            code = "TIMEOUT"
            details = "El servidor tardó más de 15 segundos en responder."
        elif not http_info["ok"]:
            category = f"🔴 Error {http_info['status_code']}"
            code = f"HTTP_{http_info['status_code']}"
            details = f"Fallo de respuesta HTTP. Error: {http_info['error']}"

        result = {
            "target_url": url,
            "direct_url": direct_url,
            "timestamp": timestamp,
            "category": category,
            "code": code,
            "details": details,
            "latency_ms": http_info["latency_ms"],
            "dns": {"ok": dns_ok, "ip": ip, "message": dns_msg},
            "ssl": {"ok": ssl_ok, "message": ssl_msg},
            "hf_api": hf_api_info,
            "http": http_info
        }

        # Guardar en historial
        if url not in self.history:
            self.history[url] = {"current": result, "logs": []}
        
        self.history[url]["current"] = result
        self.history[url]["logs"].append({
            "timestamp": timestamp,
            "category": category,
            "latency_ms": http_info["latency_ms"],
            "code": code
        })
        # Mantener últimos 100 registros por URL
        if len(self.history[url]["logs"]) > 100:
            self.history[url]["logs"] = self.history[url]["logs"][-100:]

        return result

    def generate_txt_report(self, diag: dict) -> str:
        """ Genera el contenido formateado del archivo TXT de diagnóstico """
        space_name = diag['target_url'].split('/')[-1]
        now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"diagnostico_{space_name}_{now_str}.txt"
        file_path = os.path.join(LOGS_DIR, filename)

        content = f"""================================================================================
                    DIAGNÓSTICO TÉCNICO DE SPACE
================================================================================
Fecha y Hora      : {diag['timestamp']}
Target URL        : {diag['target_url']}
Direct App URL    : {diag['direct_url']}
Estado Diagnóstico: {diag['category']} ({diag['code']})
Latencia          : {diag['latency_ms']} ms
================================================================================

[1] RESUMEN Y CAUSA PROBABLE:
--------------------------------------------------------------------------------
{diag['details']}

[2] PRUEBA DE RED Y DNS:
--------------------------------------------------------------------------------
DNS Resuelto      : {"SÍ" if diag['dns']['ok'] else "NO"}
IP Servidor       : {diag['dns']['ip'] or "N/A"}
Detalle DNS       : {diag['dns']['message']}

[3] SEGURIDAD SSL:
--------------------------------------------------------------------------------
Estado SSL        : {diag['ssl']['message']}

[4] INFORMACIÓN DE HUGGING FACE API:
--------------------------------------------------------------------------------
Stage HF          : {diag['hf_api']['stage'] if diag['hf_api'] else 'N/A'}
Hardware          : {diag['hf_api']['hardware'] if diag['hf_api'] else 'N/A'}
Estado GC         : {diag['hf_api']['gc_status'] if diag['hf_api'] else 'N/A'}
Raw Error HF      : {diag['hf_api']['raw_error'] if diag['hf_api'] else 'Ninguno registrado'}

[5] RESPUESTA HTTP EN DIRECTO:
--------------------------------------------------------------------------------
Código HTTP       : {diag['http']['status_code']}
Timeout / Error   : {diag['http']['error'] or "Sin errores de red"}
Es Sleeping       : {"SÍ" if diag['http']['is_sleeping'] else "NO"}

================================================================================
Generado automáticamente por SpaceMonitor - Brody Prime UserBot
================================================================================
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return file_path, filename

    async def notify_telegram(self, diag: dict, is_transition: bool, previous_cat: str):
        """ Envía mensaje de alerta y el archivo .txt de diagnóstico a Mensajes Guardados ('me') """
        if not self.telegram_client:
            print("[SpaceMonitor Warning] No hay cliente de Telegram vinculado. Omitiendo alerta.")
            return

        txt_path, txt_filename = self.generate_txt_report(diag)
        space_name = diag['target_url'].split('/')[-1]

        if "🟢" in diag['category']:
            header = "✅ **[RECURSOS Y ESPACIO RECUPERADO]**"
            color_emoji = "🟢"
        elif "🟡" in diag['category']:
            header = "🟡 **[SPACE SUSPENDIDO / SLEEPING]**"
            color_emoji = "🟡"
        else:
            header = "🚨 **[ALERTA DE CAÍDA DE SPACE]**"
            color_emoji = "🔴"

        alert_msg = (
            f"{header}\n\n"
            f"🌐 **Space:** `{space_name}`\n"
            f"🔗 **URL:** {diag['target_url']}\n"
            f"📊 **Estado:** {diag['category']}\n"
            f"⏱️ **Latencia:** `{diag['latency_ms']} ms`\n"
            f"📅 **Hora:** `{diag['timestamp']}`\n\n"
            f"📝 **Diagnóstico:**\n_{diag['details']}_\n\n"
            f"📄 *Adjunto encontrarás el informe técnico detallado en formato .txt.*"
        )

        try:
            # 1. Enviar mensaje de texto a Mensajes Guardados ("me")
            await self.telegram_client.send_message("me", alert_msg)
            # 2. Enviar el archivo .txt de diagnóstico a Mensajes Guardados ("me")
            await self.telegram_client.send_file(
                "me",
                txt_path,
                caption=f"📄 Registro de Diagnóstico Técnico: `{txt_filename}`"
            )
            print(f"[SpaceMonitor OK] Alerta y archivo {txt_filename} enviados a Mensajes Guardados ('me').")
        except Exception as e:
            print(f"[SpaceMonitor Error] No se pudo enviar mensaje/archivo por Telegram: {e}")

    async def run_check_cycle(self):
        """ Ejecuta un ciclo de verificación completo para todas las Spaces configuradas """
        print(f"[SpaceMonitor] Ejecutando ciclo de verificación a las {datetime.now().strftime('%H:%M:%S')}...")
        self.load_config()

        for url in self.monitored_spaces:
            diag = await self.diagnose_space(url)
            prev_cat = self.previous_states.get(url)
            curr_cat = diag["category"]

            try:
                print(f"[SpaceMonitor] {url} -> {curr_cat} ({diag['latency_ms']} ms)")
            except UnicodeEncodeError:
                safe_cat = curr_cat.encode('ascii', errors='replace').decode('ascii')
                print(f"[SpaceMonitor] {url} -> {safe_cat} ({diag['latency_ms']} ms)")

            # Se ha deshabilitado el envío de notificaciones a Telegram por petición del usuario
            # is_transition = (prev_cat is not None and prev_cat != curr_cat)
            # is_critical_failure = "🔴" in curr_cat or "🟡" in curr_cat
            #
            # if is_transition or (prev_cat is None and is_critical_failure):
            #     await self.notify_telegram(diag, is_transition, prev_cat)

            self.previous_states[url] = curr_cat

        self.save_state()

    async def start_monitoring(self):
        """ Inicia el bucle periódico de monitoreo en segundo plano """
        print(f"[SpaceMonitor] Iniciando monitoreo autónomo cada {self.check_interval} segundos...")
        while True:
            try:
                await self.run_check_cycle()
            except Exception as e:
                print(f"[SpaceMonitor Error] Excepción en ciclo de monitoreo: {e}")
            await asyncio.sleep(self.check_interval)

# Instancia global del monitor
space_monitor = SpaceMonitor()
