import os
import re
import html
import time
import asyncio
from telegraph.aio import Telegraph
from telethon import events, Button
from telethon.tl.types import DocumentAttributeVideo
from telethon.errors import FloodWaitError
from core.client import client
from utils.helpers import (
    extract_title_from_caption,
    clean_comparison_string,
    extract_series_name,
    get_message_title,
    safe_edit_status
)
from utils.channel_resolver import matches_channel, is_jav_channel


# Expresión regular para códigos JAV (ej: PRED-769, DVDMS-149, GVG-707, etc.)
JAV_REGEX = re.compile(r'\b([a-zA-Z0-9]{2,10}-\d{2,7})\b')

# Prefijos excluidos comunes para evitar falsos positivos
EXCLUDED_PREFIXES = {
    'ep', 'pt', 'part', 'cap', 'vol', 'v', 'ed', 'id', 'p',
    'dvd', 'cd', 'mp4', 'mkv', 'avi', 'gif', 'png', 'jpg'
}

def determine_censorship(text):
    text_lower = text.lower()
    # Buscar "sin censura", "uncensored" o "s/c"
    if "sin censura" in text_lower or "uncensored" in text_lower or re.search(r'\b(?:s/c|sin_censura)\b', text_lower):
        return "sin censura"
    # Buscar "con censura", "tiene censura", "censored" o "c/c"
    if "con censura" in text_lower or "tiene censura" in text_lower or "censored" in text_lower or re.search(r'\b(?:c/c|con_censura)\b', text_lower):
        return "con censura"
    return None

def format_duration(seconds):
    if not seconds:
        return "00:00"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def format_size(size_bytes):
    if not size_bytes:
        return "0 B"
    size_bytes = int(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def shorten_title(title, max_len=20):
    if not title:
        return ""
    return title[:max_len]

async def create_telegraph_page(title, html_content):
    try:
        telegraph = Telegraph()
        await telegraph.create_account(short_name='BotPrime')
        response = await telegraph.create_page(
            title=title,
            html_content=html_content
        )
        return f"https://telegra.ph/{response['path']}"
    except Exception as e:
        print(f"Telegraph error: {e}")
        return None

async def procesar_comando_repetidos(event):
    chat_id = event.chat_id
    
    # Parse scan limit (default None to scan everything)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    limit_desc = f"en los últimos {limit} mensajes" if limit else "en todo el historial"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Analizando el canal {limit_desc}...")
    
    try:
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', '') or ''
        
        # Si es el canal Hentaila VIP, usar la lógica original basada en títulos
        if matches_channel(chat_id, chat_title, "hentaila_vip"):
            await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Buscando títulos y duplicados {limit_desc} (Hentaila VIP)...")
            await procesar_repetidos_hentaila(event, status_msg, limit=limit)
            return

        # Si es un canal JAV, buscar duplicados por código en portadas
        if is_jav_channel(chat_id, chat_title):
            await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Buscando códigos JAV duplicados en portadas {limit_desc}...")
            await procesar_repetidos_jav(event, status_msg, chat, limit=limit)
            return

        # Para los demás canales: Lógica basada en archivos de video, peso y duración
        await procesar_repetidos_general(event, status_msg, chat, limit=limit)
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
        except Exception:
            pass

async def procesar_repetidos_hentaila(event, status_msg, limit=None):
    chat_id = event.chat_id
    try:
        total_msgs = limit
        if not total_msgs:
            try:
                total_info = await client.get_messages(chat_id, limit=0)
                total_msgs = total_info.total
            except Exception:
                total_msgs = 0

        # 1. Obtener todos los mensajes
        messages = []
        count = 0
        last_update = time.time()
        
        async for m in client.iter_messages(chat_id, limit=limit):
            count += 1
            messages.append(m)
            
            now = time.time()
            if now - last_update > 4.0:
                pct_str = f" ({int((count / total_msgs) * 100)}%)" if total_msgs else ""
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando historial... {count} msgs{pct_str}")
                last_update = now
            
        # 2. Agrupar series y videos
        series_groups = {}
        video_groups = {}
        
        for m in messages:
            # Identificar fotos de series (plantilla del bot con sinopsis)
            if m.photo and m.message:
                if re.search(r'\b(?:titulo|título):\s*', m.message, re.IGNORECASE):
                    raw_title = extract_title_from_caption(m.message)
                    if raw_title:
                        clean_title = clean_comparison_string(raw_title)
                        if clean_title:
                            if clean_title not in series_groups:
                                series_groups[clean_title] = []
                            series_groups[clean_title].append((raw_title, m))
            
            # Identificar videos (para detectar duplicados de videos con la misma descripción)
            elif m.video:
                v_title = get_message_title(m)
                if v_title:
                    clean_v_title = clean_comparison_string(v_title)
                    if clean_v_title:
                        if clean_v_title not in video_groups:
                            video_groups[clean_v_title] = []
                        video_groups[clean_v_title].append((v_title, m))
                        
        # 3. Filtrar y clasificar series duplicadas
        all_items = []
        series_copies = []
        channel_id_str = str(chat_id).replace("-100", "")
        
        for clean_title, msg_list in series_groups.items():
            # Ordenar por ID ascendente para que el más antiguo sea el original
            msg_list.sort(key=lambda x: x[1].id)
            
            orig_title, orig_msg = msg_list[0]
            orig_link = f"https://t.me/c/{channel_id_str}/{orig_msg.id}"
            all_items.append((orig_title, orig_msg.id, False, 1, orig_link))
            
            for idx, (copy_title, copy_msg) in enumerate(msg_list[1:], start=2):
                copy_link = f"https://t.me/c/{channel_id_str}/{copy_msg.id}"
                all_items.append((f"{copy_title} (copia {idx})", copy_msg.id, True, idx, copy_link))
                series_copies.append((copy_title, copy_msg, idx))
                
        # 4. Filtrar y clasificar videos duplicados
        video_copies = []
        for clean_v_title, msg_list in video_groups.items():
            # Ordenar por ID ascendente para que el más antiguo sea el original
            msg_list.sort(key=lambda x: x[1].id)
            
            if len(msg_list) > 1:
                # El primero se considera el original, los siguientes son copias
                for idx, (copy_title, copy_msg) in enumerate(msg_list[1:], start=2):
                    video_copies.append((copy_title, copy_msg, idx))

        if not all_items and not video_copies:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontraron series ni videos para procesar.")
            await asyncio.sleep(5)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        # 5. Construir lista de enlaces para la lista general de títulos de series
        lines = []
        for i, (title, msg_id, is_copy, copy_num, link) in enumerate(all_items, start=1):
            lines.append(f"<li><b>{i}.</b> <a href=\"{link}\">{title}</a></li>")
            
        telegraph_urls = []
        if lines:
            batch_size = 150
            for i in range(0, len(lines), batch_size):
                batch_lines = lines[i:i+batch_size]
                html_list = "<p><b>Lista de Títulos en el Canal:</b></p><ul>" + "".join(batch_lines) + "</ul>"
                part_suffix = f" (Parte {i//batch_size + 1})" if len(lines) > batch_size else ""
                url = await create_telegraph_page(f"Lista de Títulos{part_suffix}", html_list)
                if url:
                    telegraph_urls.append(f"📂 <a href='{url}'>Ver Lista de Títulos{part_suffix}</a>")
            
        # Eliminar el mensaje de estado inicial
        await status_msg.delete()
 
        # Enviar el enlace de Telegraph
        if telegraph_urls:
            links_text = "\n".join(telegraph_urls)
            await event.respond(f"🌐 <b>Catálogo general generado:</b>\n{links_text}\u200b", parse_mode='html', link_preview=True)
            
        # 6. Enviar el informe de duplicados en un mensaje separado
        if series_copies or video_copies:
            dup_lines = []
            
            if series_copies:
                dup_lines.append("🗂️ **Series Duplicadas (plantilla sinopsis):**")
                for copy_title, copy_msg, copy_num in series_copies:
                    copy_link = f"https://t.me/c/{channel_id_str}/{copy_msg.id}"
                    dup_lines.append(
                        f"• <a href=\"{copy_link}\">{copy_title} (copia {copy_num})</a>\n"
                        f"  └─ Eliminar: <code>/eliminar_copia_{copy_msg.id}</code>"
                    )
                dup_lines.append("")
                
            if video_copies:
                dup_lines.append("🎬 **Videos Duplicados (misma descripción):**")
                for copy_title, copy_msg, copy_num in video_copies:
                    copy_link = f"https://t.me/c/{channel_id_str}/{copy_msg.id}"
                    dup_lines.append(
                        f"• <a href=\"{copy_link}\">{copy_title} (copia {copy_num})</a>\n"
                        f"  └─ Eliminar: <code>/eliminar_copia_{copy_msg.id}</code>"
                    )
                
            dup_message = (
                "⚠️ **Se detectaron las siguientes copias duplicadas en el canal:**\n\n" + 
                "\n".join(dup_lines) +
                "\n\n🧹 **Para limpiar este reporte:** <code>/limpiar</code>"
            )
            await event.respond(dup_message + "\u200b", parse_mode='html', link_preview=False)
        else:
            await event.respond("✅ **No hay series ni videos duplicados.**\n\n🧹 **Para limpiar este reporte:** <code>/limpiar</code>\u200b", parse_mode='html', link_preview=False)
            
    except Exception as e:
        await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error al buscar repetidos: {e}")

async def procesar_repetidos_general(event, status_msg, chat, limit=None):
    chat_id = event.chat_id
    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    messages = []
    
    total_msgs = limit
    if not total_msgs:
        try:
            total_info = await client.get_messages(chat_id, limit=0)
            total_msgs = total_info.total
        except Exception:
            total_msgs = 0

    count = 0
    last_update = time.time()
    
    # Escanear todos los mensajes del canal
    async for m in client.iter_messages(chat_id, limit=limit):
        count += 1
        if m.document:
            is_video = False
            file_name = ""
            
            # Extraer atributos y nombre del archivo
            for attr in m.document.attributes:
                if isinstance(attr, DocumentAttributeVideo):
                    is_video = True
                elif hasattr(attr, 'file_name') and attr.file_name:
                    file_name = attr.file_name
            
            mime = m.document.mime_type or ""
            if mime.startswith('video/') or file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts')):
                is_video = True
            
            if is_video:
                messages.append(m)
                
            # Throttling de actualizaciones de estado para evitar FloodWait
            now = time.time()
            if now - last_update > 4.0:
                pct_str = f" ({int((count / total_msgs) * 100)}%)" if total_msgs else ""
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando {limit_desc}... {count} msgs{pct_str}\n\n(Videos encontrados: {len(messages)})")
                last_update = now
                
    if not messages:
        await safe_edit_status(status_msg, f"❌ **[Bot Prime]** No se encontraron videos en {limit_desc}.")
        await asyncio.sleep(5)
        await status_msg.delete()
        try:
            await event.delete()
        except Exception:
            pass
        return
        
    # Ordenar por peso (tamaño del archivo en bytes) de menor a mayor
    messages.sort(key=lambda x: x.document.size or 0)
    
    # Construir lista de videos y buscar duplicados
    lines = []
    dup_groups = {}
    
    channel_id_str = str(chat.id).replace("-100", "")
    is_public = bool(getattr(chat, 'username', None))
    
    for idx_msg, m in enumerate(messages, start=1):
        # File name
        file_name = m.file.name or f"video_{m.id}"
        
        # Duration & Size
        duration = 0
        for attr in m.document.attributes:
            if isinstance(attr, DocumentAttributeVideo):
                duration = attr.duration
                break
        if not duration and m.file.duration:
            duration = m.file.duration
            
        size = m.document.size or 0
        
        # Link
        if is_public:
            link = f"https://t.me/{chat.username}/{m.id}"
        else:
            link = f"https://t.me/c/{channel_id_str}/{m.id}"
            
        formatted_duration = format_duration(duration)
        formatted_size = format_size(size)
        short_name = shorten_title(file_name)
        escaped_name = html.escape(short_name)
        
        # Línea de la lista general
        lines.append(f"<li><b>{idx_msg}.</b> <a href=\"{link}\">{escaped_name}</a> ({formatted_duration}) ({formatted_size})</li>")
        
        # Agrupar para duplicados
        if size > 0:
            key = (size, duration)
            if key not in dup_groups:
                dup_groups[key] = []
            dup_groups[key].append(m)
            
    # Enviar lista general usando Telegraph dividida en partes si es muy grande
    telegraph_urls = []
    if lines:
        batch_size = 150
        for i in range(0, len(lines), batch_size):
            batch_lines = lines[i:i+batch_size]
            html_list = "<p><b>Lista de Videos en el Canal:</b></p><ul>" + "".join(batch_lines) + "</ul>"
            part_suffix = f" (Parte {i//batch_size + 1})" if len(lines) > batch_size else ""
            url = await create_telegraph_page(f"Videos en el Canal{part_suffix}", html_list)
            if url:
                telegraph_urls.append(f"📂 <a href='{url}'>Ver Lista Completa{part_suffix}</a>")
        
    await status_msg.delete()
    
    if telegraph_urls:
        links_text = "\n".join(telegraph_urls)
        await event.respond(f"🌐 <b>Catálogo de videos generado:</b>\n{links_text}\u200b", parse_mode='html', link_preview=True)
        
    # Enviar informe de duplicados ordenado por peso de menor a mayor
    dup_html = []
    for (size, duration), msg_list in sorted(dup_groups.items(), key=lambda x: x[0][0]):
        if len(msg_list) > 1:
            formatted_size = format_size(size)
            formatted_duration = format_duration(duration)
            dup_html.append(f"<p><b>Coincidencia: {formatted_size} | {formatted_duration}</b></p><ul>")
            
            for idx, m in enumerate(msg_list, 1):
                f_name = m.file.name or f"video_{m.id}"
                
                # Obtener detalles del video en el grupo
                m_duration = 0
                for attr in m.document.attributes:
                    if isinstance(attr, DocumentAttributeVideo):
                        m_duration = attr.duration
                        break
                if not m_duration and m.file.duration:
                    m_duration = m.file.duration
                m_size = m.document.size or 0
                
                m_formatted_duration = format_duration(m_duration)
                m_formatted_size = format_size(m_size)
                
                f_short_name = shorten_title(f_name)
                esc_name = html.escape(f_short_name)
                
                if is_public:
                    lnk = f"https://t.me/{chat.username}/{m.id}"
                else:
                    lnk = f"https://t.me/c/{channel_id_str}/{m.id}"
                dup_html.append(f"<li>{idx}. <a href=\"{lnk}\">{esc_name}</a> ({m_formatted_size} | {m_formatted_duration})</li>")
            dup_html.append("</ul>")
            
    if dup_html:
        html_dups = "<p><b>Videos Duplicados Encontrados:</b></p>" + "".join(dup_html)
        telegraph_dup_url = await create_telegraph_page("Reporte de Duplicados", html_dups)
        
        text_reply = f"⚠️ <b>Se detectaron {len(dup_html)//2} grupos de videos duplicados.</b>\n\n"
        if telegraph_dup_url:
            text_reply += f"📂 <a href='{telegraph_dup_url}'>Ver Reporte de Duplicados en Telegraph</a>\n\n"
            
        text_reply += "<b>Opciones Rápidas:</b>\n"
        text_reply += "🧹 <b>Limpiar reporte:</b> <code>/limpiar</code>\n"
        text_reply += "🗑️ <b>Borrar duplicados automáticamente:</b> <code>/elimina_duplicados</code>"
        
        await event.respond(text_reply + "\u200b", parse_mode='html', link_preview=True)
    else:
        text_no_duplicates = (
            "✅ <b>No se encontraron videos duplicados por peso y tiempo.</b>\n\n"
            "🧹 <b>Para limpiar este reporte:</b> <code>/limpiar</code>"
        )
        await event.respond(text_no_duplicates + "\u200b", parse_mode='html', link_preview=False)

async def procesar_comando_limpiar(event):
    chat_id = event.chat_id
    
    delete_ids = set([event.id]) # el propio comando /limpiar
    delete_grouped_ids = set()
    all_recent = []
    
    # Buscar en los últimos 150 mensajes del chat
    async for m in client.iter_messages(chat_id, limit=150):
        all_recent.append(m)
        if m.message:
            text = m.message
            # Identificar de forma inteligente si el mensaje es parte del reporte
            if (
                "\u200b" in text or
                "Lista de Videos en el Canal:" in text or
                "Videos Duplicados Encontrados" in text or
                "No se encontraron videos duplicados" in text or
                "Lista de Títulos en el Canal:" in text or
                "Se detectaron las siguientes copias" in text or
                "No hay series duplicadas." in text or
                "Para limpiar este reporte:" in text or
                "Lista de Códigos JAV:" in text or
                "Lista de Actrices:" in text or
                "¡Indexación" in text or
                "Ver Catálogo:" in text or
                "Ver Catálogo de Escenas:" in text or
                "Se ha vaciado la base de datos y el catálogo de este canal" in text or
                "Lista de Comandos Detallada" in text or
                "Información de Mensajes y Desaparición" in text or
                "📂 Control y Ayuda" in text or
                "🌐 Guía interactiva detallada:" in text
            ):
                delete_ids.add(m.id)
                if m.grouped_id:
                    delete_grouped_ids.add(m.grouped_id)
            elif text.strip() == ".":
                delete_ids.add(m.id)
            elif text.strip().lower().startswith(('/r', '/v', '/p', '/elimina_duplicados_especial_miniatura', '/elimina_duplicados_modo_avanzado', '/elimina_duplicados_miniatura', '/duplicados_modo_avanzado', '/duplicados_miniatura', '/duplicados', '/repetidos', '/similares', '/limpiar', '/clean', '/clear', '/elimina_duplicados', '/borrar_duplicados', '/eliminar_mensaje_de_portada', '/elimina_spam_fijar', '/buscar_codigos_jav', '/portada_jav', '/code_duplicado', '/jav_sin_code', '/name_actriz', '/etiquetado_de_actriz', '/etiquetado_actriz', '/lista_de_actriz', '/lista_actriz', '/albun_maker_video', '/album_maker_video', '/albun_maker_imagenes', '/album_maker_imagenes', '/albun_maker', '/album_maker', '/albun_directo_video', '/album_directo_video', '/albun_directo_imagenes', '/album_directo_imagenes', '/albun_directo_imagen', '/album_directo_imagen', '/prime_video', '/prime_imagenes', '/limpiar_catalogo', '/lista', '/start', '/info', '/manga_flow')):
                delete_ids.add(m.id)
                
    # Asegurarnos de borrar TODAS las imágenes de los álbumes marcados
    for m in all_recent:
        if m.grouped_id and m.grouped_id in delete_grouped_ids:
            delete_ids.add(m.id)
            
    if len(delete_ids) > 1:
        # Eliminar mensajes en bloque
        await client.delete_messages(chat_id, list(delete_ids))
    else:
        # Mensaje temporal que se borra solo
        reply = await event.reply("❌ **[Bot Prime]** No se encontró ningún reporte reciente en el canal para limpiar.")
        await asyncio.sleep(4)
        await client.delete_messages(chat_id, [event.id, reply.id])

async def procesar_comando_eliminar_duplicados(event):
    chat_id = event.chat_id
    status_msg = await event.reply("⚙️ **[Bot Prime]** Buscando y eliminando videos duplicados en el canal...")
    
    try:
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', '') or ''
        
        if is_jav_channel(chat_id, chat_title):
            await safe_edit_status(status_msg, "⚙️ **[Bot Prime]** Buscando y eliminando portadas duplicadas en el canal...")
            await procesar_eliminar_duplicados_jav(event, status_msg)
            return

        # 1. Escanear todos los videos del canal
        messages = []
        async for m in client.iter_messages(chat_id):
            if m.document:
                is_video = False
                file_name = ""
                for attr in m.document.attributes:
                    if isinstance(attr, DocumentAttributeVideo):
                        is_video = True
                    elif hasattr(attr, 'file_name') and attr.file_name:
                        file_name = attr.file_name
                
                mime = m.document.mime_type or ""
                if mime.startswith('video/') or file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts')):
                    is_video = True
                
                if is_video:
                    messages.append(m)
                    
        if not messages:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontraron videos en este canal.")
            await asyncio.sleep(5)
            await status_msg.delete()
            try:
                await event.delete()
            except Exception:
                pass
            return

        # 2. Agrupar duplicados por (peso, tiempo)
        dup_groups = {}
        for m in messages:
            duration = 0
            for attr in m.document.attributes:
                if isinstance(attr, DocumentAttributeVideo):
                    duration = attr.duration
                    break
            if not duration and m.file.duration:
                duration = m.file.duration
                
            size = m.document.size or 0
            if size > 0:
                key = (size, duration)
                if key not in dup_groups:
                    dup_groups[key] = []
                dup_groups[key].append(m)
                
        # 3. Identificar cuáles borrar (todos excepto el más antiguo / ID menor)
        ids_to_delete = []
        for (size, duration), msg_list in dup_groups.items():
            if len(msg_list) > 1:
                # Ordenar por ID ascendente (más antiguo primero)
                msg_list.sort(key=lambda x: x.id)
                # El primero se conserva (msg_list[0]), los demás se borran
                for m_copy in msg_list[1:]:
                    ids_to_delete.append(m_copy.id)
                    
        if ids_to_delete:
            # Eliminar mensajes en bloque
            await client.delete_messages(chat_id, ids_to_delete)
            await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Se eliminaron {len(ids_to_delete)} videos duplicados correctamente (conservando los originales).")
        else:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron videos duplicados para borrar.")
            
        await asyncio.sleep(6)
        # Limpiar el comando del usuario y el mensaje de estado
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error al eliminar duplicados: {e}")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass

async def borrar_copia_por_id(event, album_msg_id):
    chat_id = event.chat_id
    
    # Enviar mensaje temporal informando el progreso de la eliminación
    progress_msg = await event.reply("⚙️ **[Bot Prime]** Eliminando copia y sus videos/capítulos asociados...")
    
    try:
        # 1. Obtener mensaje del álbum
        album_msg = await client.get_messages(chat_id, ids=album_msg_id)
        if not album_msg or not album_msg.message:
            await safe_edit_status(progress_msg, "❌ **[Bot Prime]** No se encontró el mensaje original de la copia.")
            await asyncio.sleep(5)
            await progress_msg.delete()
            try:
                await event.delete()
            except Exception:
                pass
            return
            
        raw_title = extract_title_from_caption(album_msg.message)
        series_name = extract_series_name(raw_title)
        clean_series_name = clean_comparison_string(series_name)
        
        if not clean_series_name:
            await safe_edit_status(progress_msg, "❌ **[Bot Prime]** No se pudo determinar el nombre de la serie.")
            await asyncio.sleep(5)
            await progress_msg.delete()
            try:
                await event.delete()
            except Exception:
                pass
            return
            
        # Agregamos el comando del usuario a la lista de mensajes a eliminar
        delete_ids = {album_msg_id, event.id}
        
        # 2. Obtener fotos del mismo álbum (mismo grouped_id)
        if album_msg.grouped_id:
            async for m in client.iter_messages(
                chat_id,
                min_id=album_msg_id - 15,
                max_id=album_msg_id + 15
            ):
                if m.grouped_id == album_msg.grouped_id:
                    delete_ids.add(m.id)
                    
        # 3. Buscar videos cercanos de la misma serie (+/- 30 IDs)
        async for m in client.iter_messages(
            chat_id,
            min_id=album_msg_id - 30,
            max_id=album_msg_id + 30
        ):
            if m.video:
                v_title = get_message_title(m)
                v_series = extract_series_name(v_title)
                if clean_comparison_string(v_series) == clean_series_name:
                    delete_ids.add(m.id)
                    
        # 4. Eliminar los mensajes
        delete_list = list(delete_ids)
        print(f"🗑️ Eliminando mensajes de la copia '{series_name}': {delete_list}")
        await client.delete_messages(chat_id, delete_list)
        
        # 5. Notificar éxito
        await safe_edit_status(progress_msg, f"✅ **[Bot Prime]** La copia de `\"{series_name}\"` y sus videos se eliminaron con éxito.")
        await asyncio.sleep(10)
        await progress_msg.delete()
            
    except Exception as e:
        await safe_edit_status(progress_msg, f"❌ **[Bot Prime]** Error al eliminar: {e}")
        await asyncio.sleep(5)
        await progress_msg.delete()

async def eliminar_mensaje_de_portada(event):
    chat_id = event.chat_id
    
    # Parse scan limit (default None to scan everything)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"⚙️ **[Bot Prime]** Buscando notificaciones de actualización de portada en {limit_desc}...")
    
    try:
        from telethon.tl.types import MessageActionChatEditPhoto, MessageActionChatDeletePhoto
        delete_ids = []
        
        async for m in client.iter_messages(chat_id, limit=limit):
            if m.action and isinstance(m.action, (MessageActionChatEditPhoto, MessageActionChatDeletePhoto)):
                delete_ids.append(m.id)
                
        if delete_ids:
            await client.delete_messages(chat_id, delete_ids)
            await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Se eliminaron {len(delete_ids)} notificaciones de actualización de portada.")
        else:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontró ninguna notificación de actualización de portada.")
            
        await asyncio.sleep(5)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(5)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass

async def elimina_spam_fijar(event):
    chat_id = event.chat_id
    
    # Parse scan limit (default None to scan everything)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"⚙️ **[Bot Prime]** Buscando notificaciones de mensajes fijados en {limit_desc}...")
    
    try:
        from telethon.tl.types import MessageActionPinMessage
        delete_ids = []
        
        async for m in client.iter_messages(chat_id, limit=limit):
            if m.action and isinstance(m.action, MessageActionPinMessage):
                delete_ids.append(m.id)
                
        if delete_ids:
            await client.delete_messages(chat_id, delete_ids)
            await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Se eliminaron {len(delete_ids)} notificaciones de mensajes fijados.")
        else:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontró ninguna notificación de mensajes fijados.")
            
        await asyncio.sleep(5)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(5)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass

async def procesar_repetidos_jav(event, status_msg, chat, limit=None):
    chat_id = event.chat_id
    limit_desc = f"en los últimos {limit} mensajes" if limit else "en todo el historial"
    try:
        total_msgs = limit
        if not total_msgs:
            try:
                total_info = await client.get_messages(chat_id, limit=0)
                total_msgs = total_info.total
            except Exception:
                total_msgs = 0

        messages = []
        count = 0
        last_update = time.time()
        
        # 1. Escanear todos los mensajes del canal
        async for m in client.iter_messages(chat_id, limit=limit):
            count += 1
            messages.append(m)
            
            # Throttling de la actualización de estado para evitar FloodWait
            now = time.time()
            if now - last_update > 4.0:
                pct_str = f" ({int((count / total_msgs) * 100)}%)" if total_msgs else ""
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Escaneando portadas... {count} msgs{pct_str}")
                last_update = now
                
        # 2. Extraer códigos JAV y agrupar por (código, censura) de las portadas (imágenes)
        codes_map = {}
        
        for msg in messages:
            # Procesar únicamente portadas/imágenes
            is_image = False
            if msg.photo:
                is_image = True
            elif msg.document:
                mime = msg.document.mime_type or ""
                if mime.startswith('image/'):
                    is_image = True
            
            if not is_image:
                continue
                    
            text_sources = []
            if msg.message:
                text_sources.append(msg.message)
            if msg.file and msg.file.name:
                text_sources.append(msg.file.name)
                
            full_text = " ".join(text_sources)
            if not full_text:
                continue
                
            matches = JAV_REGEX.findall(full_text)
            if not matches:
                continue
                
            censorship = determine_censorship(full_text)
            if censorship is None:
                censorship = ""  # Sin etiqueta
                
            seen_in_msg = set()
            for raw_code in matches:
                code_upper = raw_code.upper()
                prefix = code_upper.split('-')[0]
                
                # Omitir prefijos de la lista de excluidos o si ya se vio en este mensaje
                if prefix.lower() in EXCLUDED_PREFIXES or code_upper in seen_in_msg:
                    continue
                    
                seen_in_msg.add(code_upper)
                
                key = (code_upper, censorship)
                if key not in codes_map:
                    codes_map[key] = []
                codes_map[key].append(msg)

        if not codes_map:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontraron portadas con códigos JAV en los mensajes analizados.")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return

        # 3. Procesar y ordenar duplicados
        channel_id_str = str(chat.id).replace("-100", "")
        is_public = bool(getattr(chat, 'username', None))
        
        duplicate_groups = []
        for (code, censorship), msgs_list in codes_map.items():
            if len(msgs_list) > 1:
                # Ordenar por ID ascendente (más antiguo primero)
                msgs_list.sort(key=lambda x: x.id)
                duplicate_groups.append(((code, censorship), msgs_list))
                
        # Ordenar alfabéticamente por código y censura
        duplicate_groups.sort(key=lambda x: (x[0][0], x[0][1]))

        # Eliminar el mensaje de búsqueda inicial
        await status_msg.delete()

        # 4. Enviar reporte de duplicados
        if duplicate_groups:
            dup_html = []
            for (code, censorship), msgs_list in duplicate_groups:
                censorship_label = f" ({censorship})" if censorship else ""
                
                group_html = []
                for msg_idx, msg in enumerate(msgs_list):
                    link = f"https://t.me/{chat.username}/{msg.id}" if is_public else f"https://t.me/c/{channel_id_str}/{msg.id}"
                    status_tag = "original" if msg_idx == 0 else "duplicado"
                    line_text = f"<li>({msg_idx+1}) <a href=\"{link}\">{code}{censorship_label} {status_tag}</a></li>"
                    group_html.append(line_text)
                    
                dup_html.append("<ul>" + "".join(group_html) + "</ul>")

            html_dups = "<p><b>Códigos Duplicados Detectados en Portadas:</b></p>" + "".join(dup_html)
            telegraph_dup_url = await create_telegraph_page("Reporte de Portadas JAV", html_dups)
            
            text_reply = f"⚠️ <b>Se detectaron portadas JAV duplicadas.</b>\n\n"
            if telegraph_dup_url:
                text_reply += f"📄 <a href='{telegraph_dup_url}'>Ver Reporte de Duplicados en Telegraph</a>\n\n"
                
            text_reply += "🧹 <b>Para limpiar este reporte:</b> <code>/limpiar</code> | <b>Para borrar las portadas duplicadas:</b> <code>/elimina_duplicados</code>"
            
            await event.respond(text_reply + "\u200b", parse_mode='html', link_preview=True)
        else:
            await event.respond("✅ **No se encontraron códigos duplicados en las portadas.**\n\n🧹 **Para limpiar este reporte:** <code>/limpiar</code>\u200b", parse_mode='html', link_preview=False)
            
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(10)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass

async def procesar_eliminar_duplicados_jav(event, status_msg):
    chat_id = event.chat_id
    try:
        # 1. Escanear todos los mensajes del canal
        messages = []
        async for m in client.iter_messages(chat_id):
            messages.append(m)

        # 2. Extraer códigos JAV y agrupar por (código, censura) de las portadas (imágenes)
        codes_map = {}
        
        for msg in messages:
            # Procesar únicamente portadas/imágenes
            is_image = False
            if msg.photo:
                is_image = True
            elif msg.document:
                mime = msg.document.mime_type or ""
                if mime.startswith('image/'):
                    is_image = True
            
            if not is_image:
                continue
                    
            text_sources = []
            if msg.message:
                text_sources.append(msg.message)
            if msg.file and msg.file.name:
                text_sources.append(msg.file.name)
                
            full_text = " ".join(text_sources)
            if not full_text:
                continue
                
            matches = JAV_REGEX.findall(full_text)
            if not matches:
                continue
                
            censorship = determine_censorship(full_text)
            if censorship is None:
                censorship = ""  # Sin etiqueta
                
            seen_in_msg = set()
            for raw_code in matches:
                code_upper = raw_code.upper()
                prefix = code_upper.split('-')[0]
                
                # Omitir prefijos de la lista de excluidos o si ya se vio en este mensaje
                if prefix.lower() in EXCLUDED_PREFIXES or code_upper in seen_in_msg:
                    continue
                    
                seen_in_msg.add(code_upper)
                
                key = (code_upper, censorship)
                if key not in codes_map:
                    codes_map[key] = []
                codes_map[key].append(msg)

        # 3. Identificar cuáles borrar (todos excepto el más antiguo / ID menor de cada grupo duplicado)
        ids_to_delete = []
        for (code, censorship), msgs_list in codes_map.items():
            if len(msgs_list) > 1:
                # Ordenar por ID ascendente (más antiguo primero)
                msgs_list.sort(key=lambda x: x.id)
                # El primero se conserva, los demás se borran
                for m_copy in msgs_list[1:]:
                    ids_to_delete.append(m_copy.id)

        if ids_to_delete:
            # Eliminar mensajes en bloque
            await client.delete_messages(chat_id, ids_to_delete)
            await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Se eliminaron {len(ids_to_delete)} portadas duplicadas correctamente (conservando las originales).")
        else:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** No se encontraron portadas duplicadas para borrar.")
            
        await asyncio.sleep(6)
        # Limpiar el comando del usuario y el mensaje de estado
        await client.delete_messages(chat_id, [event.id, status_msg.id])

    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error al eliminar portadas duplicadas: {e}")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
