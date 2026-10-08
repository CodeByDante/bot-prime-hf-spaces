import os
import asyncio
import json
import subprocess
import aiohttp

# Silenciar logs molestos de FFmpeg y OpenCV en la consola
os.environ["AV_LOG_LEVEL"] = "quiet"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"

from aiohttp import web
import bot_prime
from utils.database import DB
from utils.space_monitor import space_monitor
from handlers.descargar import download_batches
from telethon.tl.types import InputDocumentFileLocation
from telethon.tl.functions.upload import GetFileRequest
from telethon.errors import FloodWaitError

async def handle_home(request):
    print("[Servidor Web] Petición recibida en '/' (Health check de Hugging Face)")
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>twisted brody prime user bot Status</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-gradient: linear-gradient(135deg, #0f0c1b 0%, #1a103c 50%, #05020a 100%);
                --card-bg: rgba(255, 255, 255, 0.03);
                --card-border: rgba(255, 255, 255, 0.08);
                --text-primary: #ffffff;
                --text-secondary: #a0aec0;
                --accent: #d53f8c;
                --accent-glow: rgba(213, 63, 140, 0.4);
                --success: #38a169;
                --success-glow: rgba(56, 161, 105, 0.4);
            }
            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }
            body {
                font-family: 'Outfit', sans-serif;
                background: var(--bg-gradient);
                color: var(--text-primary);
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                overflow-x: hidden;
            }
            .container {
                width: 90%;
                max-width: 600px;
                padding: 40px;
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 24px;
                backdrop-filter: blur(20px);
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
                text-align: center;
                position: relative;
            }
            .container::before {
                content: '';
                position: absolute;
                top: -2px;
                left: -2px;
                right: -2px;
                bottom: -2px;
                background: linear-gradient(45deg, var(--accent), #6b46c1, #319795);
                border-radius: 26px;
                z-index: -1;
                opacity: 0.15;
            }
            h1 {
                font-size: 2.5rem;
                font-weight: 800;
                margin-bottom: 10px;
                background: linear-gradient(to right, #f687b3, #b7791f, #319795);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .status-badge {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 8px 16px;
                background: rgba(56, 161, 105, 0.1);
                border: 1px solid var(--success);
                color: #48bb78;
                border-radius: 9999px;
                font-weight: 600;
                font-size: 0.9rem;
                margin-top: 15px;
                margin-bottom: 30px;
                box-shadow: 0 0 15px var(--success-glow);
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0% { box-shadow: 0 0 5px var(--success-glow); }
                50% { box-shadow: 0 0 20px var(--success-glow); }
                100% { box-shadow: 0 0 5px var(--success-glow); }
            }
            p.description {
                color: var(--text-secondary);
                font-size: 1.1rem;
                line-height: 1.6;
                margin-bottom: 30px;
            }
            .commands-card {
                background: rgba(0, 0, 0, 0.2);
                border: 1px solid var(--card-border);
                border-radius: 16px;
                padding: 20px;
                text-align: left;
            }
            .commands-card h3 {
                font-size: 1.2rem;
                margin-bottom: 15px;
                color: #f687b3;
            }
            ul {
                list-style: none;
            }
            li {
                margin-bottom: 10px;
                font-size: 0.95rem;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            li code {
                background: rgba(255, 255, 255, 0.08);
                padding: 3px 8px;
                border-radius: 6px;
                color: #e2e8f0;
                font-family: monospace;
                font-size: 0.9rem;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            li span {
                color: var(--text-secondary);
            }
            footer {
                margin-top: 30px;
                font-size: 0.8rem;
                color: #718096;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>twisted brody prime user bot</h1>
            <div class="status-badge">
                <span style="width: 8px; height: 8px; background: #38a169; border-radius: 50%;"></span>
                Online & Activo
            </div>
            <p class="description">
                Tu bot de Telegram está ejecutándose en segundo plano en Hugging Face Spaces y escuchando comandos en tus canales.
            </p>
            <div class="commands-card">
                <h3>Comandos del Bot:</h3>
                <ul>
                    <li><code>/capturas</code> o <code>/capture</code> <span>- Generar capturas y reordenar</span></li>
                    <li><code>/sinopsis</code> <span>- Buscar y agregar sinopsis/hashtags</span></li>
                    <li><code>/lista</code> <span>- Lista rápida auto-limpiable</span></li>
                    <li><code>/ping</code> <span>- Comprobar estado de actividad</span></li>
                    <li><code>/menu</code> <span>- Panel de ayuda</span></li>
                </ul>
            </div>
            <footer>
                Powered by codebydante & Antigravity AI
            </footer>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type="text/html")

async def handle_download_batch(request):
    batch_id = request.match_info.get("batch_id")
    batch = download_batches.get(batch_id)
    if not batch:
        error_html = """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Lote no encontrado</title>
            <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
            <style>
                body {
                    font-family: 'Outfit', sans-serif;
                    background: #0b0819;
                    color: #ffffff;
                    height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0;
                }
                .card {
                    background: rgba(255, 255, 255, 0.03);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    padding: 40px;
                    border-radius: 24px;
                    text-align: center;
                    backdrop-filter: blur(10px);
                    box-shadow: 0 20px 40px rgba(0,0,0,0.5);
                }
                h1 { color: #f687b3; margin-bottom: 10px; }
                p { color: #a0aec0; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Lote Inexistente o Expirado ❌</h1>
                <p>El enlace de descarga que has utilizado no existe o ya ha expirado.</p>
            </div>
        </body>
        </html>
        """
        return web.Response(text=error_html, content_type="text/html")
        
    chat_id = batch["chat_id"]
    files = batch["files"]
    media_type = batch["type"]
    
    def fmt_size(sz):
        if sz >= 1024 * 1024 * 1024:
            return f"{sz / (1024*1024*1024):.2f} GB"
        if sz >= 1024 * 1024:
            return f"{sz / (1024*1024):.2f} MB"
        if sz >= 1024:
            return f"{sz / 1024:.2f} KB"
        return f"{sz} B"
        
    files_list_html = ""
    for idx, f in enumerate(files, 1):
        files_list_html += f"""
        <tr>
            <td>{idx}</td>
            <td>{f['name']}</td>
            <td>{fmt_size(f['size'])}</td>
            <td>
                <a class="action-btn" href="/download_file/{chat_id}/{f['id']}" download="{f['name']}">Descargar</a>
            </td>
        </tr>
        """
        
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Descargar Lote - Bot Prime</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-gradient: linear-gradient(135deg, #0d0a1b 0%, #150f2e 50%, #05030a 100%);
                --card-bg: rgba(255, 255, 255, 0.02);
                --card-border: rgba(255, 255, 255, 0.08);
                --accent: #805ad5;
                --accent-hover: #9f7aea;
                --text-primary: #ffffff;
                --text-secondary: #a0aec0;
            }}
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}
            body {{
                font-family: 'Outfit', sans-serif;
                background: var(--bg-gradient);
                color: var(--text-primary);
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 40px 20px;
            }}
            .container {{
                width: 100%;
                max-width: 800px;
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 24px;
                backdrop-filter: blur(20px);
                box-shadow: 0 30px 60px rgba(0, 0, 0, 0.4);
                padding: 40px;
                position: relative;
            }}
            h1 {{
                font-size: 2.2rem;
                font-weight: 800;
                margin-bottom: 10px;
                background: linear-gradient(to right, #d53f8c, #805ad5);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            p.subtitle {{
                color: var(--text-secondary);
                margin-bottom: 30px;
                font-size: 1.1rem;
            }}
            .btn-group {{
                display: flex;
                gap: 15px;
                margin-bottom: 30px;
            }}
            .btn {{
                flex: 1;
                padding: 14px 20px;
                border: none;
                border-radius: 12px;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }}
            .btn-primary {{
                background: var(--accent);
                color: #ffffff;
                box-shadow: 0 0 15px rgba(128, 90, 213, 0.4);
            }}
            .btn-primary:hover {{
                background: var(--accent-hover);
                transform: translateY(-2px);
            }}
            .btn-secondary {{
                background: rgba(255, 255, 255, 0.08);
                color: #ffffff;
                border: 1px solid var(--card-border);
            }}
            .btn-secondary:hover {{
                background: rgba(255, 255, 255, 0.15);
                transform: translateY(-2px);
            }}
            .filter-box {{
                margin-bottom: 20px;
                width: 100%;
            }}
            .filter-input {{
                width: 100%;
                padding: 12px 20px;
                background: rgba(0, 0, 0, 0.2);
                border: 1px solid var(--card-border);
                border-radius: 10px;
                color: #ffffff;
                font-family: inherit;
                font-size: 1rem;
            }}
            .filter-input:focus {{
                border-color: var(--accent);
                outline: none;
            }}
            .table-container {{
                overflow-x: auto;
                max-height: 400px;
                border-radius: 12px;
                border: 1px solid var(--card-border);
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                text-align: left;
                font-size: 0.95rem;
            }}
            th, td {{
                padding: 14px 16px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }}
            th {{
                background: rgba(0, 0, 0, 0.3);
                font-weight: 600;
                color: #e2e8f0;
                position: sticky;
                top: 0;
            }}
            tr:hover td {{
                background: rgba(255, 255, 255, 0.02);
            }}
            .action-btn {{
                background: rgba(128, 90, 213, 0.15);
                border: 1px solid var(--accent);
                color: #b794f4;
                padding: 6px 12px;
                border-radius: 6px;
                text-decoration: none;
                font-size: 0.85rem;
                font-weight: 600;
                transition: all 0.2s ease;
                display: inline-block;
            }}
            .action-btn:hover {{
                background: var(--accent);
                color: #ffffff;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Descargar Lote de Archivos 📦</h1>
            <p class="subtitle">Se han encontrado {len(files)} {'videos' if media_type == 'video' else 'imágenes'} listos para descargar.</p>
            
            <div class="btn-group">
                <button id="download-btn" class="btn btn-primary" onclick="downloadAll()">Descargar Todos</button>
                <button class="btn btn-secondary" onclick="copyLinks()">Copiar Enlaces de Descarga</button>
            </div>
            
            <div class="filter-box">
                <input id="filter-input" type="text" class="filter-input" placeholder="Buscar por nombre..." oninput="filterFiles()">
            </div>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 50px;">#</th>
                            <th>Nombre del Archivo</th>
                            <th style="width: 120px;">Tamaño</th>
                            <th style="width: 100px;">Acción</th>
                        </tr>
                    </thead>
                    <tbody id="files-body">
                        {files_list_html}
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            const files = {json.dumps(files, ensure_ascii=False)};
            const chat_id = "{chat_id}";
            
            function copyLinks() {{
                const links = files.map(f => `${{window.location.origin}}/download_file/${{chat_id}}/${{f.id}}`).join('\\n');
                navigator.clipboard.writeText(links).then(() => {{
                    alert('¡Todos los enlaces de descarga directa se han copiado al portapapeles!');
                }}).catch(err => {{
                    alert('Error al copiar enlaces: ' + err);
                }});
            }}

            async function downloadAll() {{
                const btn = document.getElementById('download-btn');
                btn.disabled = true;
                btn.innerText = 'Descargando lote...';
                
                for (let i = 0; i < files.length; i++) {{
                    const f = files[i];
                    const url = `${{window.location.origin}}/download_file/${{chat_id}}/${{f.id}}`;
                    
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = f.name;
                    a.style.display = 'none';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    
                    await new Promise(r => setTimeout(r, 1500));
                }}
                
                btn.disabled = false;
                btn.innerText = 'Descargar Todos';
            }}
            
            function filterFiles() {{
                const query = document.getElementById('filter-input').value.toLowerCase();
                const rows = document.querySelectorAll('#files-body tr');
                rows.forEach(row => {{
                    const fileName = row.cells[1].innerText.toLowerCase();
                    if (fileName.includes(query)) {{
                        row.style.display = '';
                    }} else {{
                        row.style.display = 'none';
                    }}
                }});
            }}
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")

async def handle_download_file(request):
    chat_id_str = request.match_info.get("chat_id")
    msg_id_str = request.match_info.get("msg_id")
    
    try:
        chat_id = int(chat_id_str)
        msg_id = int(msg_id_str)
    except ValueError:
        return web.Response(status=400, text="Parámetros inválidos")
        
    from core.client import client
    try:
        msg = await client.get_messages(chat_id, ids=msg_id)
    except Exception as e:
        return web.Response(status=500, text=f"Error obteniendo mensaje: {e}")
        
    if not msg or not msg.media:
        return web.Response(status=404, text="Multimedia no encontrado")
        
    is_photo = bool(msg.photo)
    doc = getattr(msg, 'document', None)
    
    if is_photo:
        try:
            data = await client.download_media(msg, file=bytes)
            filename = f"imagen_{msg_id}.jpg"
            return web.Response(
                body=data,
                content_type="image/jpeg",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                }
            )
        except Exception as e:
            return web.Response(status=500, text=f"Error descargando imagen: {e}")
            
    elif doc:
        filename = f"archivo_{msg_id}"
        for attr in doc.attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                filename = attr.file_name
                break
                
        total_size = doc.size
        mime_type = doc.mime_type or "application/octet-stream"
        
        location = InputDocumentFileLocation(
            id=doc.id,
            access_hash=doc.access_hash,
            file_reference=doc.file_reference,
            thumb_size=""
        )
        
        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": mime_type,
                "Content-Length": str(total_size),
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Accept-Ranges": "none"
            }
        )
        await response.prepare(request)
        
        chunk_size = 512 * 1024
        offset = 0
        
        try:
            while offset < total_size:
                while True:
                    try:
                        result = await client(GetFileRequest(
                            location=location,
                            offset=offset,
                            limit=chunk_size
                        ))
                        chunk = result.bytes
                        if offset + len(chunk) > total_size:
                            chunk = chunk[:total_size - offset]
                        break
                    except FloodWaitError as e:
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"[Streaming Error] GetFileRequest falló: {e}")
                        return response
                        
                if not chunk:
                    break
                await response.write(chunk)
                offset += len(chunk)
        except Exception as e:
            print(f"[Streaming Exception] Error en streaming: {e}")
        finally:
            try:
                await response.write_eof()
            except Exception:
                pass
        return response
    else:
        return web.Response(status=404, text="Tipo de multimedia no soportado")

async def handle_scene(request):
    chat_id_str = request.match_info.get("chat_id")
    video_id_str = request.match_info.get("video_id")
    scene_index_str = request.match_info.get("scene_index")
    
    try:
        chat_id = int(chat_id_str)
        video_id = int(video_id_str)
        scene_index = int(scene_index_str)
    except ValueError:
        return web.Response(status=400, text="Parámetros inválidos")
        
    from core.client import client
    try:
        # Buscar hasta 30 mensajes antes de video_id para encontrar el álbum de fotos de las capturas
        messages = await client.get_messages(chat_id, limit=30, offset_id=video_id)
    except Exception as e:
        return web.Response(status=500, text=f"Error al obtener historial: {e}")
        
    # Filtrar mensajes que tengan fotos
    photo_messages = []
    for msg in messages:
        if msg and msg.photo:
            photo_messages.append(msg)
            
    if not photo_messages:
        return web.Response(status=404, text="No se encontraron capturas para este video")
        
    # Ordenar por ID ascendente (primera foto enviada primero)
    photo_messages.sort(key=lambda x: x.id)
    
    idx = scene_index - 1
    if idx < 0 or idx >= len(photo_messages):
        return web.Response(status=404, text="Índice de escena fuera de límites")
        
    selected_msg = photo_messages[idx]
    
    try:
        data = await client.download_media(selected_msg, file=bytes)
        return web.Response(
            body=data,
            content_type="image/jpeg"
        )
    except Exception as e:
        return web.Response(status=500, text=f"Error al descargar la escena: {e}")

async def handle_api_videos(request):
    chat_id = request.match_info.get("chat_id")
    
    channel_data = await DB.get_channel_data(chat_id)
    if not channel_data:
        alt_chat_id = chat_id.replace("-100", "") if chat_id.startswith("-100") else f"-100{chat_id}"
        channel_data = await DB.get_channel_data(alt_chat_id)
        
    if not channel_data:
        return web.json_response({"error": "Canal no encontrado"}, status=404)
        
    return web.json_response(channel_data)

async def sync_channel_pinned_status(chat_id_str):
    """Sincroniza en tiempo real los mensajes fijados de un canal con la base de datos."""
    try:
        from core.client import client
        from telethon.tl.types import InputMessagesFilterPinned
        if not client or not client.is_connected():
            return None

        clean_id = str(chat_id_str).strip()
        if clean_id.lstrip("-").isdigit():
            target_chat = int(clean_id)
        else:
            target_chat = clean_id

        pinned_msgs = await asyncio.wait_for(
            client.get_messages(target_chat, limit=100, filter=InputMessagesFilterPinned),
            timeout=3.0
        )
        if pinned_msgs is None:
            return None

        pinned_ids = {m.id for m in pinned_msgs}
        channel_data, actual_id = await find_channel_data_and_id(chat_id_str)
        if not channel_data or "videos" not in channel_data:
            return None

        changed = False
        for v in channel_data["videos"]:
            is_pinned = v.get("id") in pinned_ids
            if v.get("pinned") != is_pinned or v.get("is_pinned") != is_pinned:
                v["pinned"] = is_pinned
                v["is_pinned"] = is_pinned
                changed = True

        if changed:
            await DB.save_channel_data(actual_id, channel_data)
            print(f"[Auto-Sync Pinned] Fijados actualizados para canal {actual_id}: {len(pinned_ids)} fijados encontrados.")

        return channel_data
    except Exception as e:
        print(f"[Auto-Sync Pinned Warning] No se pudo sincronizar fijados para {chat_id_str}: {e}")
        return None

async def handle_api_sync_pinned(request):
    chat_id = request.match_info.get("chat_id")
    if not chat_id:
        return web.json_response({"success": False, "error": "Chat ID requerido"}, status=400)
        
    channel_data = await sync_channel_pinned_status(chat_id)
    if not channel_data:
        channel_data, _ = await find_channel_data_and_id(chat_id)
        
    if not channel_data:
        return web.json_response({"success": False, "error": "Canal no encontrado"}, status=404)
        
    return web.json_response({
        "success": True,
        "videos": channel_data.get("videos", [])
    })

async def handle_catalog(request):
    chat_id = request.match_info.get("chat_id")
    
    try:
        updated_data = await sync_channel_pinned_status(chat_id)
        if updated_data:
            channel_data = updated_data
        else:
            channel_data, _ = await find_channel_data_and_id(chat_id)
    except Exception as sync_err:
        print(f"[Catalog Error] Falló auto-sync de fijados: {sync_err}")
        channel_data, _ = await find_channel_data_and_id(chat_id)
        
    if not channel_data:
        error_html = """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Canal no encontrado - Brody Prime</title>
            <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
            <style>
                body {
                    font-family: 'Outfit', sans-serif;
                    background: #080612;
                    color: #ffffff;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    text-align: center;
                }
                .card {
                    background: rgba(255, 255, 255, 0.03);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    padding: 40px;
                    border-radius: 20px;
                    max-width: 500px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                }
                h1 { color: #f687b3; margin-bottom: 10px; }
                p { color: #a0aec0; line-height: 1.6; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Canal No Indexado ❌</h1>
                <p>Este canal no ha sido indexado por el Userbot aún. Usa el comando <code>/prime_video</code> dentro del canal en Telegram para registrar todos sus videos y generar este catálogo.</p>
            </div>
        </body>
        </html>
        """
        return web.Response(text=error_html, content_type="text/html")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, "catalog.html")
    
    if not os.path.exists(template_path):
        return web.Response(text="Error: catalog.html no se encuentra en el servidor.", status=500)
        
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()
    except Exception as e:
        return web.Response(text=f"Error leyendo la plantilla: {e}", status=500)
        
    channel_title = channel_data.get("channel_title", "Catálogo de Videos")
    videos_list = channel_data.get("videos", [])
    
    html = template_content.replace("{{channel_title}}", channel_title)
    html = html.replace("{{videos_json}}", json.dumps(videos_list, ensure_ascii=False))
    html = html.replace("{{chat_id}}", str(chat_id))
    return web.Response(text=html, content_type="text/html")

async def find_channel_data_and_id(chat_id_str):
    chat_id_str = str(chat_id_str).strip()
    channel_data = await DB.get_channel_data(chat_id_str)
    if channel_data:
        return channel_data, chat_id_str
    
    alt_chat_id = chat_id_str.replace("-100", "") if chat_id_str.startswith("-100") else f"-100{chat_id_str}"
    channel_data = await DB.get_channel_data(alt_chat_id)
    if channel_data:
        return channel_data, alt_chat_id

    try:
        all_data = await DB.get_all_data()
        channels = all_data.get("channels", {})
        clean_target = chat_id_str.replace("-100", "")
        for cid, cdata in channels.items():
            if str(cid).replace("-100", "") == clean_target:
                return cdata, str(cid)
    except Exception:
        pass
        
    return None, chat_id_str

async def handle_api_toggle_duplicate(request):
    try:
        data = await request.json()
        raw_chat_id = data.get("chat_id", "")
        video_id = data.get("video_id")

        if not raw_chat_id or video_id is None:
            return web.json_response({"success": False, "error": "Datos inválidos (chat_id o video_id faltante)"}, status=400)

        try:
            video_id = int(video_id)
        except ValueError:
            return web.json_response({"success": False, "error": "video_id debe ser entero"}, status=400)

        channel_data, resolved_chat_id = await find_channel_data_and_id(raw_chat_id)

        if not channel_data:
            return web.json_response({"success": False, "error": f"Canal '{raw_chat_id}' no encontrado"}, status=404)

        videos = channel_data.get("videos", [])
        video_item = None
        for v in videos:
            if v.get("id") == video_id:
                video_item = v
                break

        if not video_item:
            return web.json_response({"success": False, "error": "Video no encontrado en el catálogo"}, status=404)

        current_dup = bool(video_item.get("duplicate") or video_item.get("is_duplicate"))
        target_dup = not current_dup

        video_item["duplicate"] = target_dup
        if target_dup:
            # 1. Obtener duplicados existentes (excluyendo el actual)
            dup_videos = [
                v for v in videos 
                if (v.get("duplicate") or v.get("is_duplicate")) and v.get("id") != video_id
            ]
            # 2. Ordenar como los ve la interfaz actualmente
            dup_videos.sort(key=lambda x: (
                x.get("dup_order") if x.get("dup_order") is not None else 99999999,
                x.get("id", 0)
            ))
            # 3. Normalizar dup_order de los existentes (0, 1, 2...)
            for idx, dv in enumerate(dup_videos):
                dv["dup_order"] = idx
            # 4. El nuevo duplicado toma el lugar final (len(dup_videos))
            video_item["dup_order"] = len(dup_videos)
        else:
            if "dup_order" in video_item:
                del video_item["dup_order"]

        await DB.save_channel_data(resolved_chat_id, channel_data)

        return web.json_response({
            "success": True,
            "duplicate": target_dup,
            "dup_order": video_item.get("dup_order"),
            "message": "Video marcado como Duplicado (D)" if target_dup else "Video desmarcado de Duplicados"
        })
    except Exception as e:
        print(f"[API Duplicate Error] {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_api_reorder_duplicates(request):
    try:
        data = await request.json()
        raw_chat_id = data.get("chat_id", "")
        ordered_ids = data.get("ordered_ids", [])

        if not raw_chat_id or not isinstance(ordered_ids, list):
            return web.json_response({"success": False, "error": "Datos inválidos (chat_id u ordered_ids faltantes)"}, status=400)

        channel_data, resolved_chat_id = await find_channel_data_and_id(raw_chat_id)

        if not channel_data:
            return web.json_response({"success": False, "error": f"Canal '{raw_chat_id}' no encontrado"}, status=404)

        videos = channel_data.get("videos", [])
        int_ordered_ids = [int(i) for i in ordered_ids if str(i).isdigit() or (isinstance(i, int))]
        order_map = {vid: index for index, vid in enumerate(int_ordered_ids)}

        for v in videos:
            v_id = v.get("id")
            if v_id in order_map:
                v["dup_order"] = order_map[v_id]

        save_success = await DB.save_channel_data(resolved_chat_id, channel_data)
        if not save_success:
            return web.json_response({"success": False, "error": "No se pudo guardar la información en la base de datos"}, status=500)

        return web.json_response({"success": True, "message": "Orden de duplicados guardado con éxito"})
    except Exception as e:
        print(f"[API Reorder Error] {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_api_set_custom_thumbnail(request):
    try:
        data = await request.json()
        raw_chat_id = data.get("chat_id", "")
        video_id = data.get("video_id")
        thumb_time = data.get("thumb_time")

        if not raw_chat_id or video_id is None or thumb_time is None:
            return web.json_response({"success": False, "error": "Datos inválidos (chat_id, video_id o thumb_time faltante)"}, status=400)

        try:
            video_id = int(video_id)
            thumb_time = float(thumb_time)
        except (ValueError, TypeError):
            return web.json_response({"success": False, "error": "Parámetros numéricos inválidos"}, status=400)

        channel_data, resolved_chat_id = await find_channel_data_and_id(raw_chat_id)
        if not channel_data:
            return web.json_response({"success": False, "error": f"Canal '{raw_chat_id}' no encontrado"}, status=404)

        videos = channel_data.get("videos", [])
        video_item = None
        for v in videos:
            if v.get("id") == video_id:
                video_item = v
                break

        if not video_item:
            return web.json_response({"success": False, "error": "Video no encontrado en el catálogo"}, status=404)

        video_item["custom_thumb_time"] = thumb_time
        
        # Eliminar archivo cache anterior si existe para forzar regeneración
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cache_path = os.path.join(base_dir, "capturas_cache", str(resolved_chat_id), str(video_id), "custom.webp")
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
            except Exception:
                pass

        save_success = await DB.save_channel_data(resolved_chat_id, channel_data)
        if not save_success:
            return web.json_response({"success": False, "error": "No se pudo guardar la información en la base de datos"}, status=500)

        return web.json_response({
            "success": True,
            "message": "Miniatura personalizada guardada exitosamente",
            "custom_thumb_time": thumb_time
        })
    except Exception as e:
        print(f"[API Custom Thumb Error] {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_catalog_images(request):
    chat_id = request.match_info.get("chat_id")
    
    channel_data = await DB.get_channel_data(chat_id)
    if not channel_data:
        alt_chat_id = chat_id.replace("-100", "") if chat_id.startswith("-100") else f"-100{chat_id}"
        channel_data = await DB.get_channel_data(alt_chat_id)
        
    if not channel_data:
        error_html = """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Canal no encontrado - Brody Prime</title>
            <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
            <style>
                body {
                    font-family: 'Outfit', sans-serif;
                    background: #080612;
                    color: #ffffff;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    text-align: center;
                }
                .card {
                    background: rgba(255, 255, 255, 0.03);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    padding: 40px;
                    border-radius: 20px;
                    max-width: 500px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                }
                h1 { color: #f687b3; margin-bottom: 10px; }
                p { color: #a0aec0; line-height: 1.6; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Canal No Indexado ❌</h1>
                <p>Este canal no ha sido indexado por el Userbot aún. Usa el comando <code>/prime_imagenes</code> dentro del canal en Telegram para registrar todos sus videos y generar este catálogo.</p>
            </div>
        </body>
        </html>
        """
        return web.Response(text=error_html, content_type="text/html")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, "catalog_images.html")
    
    if not os.path.exists(template_path):
        return web.Response(text="Error: catalog_images.html no se encuentra en el servidor.", status=500)
        
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()
    except Exception as e:
        return web.Response(text=f"Error leyendo la plantilla: {e}", status=500)
        
    channel_title = channel_data.get("channel_title", "Catálogo de Escenas")
    videos_list = channel_data.get("videos", [])
    
    html = template_content.replace("{{channel_title}}", channel_title)
    html = html.replace("{{videos_json}}", json.dumps(videos_list, ensure_ascii=False))
    html = html.replace("{{chat_id}}", chat_id)
    
    return web.Response(text=html, content_type="text/html")

async def handle_commands_web(request):
    from handlers.list import COMMANDS_METADATA
    from utils.command_tracker import get_command_count
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, "commands.html")
    
    if not os.path.exists(template_path):
        return web.Response(text="Error: commands.html no se encuentra en el servidor.", status=500)
        
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()
    except Exception as e:
        return web.Response(text=f"Error leyendo commands.html: {e}", status=500)
        
    cmds_list = []
    for cmd in COMMANDS_METADATA:
        cmd_copy = dict(cmd)
        cmd_copy["uses"] = get_command_count(cmd["name"])
        cmds_list.append(cmd_copy)
        
    html = template_content.replace("{{commands_json}}", json.dumps(cmds_list, ensure_ascii=False))
    return web.Response(text=html, content_type="text/html")

def _extract_frame_sync(stream_url, ts, cache_path):
    import cv2
    try:
        cap = cv2.VideoCapture(stream_url)
        if not cap.isOpened():
            print(f"[Dynamic Frame Extract] No se pudo abrir el stream: {stream_url}")
            return None
        
        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
        ret, frame = cap.read()
        cap.release()
        
        if ret and frame is not None:
            try:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                cv2.imwrite(cache_path, frame, [int(cv2.IMWRITE_WEBP_QUALITY), 95])
            except Exception as e:
                print(f"[Dynamic Frame Cache Write Error] {e}")
                
            retval, buffer = cv2.imencode('.webp', frame, [int(cv2.IMWRITE_WEBP_QUALITY), 95])
            if retval:
                return buffer.tobytes()
    except Exception as e:
        print(f"[Dynamic Frame Extract Error] {e}")
    return None

async def handle_scene_dynamic(request):
    chat_id = request.match_info.get("chat_id")
    video_id_str = request.match_info.get("video_id")
    scene_index_str = request.match_info.get("scene_index")
    
    try:
        video_id = int(video_id_str)
        scene_index = int(scene_index_str)
    except ValueError:
        return web.Response(status=400, text="Parámetros de escena inválidos")
        
    if scene_index < 1 or scene_index > 50:
        return web.Response(status=400, text="Índice de escena fuera de rango [1..50]")
        
    # Verificar si está en caché local en disco (WebP)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_path = os.path.join(base_dir, "capturas_cache", str(chat_id), str(video_id), f"{scene_index}.webp")
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                return web.Response(body=f.read(), content_type="image/webp")
        except Exception as e:
            print(f"[Dynamic Scene Cache Read Error] {e}")
            
    # No está en caché: buscar metadatos en Firebase
    channel_data = await DB.get_channel_data(chat_id)
    if not channel_data:
        alt_chat_id = chat_id.replace("-100", "") if chat_id.startswith("-100") else f"-100{chat_id}"
        channel_data = await DB.get_channel_data(alt_chat_id)
        
    if not channel_data:
        return web.Response(status=404, text="Canal no encontrado en la base de datos")
        
    video_item = None
    for v in channel_data.get("videos", []):
        if v.get("id") == video_id:
            video_item = v
            break
            
    if not video_item:
        return web.Response(status=404, text="Video no encontrado en el catálogo del canal")
        
    # Calcular duración a segundos
    dur_str = video_item.get("duration", "0:00")
    parts = list(map(int, dur_str.split(':')))
    if len(parts) == 2:
        duration_sec = parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        duration_sec = parts[0] * 3600 + parts[1] * 60 + parts[2]
    else:
        duration_sec = 120
        
    stream_url = video_item.get("stream_url")
    if not stream_url:
        from core.client import client as telethon_client
        try:
            msg = await telethon_client.get_messages(int(chat_id), ids=video_id)
            if msg:
                from handlers.prime_video import get_stream_link_for_video
                stream_url = await get_stream_link_for_video(msg)
        except Exception as e:
            print(f"[Dynamic Scene Stream Gen Error] {e}")
            
    if not stream_url:
        return web.Response(status=404, text="No se pudo obtener la URL de streaming para este video")
        
    # Reemplazar host público con localhost:7861
    import re
    stream_url = re.sub(r'https?://[^/]+', 'http://127.0.0.1:7861', stream_url)
    
    # Calcular timestamp (5% a 95%)
    start_percent = 0.05
    end_percent = 0.95
    if scene_index == 1:
        percent = start_percent
    else:
        percent = start_percent + (end_percent - start_percent) * ((scene_index - 1) / 49.0)
    ts = percent * duration_sec
    
    # Extraer de forma no bloqueante usando asyncio.to_thread
    img_bytes = await asyncio.to_thread(_extract_frame_sync, stream_url, ts, cache_path)
    
    return web.Response(body=img_bytes, content_type="image/webp")

async def handle_custom_thumb(request):
    chat_id = request.match_info.get("chat_id")
    video_id_str = request.match_info.get("video_id")
    
    try:
        video_id = int(video_id_str)
    except ValueError:
        return web.Response(status=400, text="ID de video inválido")
        
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_path = os.path.join(base_dir, "capturas_cache", str(chat_id), str(video_id), "custom.webp")
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                return web.Response(body=f.read(), content_type="image/webp")
        except Exception as e:
            print(f"[Custom Thumb Cache Read Error] {e}")
            
    channel_data = await DB.get_channel_data(chat_id)
    if not channel_data:
        alt_chat_id = chat_id.replace("-100", "") if chat_id.startswith("-100") else f"-100{chat_id}"
        channel_data = await DB.get_channel_data(alt_chat_id)
        
    if not channel_data:
        return web.Response(status=404, text="Canal no encontrado")
        
    video_item = None
    for v in channel_data.get("videos", []):
        if v.get("id") == video_id:
            video_item = v
            break
            
    if not video_item:
        return web.Response(status=404, text="Video no encontrado")
        
    ts = video_item.get("custom_thumb_time")
    if ts is None:
        ts = 5.0
    else:
        ts = float(ts)
        
    stream_url = video_item.get("stream_url")
    if not stream_url:
        from core.client import client as telethon_client
        try:
            msg = await telethon_client.get_messages(int(chat_id), ids=video_id)
            if msg:
                from handlers.prime_video import get_stream_link_for_video
                stream_url = await get_stream_link_for_video(msg)
        except Exception as e:
            print(f"[Custom Thumb Stream Error] {e}")
            
    if not stream_url:
        return web.Response(status=404, text="No se pudo obtener URL de stream")
        
    import re
    stream_url = re.sub(r'https?://[^/]+', 'http://127.0.0.1:7861', stream_url)
    
    img_bytes = await asyncio.to_thread(_extract_frame_sync, stream_url, ts, cache_path)
    if not img_bytes:
        return web.Response(status=500, text="No se pudo extraer la miniatura")
        
    return web.Response(body=img_bytes, content_type="image/webp")

active_generation_tasks = set()

def _extract_single_scene_sync(stream_url, ts, cache_path):
    import cv2
    import os
    try:
        cap = cv2.VideoCapture(stream_url)
        if not cap.isOpened():
            return False
            
        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
        ret, frame = cap.read()
        cap.release()
        
        if ret and frame is not None:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            cv2.imwrite(cache_path, frame, [int(cv2.IMWRITE_WEBP_QUALITY), 95])
            return True
    except Exception as e:
        print(f"[Single Scene Sync Error] {e}")
    return False

async def bg_generate_scenes_task(chat_id, video_id, stream_url, duration_sec, cache_dir):
    import os
    import asyncio
    
    TOTAL_SCENES = 30
    CONCURRENCY_LIMIT = 4  # Extraer hasta 4 fotogramas en paralelo
    
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    
    # Escribir progreso inicial
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "progress.txt"), "w") as f_init:
        f_init.write("0")
        
    start_percent = 0.05
    end_percent = 0.95
    
    def update_progress():
        try:
            files = [f for f in os.listdir(cache_dir) if f.endswith(".webp") and os.path.getsize(os.path.join(cache_dir, f)) > 0]
            with open(os.path.join(cache_dir, "progress.txt"), "w") as f_progress:
                f_progress.write(str(len(files)))
        except Exception:
            pass

    async def worker(i):
        async with semaphore:
            cache_path = os.path.join(cache_dir, f"{i}.webp")
            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
                return
                
            if i == 1:
                percent = start_percent
            else:
                percent = start_percent + (end_percent - start_percent) * ((i - 1) / float(TOTAL_SCENES - 1))
                
            ts = percent * duration_sec
            
            # Intentar hasta 3 veces reconectando la transmisión si se cae
            for retry in range(3):
                success = await asyncio.to_thread(_extract_single_scene_sync, stream_url, ts, cache_path)
                if success:
                    break
                await asyncio.sleep(0.5)
                
            update_progress()

    try:
        # Lanzar extracción concurrente regulada por semáforo
        tasks = [worker(i) for i in range(1, TOTAL_SCENES + 1)]
        await asyncio.gather(*tasks)
    except Exception as e:
        print(f"[BG Gen Task Error] {e}")
    finally:
        active_generation_tasks.discard((chat_id, video_id))
        update_progress()

pregeneration_queue = asyncio.Queue()
pregeneration_worker_active = False

async def pregeneration_worker():
    global pregeneration_worker_active
    pregeneration_worker_active = True
    print("[Pregen Worker] Iniciado...")
    while True:
        try:
            item = await pregeneration_queue.get()
            chat_id, video_id, stream_url, duration_sec = item
            
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.join(base_dir, "capturas_cache", str(chat_id), str(video_id))
            
            # Verificar si ya está completo
            progress_file = os.path.join(cache_dir, "progress.txt")
            is_completed = False
            if os.path.exists(progress_file):
                try:
                    with open(progress_file, "r") as f:
                        if int(f.read().strip()) >= 30:
                            is_completed = True
                except Exception:
                    pass
                    
            if not is_completed:
                print(f"[Pregen Worker] Generando escenas para video {video_id}...")
                active_generation_tasks.add((chat_id, video_id))
                await bg_generate_scenes_task(chat_id, video_id, stream_url, duration_sec, cache_dir)
                print(f"[Pregen Worker] Escenas completadas para video {video_id}!")
                
            pregeneration_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Pregen Worker Error] {e}")
            await asyncio.sleep(5)
            
    pregeneration_worker_active = False

async def add_to_pregeneration_queue(chat_id, video_id, stream_url, duration_sec):
    global pregeneration_worker_active
    await pregeneration_queue.put((chat_id, video_id, stream_url, duration_sec))
    if not pregeneration_worker_active:
        asyncio.create_task(pregeneration_worker())

async def handle_generate_scenes(request):
    chat_id = request.match_info.get("chat_id")
    video_id_str = request.match_info.get("video_id")
    
    try:
        video_id = int(video_id_str)
    except ValueError:
        return web.json_response({"error": "ID de video inválido"}, status=400)
        
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(base_dir, "capturas_cache", str(chat_id), str(video_id))
    progress_file = os.path.join(cache_dir, "progress.txt")
    
    # Comprobar si ya están completadas
    if os.path.exists(progress_file):
        try:
            with open(progress_file, "r") as f:
                progress = int(f.read().strip())
            if progress >= 30:
                return web.json_response({"status": "completed", "progress": 30})
        except Exception:
            pass
            
    # Si está activamente generándose
    if (chat_id, video_id) in active_generation_tasks:
        current_progress = 0
        if os.path.exists(progress_file):
            try:
                with open(progress_file, "r") as f:
                    current_progress = int(f.read().strip())
            except Exception:
                pass
        return web.json_response({"status": "processing", "progress": current_progress})
        
    # Si no está generándose, buscar el video en la DB
    channel_data = await DB.get_channel_data(chat_id)
    if not channel_data:
        alt_chat_id = chat_id.replace("-100", "") if chat_id.startswith("-100") else f"-100{chat_id}"
        channel_data = await DB.get_channel_data(alt_chat_id)
        
    if not channel_data:
        return web.json_response({"error": "Canal no encontrado"}, status=404)
        
    video_item = None
    for v in channel_data.get("videos", []):
        if v.get("id") == video_id:
            video_item = v
            break
            
    if not video_item:
        return web.json_response({"error": "Video no encontrado"}, status=404)
        
    # Calcular duración
    dur_str = video_item.get("duration", "0:00")
    parts = list(map(int, dur_str.split(':')))
    if len(parts) == 2:
        duration_sec = parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        duration_sec = parts[0] * 3600 + parts[1] * 60 + parts[2]
    else:
        duration_sec = 120
        
    stream_url = video_item.get("stream_url")
    if not stream_url:
        from core.client import client as telethon_client
        try:
            msg = await telethon_client.get_messages(int(chat_id), ids=video_id)
            if msg:
                from handlers.prime_video import get_stream_link_for_video
                stream_url = await get_stream_link_for_video(msg)
        except Exception:
            pass
            
    if not stream_url:
        return web.json_response({"error": "No se pudo obtener URL de stream"}, status=404)
        
    import re
    stream_url = re.sub(r'https?://[^/]+', 'http://127.0.0.1:7861', stream_url)
    
    # Iniciar la tarea de fondo y responder inmediatamente
    active_generation_tasks.add((chat_id, video_id))
    asyncio.create_task(bg_generate_scenes_task(chat_id, video_id, stream_url, duration_sec, cache_dir))
    
    return web.json_response({"status": "started", "progress": 0})

async def handle_scene_progress(request):
    chat_id = request.match_info.get("chat_id")
    video_id_str = request.match_info.get("video_id")
    
    try:
        video_id = int(video_id_str)
    except ValueError:
        return web.json_response({"error": "ID de video inválido"}, status=400)
        
    base_dir = os.path.dirname(os.path.abspath(__file__))
    progress_file = os.path.join(base_dir, "capturas_cache", str(chat_id), str(video_id), "progress.txt")
    
    progress = 0
    if os.path.exists(progress_file):
        try:
            with open(progress_file, "r") as f:
                progress = int(f.read().strip())
        except Exception:
            pass
            
    # Determinar si sigue activo
    status = "completed" if progress >= 30 else "processing"
    if (chat_id, video_id) in active_generation_tasks:
        status = "processing"
        
    return web.json_response({"status": status, "progress": progress})

async def handle_stream_proxy(request):
    path = request.path
    query = request.query_string
    url = f"http://127.0.0.1:7861{path}"
    if query:
        url += f"?{query}"
        
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ('host',)}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=request.method,
                url=url,
                headers=headers,
                data=await request.read() if request.has_body else None,
                allow_redirects=False
            ) as resp:
                
                exclude_headers = {'content-encoding', 'transfer-encoding'}
                resp_headers = {
                    k: v for k, v in resp.headers.items()
                    if k.lower() not in exclude_headers
                }
                
                response = web.StreamResponse(
                    status=resp.status,
                    reason=resp.reason,
                    headers=resp_headers
                )
                await response.prepare(request)
                
                async for chunk in resp.content.iter_chunked(262144): # 256KB chunks
                    await response.write(chunk)
                    
                await response.write_eof()
                return response
    except Exception as e:
        print(f"[Proxy Error] Error al conectar con el servidor de streaming de Go: {e}")
async def handle_monitor_dashboard(request):
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Diagnóstico y Monitoreo de Spaces - Hugging Face</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg: #0b0914;
                --card: rgba(255, 255, 255, 0.03);
                --card-border: rgba(255, 255, 255, 0.08);
                --text: #f7fafc;
                --text-sub: #a0aec0;
                --accent: #805ad5;
                --green: #48bb78;
                --yellow: #ecc94b;
                --red: #f56565;
            }
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: 'Outfit', sans-serif;
                background: linear-gradient(135deg, #090614 0%, #120c2b 50%, #04020a 100%);
                color: var(--text);
                min-height: 100vh;
                padding: 40px 20px;
            }
            .header {
                max-width: 1000px;
                margin: 0 auto 30px auto;
                text-align: center;
            }
            .header h1 {
                font-size: 2.2rem;
                font-weight: 800;
                background: linear-gradient(to right, #b794f4, #f687b3, #63b3ed);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 8px;
            }
            .header p { color: var(--text-sub); font-size: 1rem; }
            .container {
                max-width: 1000px;
                margin: 0 auto;
                display: flex;
                flex-direction: column;
                gap: 25px;
            }
            .controls {
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: var(--card);
                border: 1px solid var(--card-border);
                border-radius: 16px;
                padding: 15px 25px;
                backdrop-filter: blur(10px);
            }
            .btn {
                background: linear-gradient(135deg, #6b46c1, #805ad5);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 10px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s ease;
                font-family: inherit;
            }
            .btn:hover { opacity: 0.9; transform: translateY(-1px); }
            .space-card {
                background: var(--card);
                border: 1px solid var(--card-border);
                border-radius: 20px;
                padding: 25px;
                backdrop-filter: blur(12px);
                box-shadow: 0 15px 35px rgba(0,0,0,0.4);
            }
            .card-top {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }
            .space-title { font-size: 1.3rem; font-weight: 700; color: #e2e8f0; }
            .badge {
                padding: 6px 14px;
                border-radius: 999px;
                font-weight: 700;
                font-size: 0.85rem;
                display: inline-flex;
                align-items: center;
                gap: 6px;
            }
            .badge-green { background: rgba(72, 187, 120, 0.15); border: 1px solid var(--green); color: var(--green); }
            .badge-yellow { background: rgba(236, 201, 75, 0.15); border: 1px solid var(--yellow); color: var(--yellow); }
            .badge-red { background: rgba(245, 101, 101, 0.15); border: 1px solid var(--red); color: var(--red); }
            .grid-details {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }
            .detail-item {
                background: rgba(0,0,0,0.25);
                border: 1px solid rgba(255,255,255,0.05);
                padding: 12px 16px;
                border-radius: 12px;
            }
            .detail-label { font-size: 0.8rem; color: var(--text-sub); margin-bottom: 4px; }
            .detail-value { font-size: 0.95rem; font-weight: 600; color: #edf2f7; }
            .cause-box {
                margin-top: 15px;
                background: rgba(0, 0, 0, 0.3);
                border-left: 4px solid var(--accent);
                padding: 12px 16px;
                border-radius: 0 10px 10px 0;
                font-size: 0.9rem;
                color: #e2e8f0;
            }
            .action-bar {
                margin-top: 20px;
                display: flex;
                gap: 12px;
            }
            .btn-outline {
                background: transparent;
                border: 1px solid var(--card-border);
                color: #cbd5e0;
                padding: 8px 16px;
                border-radius: 8px;
                font-size: 0.85rem;
                cursor: pointer;
                text-decoration: none;
            }
            .btn-outline:hover { background: rgba(255,255,255,0.05); color: white; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔍 Diagnóstico & Monitoreo de Spaces</h1>
            <p>Estado en tiempo real, latencia, SSL/DNS y generación de informes .txt autónomos</p>
        </div>
        <div class="container">
            <div class="controls">
                <span id="last-update-time">Cargando estado...</span>
                <button class="btn" onclick="checkNow()">🔄 Comprobar Ahora</button>
            </div>
            <div id="spaces-list"></div>
        </div>

        <script>
            async defFetchStatus() {
                try {
                    const res = await fetch('/api/monitor_status');
                    const data = await res.json();
                    renderSpaces(data);
                } catch(e) {
                    console.error("Error al obtener estado:", e);
                }
            }

            function renderSpaces(data) {
                const container = document.getElementById('spaces-list');
                container.innerHTML = '';
                document.getElementById('last-update-time').innerText = 'Último chequeo: ' + new Date().toLocaleTimeString();

                for (const [url, info] of Object.entries(data)) {
                    const current = info.current;
                    if (!current) continue;
                    
                    const spaceName = url.split('/').pop();
                    let badgeClass = 'badge-green';
                    if (current.category.includes('🟡')) badgeClass = 'badge-yellow';
                    if (current.category.includes('🔴')) badgeClass = 'badge-red';

                    const card = document.createElement('div');
                    card.className = 'space-card';
                    card.innerHTML = `
                        <div class="card-top">
                            <div class="space-title">🌐 ${spaceName}</div>
                            <div class="badge ${badgeClass}">${current.category}</div>
                        </div>
                        <div class="grid-details">
                            <div class="detail-item">
                                <div class="detail-label">Latencia</div>
                                <div class="detail-value">${current.latency_ms} ms</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">DNS</div>
                                <div class="detail-value">${current.dns.ok ? '🟢 OK (' + (current.dns.ip || 'Resuelto') + ')' : '🔴 Error'}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">SSL (HTTPS)</div>
                                <div class="detail-value">${current.ssl.ok ? '🟢 Válido' : '🔴 Fallo'}</div>
                            </div>
                            <div class="detail-item">
                                <div class="detail-label">HF API Stage</div>
                                <div class="detail-value">${current.hf_api ? current.hf_api.stage : 'N/A'}</div>
                            </div>
                        </div>
                        <div class="cause-box">
                            <strong>Diagnóstico:</strong> ${current.details}
                        </div>
                        <div class="action-bar">
                            <a class="btn-outline" href="/api/monitor_download_log/${spaceName}" target="_blank">📄 Descargar Reporte TXT</a>
                            <a class="btn-outline" href="${url}" target="_blank">🌐 Visitar Space</a>
                        </div>
                    `;
                    container.appendChild(card);
                }
            }

            async function checkNow() {
                document.getElementById('last-update-time').innerText = 'Verificando...';
                await fetch('/api/monitor_check_now', { method: 'POST' });
                defFetchStatus();
            }

            defFetchStatus();
            setInterval(defFetchStatus, 30000);
        </script>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type="text/html")

async def handle_api_monitor_status(request):
    return web.json_response(space_monitor.history)

async def handle_api_monitor_check_now(request):
    await space_monitor.run_check_cycle()
    return web.json_response({"status": "ok", "history": space_monitor.history})

async def handle_api_monitor_download_log(request):
    space_name = request.match_info.get("space_name")
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "diagnostics")
    os.makedirs(logs_dir, exist_ok=True)
    
    files = [f for f in os.listdir(logs_dir) if space_name.lower() in f.lower() and f.endswith(".txt")]
    if not files:
        # Generar un informe en vivo si aún no se había guardado un archivo
        target_url = None
        for u in space_monitor.history:
            if space_name.lower() in u.lower():
                target_url = u
                break
        if target_url and space_monitor.history.get(target_url, {}).get("current"):
            txt_path, latest_file = space_monitor.generate_txt_report(space_monitor.history[target_url]["current"])
        else:
            return web.Response(status=404, text=f"No hay datos de diagnóstico para {space_name}")
    else:
        latest_file = sorted(files)[-1]
        txt_path = os.path.join(logs_dir, latest_file)
        
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()
    return web.Response(text=content, content_type="text/plain; charset=utf-8", headers={
        "Content-Disposition": f"inline; filename={latest_file}"
    })

async def start_go_stream_bot():
    fsb_path = "./BrodyFileStreamBot/fsb"
    if os.name == "nt":
        fsb_path = "./BrodyFileStreamBot/fsb.exe"
        
    if os.path.exists(fsb_path):
        if os.name != "nt":
            try:
                os.chmod(fsb_path, 0o755)
            except Exception as e:
                print(f"[Go Stream Bot] Advertencia al cambiar permisos: {e}")
                
        abs_fsb_path = os.path.abspath(fsb_path)
        print(f"[Go Stream Bot] Iniciando BrodyFileStreamBot ({abs_fsb_path}) en segundo plano...")
        env = os.environ.copy()
        env["PORT"] = "7861"
        try:
            process = await asyncio.create_subprocess_exec(
                abs_fsb_path, "run",
                env=env,
                cwd="./BrodyFileStreamBot",
                stdout=None,
                stderr=None
            )
            print(f"[Go Stream Bot] Proceso iniciado con PID: {process.pid}")
        except Exception as e:
            print(f"[Go Stream Bot] ❌ Error al iniciar subprocess: {e}")
    else:
        print(f"[Go Stream Bot] ⚠️ No se encontró el ejecutable {fsb_path}. Se asume ejecución externa.")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_home)
    app.router.add_get("/monitor", handle_monitor_dashboard)
    app.router.add_get("/api/monitor_status", handle_api_monitor_status)
    app.router.add_post("/api/monitor_check_now", handle_api_monitor_check_now)
    app.router.add_get("/api/monitor_download_log/{space_name}", handle_api_monitor_download_log)
    app.router.add_get("/catalog/{chat_id}", handle_catalog)
    app.router.add_get("/catalog_images/{chat_id}", handle_catalog_images)
    app.router.add_get("/commands", handle_commands_web)
    app.router.add_get("/comandos", handle_commands_web)
    app.router.add_get("/api/videos/{chat_id}", handle_api_videos)
    app.router.add_get("/api/sync_pinned/{chat_id}", handle_api_sync_pinned)
    app.router.add_post("/api/sync_pinned/{chat_id}", handle_api_sync_pinned)
    app.router.add_get("/download_batch/{batch_id}", handle_download_batch)
    app.router.add_get("/download_file/{chat_id}/{msg_id}", handle_download_file)
    app.router.add_get("/scenes/{chat_id}/{video_id}/{scene_index}.jpg", handle_scene)
    app.router.add_get("/scenes_dynamic/{chat_id}/{video_id}/{scene_index}.webp", handle_scene_dynamic)
    app.router.add_get("/custom_thumb/{chat_id}/{video_id}.webp", handle_custom_thumb)
    app.router.add_get("/generate_scenes/{chat_id}/{video_id}", handle_generate_scenes)
    app.router.add_get("/api/scene_progress/{chat_id}/{video_id}", handle_scene_progress)
    app.router.add_post("/api/toggle_duplicate", handle_api_toggle_duplicate)
    app.router.add_post("/api/reorder_duplicates", handle_api_reorder_duplicates)
    app.router.add_post("/api/set_custom_thumbnail", handle_api_set_custom_thumbnail)
    app.router.add_route("*", "/stream/{tail:.*}", handle_stream_proxy)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 7860)
    await site.start()
    print("Web server running on port 7860")

def custom_exception_handler(loop, context):
    exception = context.get('exception')
    # Silenciar errores específicos de Windows Proactor (WinError 10054)
    if isinstance(exception, ConnectionResetError) or (exception and "WinError 10054" in str(exception)):
        return
    loop.default_exception_handler(context)

async def main():
    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(custom_exception_handler)
    except Exception:
        pass
    
    # Iniciar el monitor autónomo de Spaces en segundo plano
    asyncio.create_task(space_monitor.start_monitoring())
    print("[Main] Monitor de Spaces iniciado en segundo plano.")

    # Si estamos ejecutándonos en Hugging Face (o si SPACE_ID está definido), iniciamos el bot de Go
    if os.environ.get("SPACE_ID"):
        await start_go_stream_bot()
        
    # Iniciar servidor web en el puerto 7860
    await start_web_server()
    # Iniciar el bot de Telegram en segundo plano
    await bot_prime.main()

if __name__ == "__main__":
    asyncio.run(main())

