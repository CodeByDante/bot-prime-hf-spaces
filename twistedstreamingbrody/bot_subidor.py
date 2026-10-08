import asyncio
import uuid
import time
from telethon import events, Button
from telethon.tl.types import KeyboardButtonSimpleWebView, KeyboardButtonWebView
from google.cloud.firestore_v1.base_query import FieldFilter
from core import *

@client.on(events.NewMessage(pattern='/(start|subir|subir_pelicula|subir_serie)$'))
async def start_subir_handler(event):
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    if user_modes.get(chat_id) != 'subidor': return
    chat_id = event.chat_id
    if False:
        await event.respond("🛠️ **Estás en Modo Editor.**\nPor favor, usa `/desactivar_modo_editor` para salir del editor y usar los comandos normales.")
        return
    
    if chat_id not in active_tasks:
        active_tasks[chat_id] = []
        
    current_task = asyncio.current_task()
    current_task.is_uploading = False
    
    remaining_tasks = []
    for old_task in active_tasks[chat_id]:
        if not old_task.done():
            if getattr(old_task, 'is_uploading', False):
                remaining_tasks.append(old_task)
            else:
                old_task.cancel()
                try:
                    await asyncio.sleep(0.1)
                except: pass
                
    active_tasks[chat_id] = remaining_tasks
    active_tasks[chat_id].append(current_task)
    
    try:
        async with client.conversation(chat_id, timeout=600, exclusive=False) as conv:
            cmd = event.text.strip().lower()
            while True:
                try:
                    if cmd == '/subir_pelicula':
                        await handle_movie_upload(conv)
                        break
                    elif cmd == '/subir_serie':
                        await handle_series_upload(conv)
                        break

                    msg_text = "📁 Bienvenido a **Twisted Streaming Brody**.\nElige una opción:"
                    botones = [
                        [Button.inline("📁 Subir Película", b"type_movie"), Button.inline("📁 Subir Serie", b"type_series")]
                    ]
                    
                    if cmd == '/start':
                        photos = await client.get_profile_photos('me', limit=1)
                        if photos:
                            msg = await conv.send_message(msg_text, file=photos[0], buttons=botones)
                        else:
                            msg = await conv.send_message(msg_text, buttons=botones)
                    else:
                        msg = await conv.send_message(msg_text, buttons=botones)
                        
                    cmd = "" # Reset cmd
                    
                    while True:
                        press = await wait_for_message_or_callback(conv, timeout=3600)
                        if isinstance(press, events.CallbackQuery.Event):
                            if press.data in [b"type_movie", b"type_series"]:
                                await press.answer()
                                try:
                                    await msg.edit(buttons=None)
                                except: pass
                                
                                if press.data == b"type_movie":
                                    await handle_movie_upload(conv)
                                elif press.data == b"type_series":
                                    await handle_series_upload(conv)
                                break
                            else:
                                await press.answer("Botón expirado", alert=True)
                        elif getattr(press, 'text', '') in ['/start', '/subir', '/subir_pelicula', '/subir_serie']:
                            cmd = press.text
                            break
                    break
                except CancelUploadException:
                    cmd = "/subir"
                    continue
                except asyncio.CancelledError:
                    break
    finally:
        if current_task in active_tasks.get(chat_id, []):
            active_tasks[chat_id].remove(current_task)
            if not active_tasks[chat_id]:
                del active_tasks[chat_id]

async def handle_movie_upload(conv):
    # 1. Video
    await conv.send_message("📁 **Paso 1:** Envía el **video** (o el archivo) de la película:")
    msg_video = await conv.get_response()
    
    is_video = False
    if msg_video and getattr(msg_video, 'media', None):
        if getattr(msg_video, 'video', None):
            is_video = True
        elif getattr(msg_video, 'document', None):
            mime = getattr(msg_video.file, 'mime_type', '') if hasattr(msg_video, 'file') else ''
            if mime.startswith('video/'):
                is_video = True
            else:
                for attr in msg_video.document.attributes:
                    if hasattr(attr, 'file_name'):
                        import os
                        ext = os.path.splitext(attr.file_name)[1].lower()
                        if ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.ts', '.m4v']:
                            is_video = True
                        break

    if not is_video:
        await conv.send_message("📁 No enviaste un video válido. Debes enviar un video normal o un archivo de video (documento). Las imágenes no son aceptadas. Abortando proceso.")
        print("📁 Intento de subida fallido: No se recibió un video o documento válido.")
        return

    doc_name = ""
    video_caption = msg_video.raw_text if getattr(msg_video, 'raw_text', None) else ""
    if getattr(msg_video, 'file', None) and getattr(msg_video.file, 'name', None):
        import os
        doc_name = os.path.splitext(msg_video.file.name)[0]
    elif hasattr(msg_video.media, 'document'):
        for attr in msg_video.media.document.attributes:
            if hasattr(attr, 'file_name'):
                import os
                doc_name = os.path.splitext(attr.file_name)[0]
                break

    # 2. Título
    uid_title = str(uuid.uuid4()).encode()
    buttons_title = []
    if doc_name:
        buttons_title.append([Button.inline(f"📁 Usar nombre del archivo: {doc_name[:30]}", uid_title)])
    
    msg_t = await conv.send_message("📁 **Paso 2:** Escribe el **Título** de la película:", buttons=buttons_title if buttons_title else None)
    title = ""
    while True:
        event = await wait_for_message_or_callback(conv, timeout=300)
        if isinstance(event, events.CallbackQuery.Event):
            if doc_name and event.data == uid_title:
                await event.answer("Título seleccionado")
                title = doc_name
                await msg_t.edit(f"📁 Título: **{title}**", buttons=None)
                break
            else:
                await event.answer("Botón expirado", alert=True)
        else:
            title = event.raw_text
            if buttons_title:
                await msg_t.edit(buttons=None)
            break

    print(f"📁 Iniciando carga de película: {title}")

    # 3. Descripción
    uid_desc = str(uuid.uuid4()).encode()
    uid_skip = str(uuid.uuid4()).encode()
    buttons_desc = []
    if video_caption:
        buttons_desc.append([Button.inline("📁 Usar descripción del video", uid_desc)])
    buttons_desc.append([Button.inline("📁 Omitir", uid_skip)])

    msg_d = await conv.send_message("📁 **Paso 3:** Escribe la **Descripción**:", buttons=buttons_desc)
    description = ""
    while True:
        event = await wait_for_message_or_callback(conv, timeout=300)
        if isinstance(event, events.CallbackQuery.Event):
            if video_caption and event.data == uid_desc:
                await event.answer("Descripción seleccionada")
                description = video_caption
                await msg_d.edit("📁 Descripción obtenida del video.", buttons=None)
                break
            elif event.data == uid_skip:
                await event.answer("Omitido")
                description = ""
                await msg_d.edit("📁 Descripción: (Omitida)", buttons=None)
                break
            else:
                await event.answer("Botón expirado", alert=True)
        else:
            description = event.raw_text
            await msg_d.edit(buttons=None)
            break

    # 4. Portada
    cover_url = ""
    uid_skip = str(uuid.uuid4()).encode()
    uid_cancel = str(uuid.uuid4()).encode()
    
    msg_c = await conv.send_message("📁 **Paso 4:** Envía la **Portada** (solo como imagen):", buttons=[
        [Button.inline("📁 Omitir", uid_skip)],
        [Button.inline("❌ Cancelar Subida", uid_cancel)]
    ])
    
    resp_cover = None
    while True:
        event = await wait_for_message_or_callback(conv, timeout=300)
        if isinstance(event, events.CallbackQuery.Event):
            if event.data == uid_skip:
                await event.answer("Omitido")
                await msg_c.edit("📁 Portada: (Omitida)", buttons=None)
                break
            elif event.data == uid_cancel:
                await event.answer("Cancelado")
                await msg_c.edit("📁 **Subida cancelada.**", buttons=None)
                raise CancelUploadException()
            else:
                await event.answer("Botón expirado", alert=True)
        else:
            if getattr(event, 'photo', None):
                await msg_c.edit("📁 Subiendo portada...", buttons=None)
                cover_url = await upload_to_imgbb(event.photo)
                resp_cover = event
                break
            else:
                await conv.send_message("📁 Por favor, envía una IMAGEN, o presiona Omitir/Cancelar.")

    async def progress_callback(current, total):
        porcentaje = (current / total) * 100
        print(f"  ⬆️ Subiendo: {porcentaje:.1f}% ({current}/{total} bytes)")

    print(f"📦 Video recibido. Tamaño estimado: {getattr(msg_video.file, 'size', 'desconocido')} bytes")
    status_msg = await conv.send_message("📁 **Subiendo video al canal...** (Mira la consola para ver el progreso)")
    
    try:
        asyncio.current_task().is_uploading = True
        # Formatear el mensaje para el canal
        caption = f"**Twisted Streaming Brody Data**\n\n📁 **Película:** {title}\n📁 {description}"
        
        print(f"📤 Enviando al canal {CHANNEL_ID}...")
        
        if resp_cover and getattr(resp_cover, 'photo', None):
            try:
                await client.send_file(CHANNEL_ID, resp_cover.photo, caption=f"📁 **Portada Película:** {title}")
            except Exception as e:
                print(f"Error enviando portada de película al canal: {e}")
                
        sent_to_channel = await client.send_file(
            CHANNEL_ID, 
            msg_video.media, 
            caption=caption,
            progress_callback=progress_callback
        )
        
        print(f"📁 Enviado al canal. ID: {sent_to_channel.id}")
        clean_channel_id = str(CHANNEL_ID).replace("-100", "")
        file_url = f"https://t.me/c/{clean_channel_id}/{sent_to_channel.id}"

        print("🗄️ Guardando en Firebase...")
        # Guardar en Firestore con todos los campos observados en tu consola
        db.collection('videos').add({
            "title": title, 
            "description": description, 
            "section": "peliculas",
            "is_folder": False, 
            "folder_id": "", # Sin nulls para evitar errores en React
            "video_url": file_url, 
            "telegram_file_id": str(sent_to_channel.id),
            "thumbnail_url": "", 
            "cover_url": cover_url, 
            "thumbnail_position": "50% center",
            "episode": 0,
            "views": 0,
            "rating": 0,
            "categories": [], 
            "servers": [file_url],
            "status": "active",
            "is_public": True,
            "created_at": firestore.SERVER_TIMESTAMP, 
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        print("🎉 Guardado en Firebase exitoso.")
        await status_msg.edit("📁 **¡Película registrada y enviada correctamente!**")
    except Exception as e:
        print(f"📁 ERROR CRÍTICO: {e}")
        await status_msg.edit(f"📁 **Error al procesar:** {e}")

async def handle_series_upload(conv):
    series_title = ""
    videos = []
    naming_strategy = "title"
    manual_prefix = ""
    ep_titles = []
    desc_strategy = "manual"
    desc_text = ""
    cover_url = ""
    resp_cover = None

    step = 1
    while step <= 4:
        if step == 1:
            await conv.send_message("📁 **Paso 1:** Escribe el título general de la Serie (`Ej: The Last of Us, Breaking Bad, Invencible, etc.`):")
            while True:
                title_msg = await wait_for_message_or_callback(conv, timeout=300)
                if isinstance(title_msg, events.CallbackQuery.Event):
                    await title_msg.answer("Por favor, escribe un texto.", alert=True)
                elif getattr(title_msg, 'raw_text', getattr(title_msg, 'text', None)):
                    series_title = getattr(title_msg, 'raw_text', title_msg.text)
                    step = 2
                    break
                    
        elif step == 2:
            uid_done = str(uuid.uuid4()).encode()
            uid_back = str(uuid.uuid4()).encode()
            msg_v = await conv.send_message(
                f"📁 **Paso 2:** Envía los videos de los capítulos. Puedes enviar varios de una vez.\n\n"
                f"Esperando a más videos... ({len(videos)} recibidos)",
                buttons=[
                    [Button.inline("📁 Terminar y confirmar", uid_done)],
                    [Button.inline("⬅️ Atrás (Editar Título)", uid_back)]
                ]
            )
            
            debounce_task = None
            async def update_button():
                await asyncio.sleep(0.8)
                nonlocal msg_v
                try:
                    await msg_v.delete()
                except Exception:
                    pass
                msg_v = await conv.send_message(
                    f"📁 **Paso 2:** Envía los videos de los capítulos.\n\n"
                    f"Esperando a más videos... ({len(videos)} recibidos)",
                    buttons=[
                        [Button.inline("📁 Terminar y confirmar", uid_done)],
                        [Button.inline("⬅️ Atrás (Editar Título)", uid_back)]
                    ]
                )

            async def video_receiver(e):
                is_video = False
                if getattr(e, 'media', None):
                    if getattr(e, 'video', None):
                        is_video = True
                    elif getattr(e, 'document', None):
                        mime = getattr(e.file, 'mime_type', '') if hasattr(e, 'file') else ''
                        if mime.startswith('video/'):
                            is_video = True
                        else:
                            for attr in e.document.attributes:
                                if hasattr(attr, 'file_name'):
                                    import os
                                    ext = os.path.splitext(attr.file_name)[1].lower()
                                    if ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.ts', '.m4v']:
                                        is_video = True
                                    break
                                    
                if is_video:
                    videos.append(e)
                    nonlocal debounce_task
                    if debounce_task:
                        debounce_task.cancel()
                    debounce_task = asyncio.create_task(update_button())

            client.add_event_handler(video_receiver, events.NewMessage(chats=conv.chat_id, incoming=True))
            
            try:
                while True:
                    event = await wait_for_message_or_callback(conv, timeout=3600)
                    if isinstance(event, events.CallbackQuery.Event):
                        if event.data == uid_done:
                            if not videos:
                                await event.answer("No has enviado ningún video aún.", alert=True)
                            else:
                                await event.answer("Videos confirmados")
                                if debounce_task:
                                    debounce_task.cancel()
                                await msg_v.edit(f"📁 Se registraron {len(videos)} videos en total.", buttons=None)
                                step = 3
                                break
                        elif event.data == uid_back:
                            await event.answer("Volviendo atrás")
                            if debounce_task:
                                debounce_task.cancel()
                            await msg_v.edit("📁 Volviendo al Paso 1...", buttons=None)
                            step = 1
                            break
            finally:
                client.remove_event_handler(video_receiver, events.NewMessage(chats=conv.chat_id, incoming=True))
                
        elif step == 3:
            uid_title = str(uuid.uuid4()).encode()
            uid_auto = str(uuid.uuid4()).encode()
            uid_file = str(uuid.uuid4()).encode()
            uid_unique = str(uuid.uuid4()).encode()
            uid_manual = str(uuid.uuid4()).encode()
            uid_back = str(uuid.uuid4()).encode()
            
            buttons = [
                [Button.inline("📁 Título General + Capítulo X", uid_title)],
                [Button.inline("📁 Personalización Automática", uid_auto)],
                [Button.inline("📁 Nombres Originales de Archivos", uid_file)],
                [Button.inline("📁 Nombramiento Manual Masivo", uid_manual)]
            ]
            if len(videos) == 1:
                buttons.append([Button.inline("📁 Personalizado Único (1 cap)", uid_unique)])
            buttons.append([Button.inline("⬅️ Atrás (Añadir más videos)", uid_back)])
            
            msg_n = await conv.send_message(
                "📁 **Paso 3:** ¿Qué nombre llevarán los capítulos? Elige una opción:\n\n"
                "🔹 **Título General + Capítulo X:**\n"
                f"Usa el título de la serie y lo enumera. `Ej: {series_title} - Capítulo 1`\n\n"
                "🔹 **Personalización Automática:**\n"
                "Te pedirá un nombre base y lo enumerará. `Ej: Tu Texto - Capítulo 1`\n\n"
                "🔹 **Nombres Originales:**\n"
                "Mantiene el nombre exacto de cada archivo. `Ej: video_2026.mp4`\n\n"
                "🔹 **Nombramiento Manual Masivo:**\n"
                "Te enviará una plantilla vacía para que nombres todos a la vez.\n\n"
                "💡 Si enviaste 1 solo video, aparecerá la opción `Personalizado Único` para usar un nombre exacto sin números.\n",
                buttons=buttons
            )
            
            strategy = None
            while True:
                event = await wait_for_message_or_callback(conv, timeout=300)
                if isinstance(event, events.CallbackQuery.Event):
                    if event.data == uid_title:
                        strategy = "title"
                        await msg_n.edit(f"📁 Título General + Capítulo X", buttons=None)
                        break
                    elif event.data == uid_auto:
                        strategy = "auto"
                        await msg_n.edit("📁 Personalización Automática", buttons=None)
                        break
                    elif event.data == uid_file:
                        strategy = "file"
                        await msg_n.edit("📁 Nombres Originales de Archivos", buttons=None)
                        break
                    elif event.data == uid_manual:
                        strategy = "manual_mass"
                        await msg_n.edit("📁 Nombramiento Manual Masivo", buttons=None)
                        break
                    elif event.data == uid_unique and len(videos) == 1:
                        strategy = "unique"
                        await msg_n.edit("📁 Personalizado Único", buttons=None)
                        break
                    elif event.data == uid_back:
                        strategy = "back"
                        await event.answer("Volviendo atrás")
                        await msg_n.edit("📁 Volviendo al Paso 2...", buttons=None)
                        break
                    else:
                        await event.answer("Botón expirado", alert=True)
                else:
                    await msg_n.delete()
                    msg_n = await conv.send_message("📁 Por favor, usa los botones:", buttons=buttons)

            if strategy == "back":
                step = 2
                continue
                
            manual_prefix = ""
            if strategy == "auto":
                await conv.send_message("Escribe el nombre base para los capítulos (se enumerarán solos):")
                while True:
                    resp = await wait_for_message_or_callback(conv, timeout=300)
                    if not isinstance(resp, events.CallbackQuery.Event):
                        manual_prefix = resp.raw_text.strip()
                        break
            elif strategy == "unique":
                await conv.send_message("Escribe el nombre exacto que tendrá este capítulo (SIN números automáticos):")
                while True:
                    resp = await wait_for_message_or_callback(conv, timeout=300)
                    if not isinstance(resp, events.CallbackQuery.Event):
                        manual_prefix = resp.raw_text.strip()
                        break

            ep_titles = []
            for i, video_msg in enumerate(videos):
                if strategy == "title":
                    ep_titles.append(f"{series_title} - Capítulo {i+1}")
                elif strategy == "auto":
                    ep_titles.append(f"{manual_prefix} - Capítulo {i+1}")
                elif strategy == "unique":
                    ep_titles.append(manual_prefix)
                elif strategy == "manual_mass":
                    ep_titles.append("")
                elif strategy == "file":
                    doc_name = "Episodio"
                    if getattr(video_msg, 'file', None) and getattr(video_msg.file, 'name', None):
                        import os
                        doc_name = os.path.splitext(video_msg.file.name)[0]
                    elif hasattr(video_msg.media, 'document'):
                        for attr in video_msg.media.document.attributes:
                            if hasattr(attr, 'file_name'):
                                import os
                                doc_name = os.path.splitext(attr.file_name)[0]
                                break
                    ep_titles.append(doc_name)
            
            if strategy == "manual_mass":
                step = 3.3
            else:
                step = 3.2

        elif step == 3.2:
            uid_confirm = str(uuid.uuid4()).encode()
            uid_edit = str(uuid.uuid4()).encode()
            uid_back = str(uuid.uuid4()).encode()
            
            preview = ""
            for i, title in enumerate(ep_titles[:20]):
                preview += f"({i+1}) {title}\n"
            if len(ep_titles) > 20:
                preview += f"... y {len(ep_titles) - 20} más.\n"
                
            msg_p = await conv.send_message(
                f"📝 **Vista Previa de los Nombres:**\n\n{preview}\n¿Qué deseas hacer?",
                buttons=[
                    [Button.inline("✅ Confirmar Nombres", uid_confirm)],
                    [Button.inline("✏️ Editar Nombres (Plantilla)", uid_edit)],
                    [Button.inline("⬅️ Atrás (Elegir otro formato)", uid_back)]
                ]
            )
            
            while True:
                event = await wait_for_message_or_callback(conv, timeout=300)
                if isinstance(event, events.CallbackQuery.Event):
                    if event.data == uid_confirm:
                        await msg_p.edit("✅ Nombres confirmados.", buttons=None)
                        step = 3.5
                        break
                    elif event.data == uid_edit:
                        await msg_p.edit("✏️ Modo edición...", buttons=None)
                        step = 3.3
                        break
                    elif event.data == uid_back:
                        await msg_p.edit("📁 Volviendo a formatos...", buttons=None)
                        step = 3
                        break
                    else:
                        await event.answer("Botón expirado", alert=True)
                else:
                    await msg_p.delete()
                    msg_p = await conv.send_message("📁 Por favor, usa los botones:", buttons=[
                        [Button.inline("✅ Confirmar Nombres", uid_confirm)],
                        [Button.inline("✏️ Editar Nombres (Plantilla)", uid_edit)],
                        [Button.inline("⬅️ Atrás (Elegir otro formato)", uid_back)]
                    ])

        elif step == 3.3:
            template = ""
            for i, title in enumerate(ep_titles):
                template += f"{{{i+1}}} {title}\n"
            
            await conv.send_message(
                "📝 **EDICIÓN MANUAL**\n\n"
                "1. Copia el siguiente mensaje.\n"
                "2. Pégalo en el chat y edita los nombres como desees.\n"
                "3. Envíamelo.\n\n"
                "⚠️ **NO borres los números entre llaves `{ }`**"
            )
            await conv.send_message(f"```{template}```")
            
            while True:
                resp = await wait_for_message_or_callback(conv, timeout=3600)
                if isinstance(resp, events.CallbackQuery.Event):
                    await resp.answer("Botón inválido.", alert=True)
                    continue
                    
                new_text = resp.raw_text
                import re
                matches = re.findall(r'\{(\d+)\}\s*(.*)', new_text)
                
                if not matches:
                    await conv.send_message("❌ No se detectó el formato correcto. Recuerda no borrar las llaves { }.")
                    continue
                    
                for idx_str, new_title in matches:
                    try:
                        idx = int(idx_str) - 1
                        if 0 <= idx < len(ep_titles):
                            if new_title.strip():
                                ep_titles[idx] = new_title.strip()
                    except:
                        pass
                
                await conv.send_message("✅ Nombres actualizados.")
                step = 3.2
                break
                    
        elif step == 3.5:
            uid_desc_video = str(uuid.uuid4()).encode()
            uid_skip = str(uuid.uuid4()).encode()
            uid_back = str(uuid.uuid4()).encode()
            msg_d = await conv.send_message(
                "📁 **Paso 3.5:** Escribe una **Descripción** (se usará la misma para todos los capítulos).\n\n"
                "Opcional: puedes extraer la descripción original de cada video, o simplemente omitir este paso.",
                buttons=[
                    [Button.inline("📁 Usar descripción de cada video", uid_desc_video)],
                    [Button.inline("📁 Omitir", uid_skip)],
                    [Button.inline("⬅️ Atrás (Editar Nombre Capítulos)", uid_back)]
                ]
            )
            
            while True:
                event = await wait_for_message_or_callback(conv, timeout=300)
                if isinstance(event, events.CallbackQuery.Event):
                    if event.data == uid_desc_video:
                        desc_strategy = "video"
                        await msg_d.edit("📁 Descripción: **Se usará la de cada video**", buttons=None)
                        step = 4
                        break
                    elif event.data == uid_skip:
                        desc_strategy = "skip"
                        await msg_d.edit("📁 Descripción: **(Omitida)**", buttons=None)
                        step = 4
                        break
                    elif event.data == uid_back:
                        await event.answer("Volviendo atrás")
                        await msg_d.edit("📁 Volviendo al Paso 3...", buttons=None)
                        step = 3
                        break
                    else:
                        await event.answer("Botón expirado", alert=True)
                else:
                    desc_strategy = "manual"
                    desc_text = event.raw_text
                    await msg_d.edit(f"📁 Descripción: **{desc_text[:30]}...**", buttons=None)
                    step = 4
                    break

        elif step == 4:
            uid_skip = str(uuid.uuid4()).encode()
            uid_back = str(uuid.uuid4()).encode()
            uid_cancel = str(uuid.uuid4()).encode()
            
            msg_c = await conv.send_message(
                "📁 **Paso 4:** Envía la **Portada** de la serie (solo como imagen):",
                buttons=[
                    [Button.inline("📁 Omitir", uid_skip)],
                    [Button.inline("⬅️ Atrás (Editar Descripción)", uid_back)],
                    [Button.inline("❌ Cancelar Subida", uid_cancel)]
                ]
            )
            
            while True:
                event = await wait_for_message_or_callback(conv, timeout=300)
                if isinstance(event, events.CallbackQuery.Event):
                    if event.data == uid_skip:
                        await event.answer("Omitido")
                        await msg_c.edit("📁 Portada: **(Omitida)**", buttons=None)
                        resp_cover = None
                        cover_url = ""
                        step = 5
                        break
                    elif event.data == uid_back:
                        await event.answer("Volviendo atrás")
                        await msg_c.edit("📁 Volviendo al Paso 3.5...", buttons=None)
                        step = 3.5
                        break
                    elif event.data == uid_cancel:
                        await event.answer("Cancelado")
                        await msg_c.edit("📁 **Subida cancelada.**", buttons=None)
                        raise CancelUploadException()
                    else:
                        await event.answer("Botón expirado", alert=True)
                elif getattr(event, 'photo', None):
                    await msg_c.edit("📁 Subiendo portada...", buttons=None)
                    cover_url = await upload_to_imgbb(event.photo)
                    resp_cover = event
                    step = 5
                    break
                else:
                    await conv.send_message("📁 Por favor, envía una IMAGEN, o usa los botones.")

    # 5. Guardado en Firebase y reenvío
    status_msg = await conv.send_message("📁 **Procesando y subiendo los capítulos...**")
    try:
        asyncio.current_task().is_uploading = True
        if resp_cover and getattr(resp_cover, 'photo', None):
            try:
                await client.send_file(CHANNEL_ID, resp_cover.photo, caption=f"📁 **Portada Serie:** {series_title}")
            except Exception as e:
                print(f"Error enviando portada de serie al canal: {e}")

        # Buscar serie existente para asegurar nombre único
        original_title = series_title
        counter = 1
        
        while True:
            series_query = db.collection('videos').where(filter=FieldFilter('is_folder', '==', True)).where(filter=FieldFilter('title', '==', series_title)).get()
            if series_query:
                counter += 1
                series_title = f"{original_title} v{counter}"
            else:
                break

        _, doc_ref = db.collection('videos').add({
            "title": series_title, 
            "section": "series", 
            "is_folder": True,
            "thumbnail_url": cover_url, 
            "categories": [],
            "created_at": firestore.SERVER_TIMESTAMP, 
            "updated_at": firestore.SERVER_TIMESTAMP
        })
        series_id = doc_ref.id

        for i, video_msg in enumerate(videos):
            current_num = i + 1
            
            # Nombre
            ep_title = ep_titles[i] if i < len(ep_titles) else f"Capítulo {current_num}"

            # Descripción
            if desc_strategy == "video":
                ep_desc = video_msg.raw_text if getattr(video_msg, 'raw_text', None) else ""
            elif desc_strategy == "skip":
                ep_desc = ""
            else:
                ep_desc = desc_text

            await status_msg.edit(f"📁 Subiendo: **{ep_title}** ({i+1}/{len(videos)})")

            caption = f"**Twisted Streaming Brody Data**\n\n📁 **Serie:** {series_title}\n📁 **Episodio:** {ep_title}"
            if ep_desc:
                caption += f"\n📁 {ep_desc}"
            
            sent_to_channel = await client.send_file(CHANNEL_ID, video_msg.media, caption=caption)
            clean_channel_id = str(CHANNEL_ID).replace("-100", "")
            file_url = f"https://t.me/c/{clean_channel_id}/{sent_to_channel.id}"

            db.collection('videos').add({
                "title": ep_title, 
                "section": "series",
                "is_folder": False, 
                "folder_id": series_id,
                "episode": current_num,
                "season": 1,
                "video_url": file_url, 
                "telegram_file_id": str(sent_to_channel.id),
                "description": ep_desc,
                "thumbnail_url": "",
                "cover_url": "",
                "views": 0,
                "rating": 0,
                "status": "active",
                "is_public": True,
                "categories": [],
                "servers": [file_url],
                "created_at": firestore.SERVER_TIMESTAMP, 
                "updated_at": firestore.SERVER_TIMESTAMP
            })

        await status_msg.edit(f"📁 **¡Completado! {len(videos)} capítulos de '{series_title}' se han subido con éxito.**")

    except Exception as e:
        print(f"📁 Error al procesar serie: {e}")
        await status_msg.edit(f"📁 **Error al subir los capítulos:** {e}")



