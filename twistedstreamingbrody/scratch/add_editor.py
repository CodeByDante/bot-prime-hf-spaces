import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

if "editor_mode_active = {}" not in code:
    old_start = """active_tasks = {}

@client.on(events.NewMessage(pattern='/(start|subir|subir_pelicula|subir_serie)$'))
async def start_subir_handler(event):
    chat_id = event.chat_id"""

    new_start = """active_tasks = {}
editor_mode_active = {}

@client.on(events.NewMessage(pattern='/(start|subir|subir_pelicula|subir_serie)$'))
async def start_subir_handler(event):
    chat_id = event.chat_id
    if editor_mode_active.get(chat_id, False):
        await event.respond("🛠️ **Estás en Modo Editor.**\\nPor favor, usa `/desactivar_modo_editor` para salir del editor y usar los comandos normales.")
        return"""
    code = code.replace(old_start, new_start)

editor_logic = """
# --- MODO EDITOR ---
@client.on(events.NewMessage(pattern='/(activar_modo_editor)$'))
async def enable_editor(event):
    chat_id = event.chat_id
    editor_mode_active[chat_id] = True
    await handle_editor_mode(event)

@client.on(events.NewMessage(pattern='/(desactivar_modo_editor)$'))
async def disable_editor(event):
    chat_id = event.chat_id
    editor_mode_active[chat_id] = False
    await event.respond("✅ **Modo editor desactivado.** Ya puedes usar los comandos normales.")

async def handle_editor_mode(event):
    chat_id = event.chat_id
    async with client.conversation(chat_id, timeout=3600, exclusive=False) as conv:
        try:
            while editor_mode_active.get(chat_id, False):
                msg = await conv.send_message(
                    "🛠️ **Modo Editor Activado**\\n\\n¿Qué deseas gestionar?",
                    buttons=[
                        [Button.inline("🎬 Gestionar Películas", b"ed_mov")],
                        [Button.inline("📺 Gestionar Series", b"ed_ser")],
                        [Button.inline("❌ Salir del Editor", b"ed_exit")]
                    ]
                )
                
                resp = await wait_for_message_or_callback(conv, timeout=3600)
                if getattr(resp, 'raw_text', '') == '/desactivar_modo_editor':
                    break

                if isinstance(resp, events.CallbackQuery.Event):
                    await resp.answer()
                    await msg.edit(buttons=None)
                    
                    if resp.data == b"ed_exit":
                        editor_mode_active[chat_id] = False
                        await conv.send_message("✅ **Modo editor desactivado.**")
                        break
                    elif resp.data == b"ed_mov":
                        await handle_editor_movie_search(conv)
                    elif resp.data == b"ed_ser":
                        await handle_editor_series_search(conv)
        except Exception as e:
            print("Editor error:", e)

async def handle_editor_movie_search(conv):
    uid_back = str(uuid.uuid4()).encode()
    msg = await conv.send_message("🔍 Escribe el nombre de la **película** que deseas buscar:", buttons=[[Button.inline("⬅️ Cancelar", uid_back)]])
    
    resp = await wait_for_message_or_callback(conv, timeout=300)
    if isinstance(resp, events.CallbackQuery.Event) and resp.data == uid_back:
        await resp.answer("Cancelado")
        await msg.edit("Búsqueda cancelada.", buttons=None)
        return
        
    query = resp.raw_text.strip()
    await msg.delete()
    
    movies_ref = db.collection('videos').where(filter=FieldFilter('section', '==', 'peliculas')).get()
    results = [m for m in movies_ref if query.lower() in m.to_dict().get('title', '').lower()]
    
    if not results:
        await conv.send_message("❌ No se encontraron películas con ese nombre.")
        return
        
    results = results[:10]
    buttons = []
    for r in results:
        data = r.to_dict()
        buttons.append([Button.inline(f"🎬 {data.get('title')[:30]}", f"ed_m_{r.id}".encode('utf-8'))])
    
    buttons.append([Button.inline("⬅️ Volver", b"ed_back")])
    
    msg_res = await conv.send_message("📌 **Resultados (Películas):**", buttons=buttons)
    resp_res = await wait_for_message_or_callback(conv, timeout=300)
    
    if isinstance(resp_res, events.CallbackQuery.Event):
        await resp_res.answer()
        await msg_res.edit(buttons=None)
        if resp_res.data == b"ed_back": return
        
        movie_id = resp_res.data.decode().replace('ed_m_', '')
        await handle_editor_movie_action(conv, movie_id)

async def handle_editor_movie_action(conv, movie_id):
    doc = db.collection('videos').document(movie_id).get()
    if not doc.exists: return
    data = doc.to_dict()
    
    msg = await conv.send_message(
        f"🎬 **Editando Película:**\\n`{data.get('title')}`",
        buttons=[
            [Button.inline("✏️ Renombrar Título", b"renombrar")],
            [Button.inline("🗑️ Eliminar Película", b"eliminar")],
            [Button.inline("⬅️ Volver", b"volver")]
        ]
    )
    resp = await wait_for_message_or_callback(conv, timeout=300)
    if isinstance(resp, events.CallbackQuery.Event):
        await resp.answer()
        await msg.edit(buttons=None)
        if resp.data == b"volver": return
        elif resp.data == b"renombrar":
            await conv.send_message("Escribe el **nuevo título** para la película:")
            new_title = await conv.get_response()
            db.collection('videos').document(movie_id).update({"title": new_title.raw_text})
            await conv.send_message(f"✅ Título actualizado a: **{new_title.raw_text}**")
        elif resp.data == b"eliminar":
            db.collection('videos').document(movie_id).delete()
            await conv.send_message("✅ Película eliminada.")

async def handle_editor_series_search(conv):
    uid_back = str(uuid.uuid4()).encode()
    msg = await conv.send_message("🔍 Escribe el nombre de la **serie** que deseas buscar:", buttons=[[Button.inline("⬅️ Cancelar", uid_back)]])
    
    resp = await wait_for_message_or_callback(conv, timeout=300)
    if isinstance(resp, events.CallbackQuery.Event) and resp.data == uid_back:
        await resp.answer()
        await msg.edit("Búsqueda cancelada.", buttons=None)
        return
        
    query = resp.raw_text.strip()
    await msg.delete()
    
    series_ref = db.collection('videos').where(filter=FieldFilter('is_folder', '==', True)).get()
    results = [s for s in series_ref if query.lower() in s.to_dict().get('title', '').lower()]
    
    if not results:
        await conv.send_message("❌ No se encontraron series con ese nombre.")
        return
        
    results = results[:10]
    buttons = []
    for r in results:
        buttons.append([Button.inline(f"📺 {r.to_dict().get('title')[:30]}", f"ed_s_{r.id}".encode('utf-8'))])
    
    buttons.append([Button.inline("⬅️ Volver", b"ed_back")])
    
    msg_res = await conv.send_message("📌 **Resultados (Series):**", buttons=buttons)
    resp_res = await wait_for_message_or_callback(conv, timeout=300)
    
    if isinstance(resp_res, events.CallbackQuery.Event):
        await resp_res.answer()
        await msg_res.edit(buttons=None)
        if resp_res.data == b"ed_back": return
        
        series_id = resp_res.data.decode().replace('ed_s_', '')
        await handle_editor_series_action(conv, series_id)

async def handle_editor_series_action(conv, series_id):
    while editor_mode_active.get(conv.chat_id, False):
        doc = db.collection('videos').document(series_id).get()
        if not doc.exists: return
        data = doc.to_dict()
        title = data.get('title')
        
        msg = await conv.send_message(
            f"📺 **Editando Serie:**\\n`{title}`",
            buttons=[
                [Button.inline("✏️ Renombrar Serie", b"renombrar")],
                [Button.inline("📑 Ver y Editar Capítulos", b"ver_caps")],
                [Button.inline("➕ Agregar Nuevos Capítulos", b"add_caps")],
                [Button.inline("🗑️ Eliminar Serie Completa", b"eliminar")],
                [Button.inline("⬅️ Volver al menú principal", b"volver")]
            ]
        )
        resp = await wait_for_message_or_callback(conv, timeout=3600)
        if getattr(resp, 'raw_text', '').startswith('/'): return
        
        if isinstance(resp, events.CallbackQuery.Event):
            await resp.answer()
            await msg.edit(buttons=None)
            
            if resp.data == b"volver": return
            elif resp.data == b"renombrar":
                await conv.send_message("Escribe el **nuevo título general** para la serie:")
                new_title = await conv.get_response()
                db.collection('videos').document(series_id).update({"title": new_title.raw_text})
                await conv.send_message(f"✅ Título general actualizado a: **{new_title.raw_text}**")
            elif resp.data == b"eliminar":
                caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
                for c in caps: db.collection('videos').document(c.id).delete()
                db.collection('videos').document(series_id).delete()
                await conv.send_message("✅ Serie y todos sus capítulos eliminados.")
                return
            elif resp.data == b"ver_caps":
                await handle_editor_series_chapters(conv, series_id, title)
            elif resp.data == b"add_caps":
                await handle_editor_add_chapters(conv, series_id, title)

async def handle_editor_series_chapters(conv, series_id, series_title):
    caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
    caps = sorted(caps, key=lambda x: x.to_dict().get('episode', 0))
    if not caps:
        await conv.send_message("❌ Esta serie no tiene capítulos.")
        return
        
    buttons = []
    for c in caps[:90]:
        c_data = c.to_dict()
        buttons.append([Button.inline(f"Cap {c_data.get('episode', 0)}: {c_data.get('title')[:20]}", f"ed_c_{c.id}".encode('utf-8'))])
        
    buttons.append([Button.inline("⬅️ Volver", b"volver_caps")])
    
    msg = await conv.send_message(f"📑 **Capítulos de {series_title}**\\nSelecciona uno para editar:", buttons=buttons)
    resp = await wait_for_message_or_callback(conv, timeout=300)
    
    if isinstance(resp, events.CallbackQuery.Event):
        await resp.answer()
        await msg.edit(buttons=None)
        if resp.data == b"volver_caps": return
        cap_id = resp.data.decode().replace('ed_c_', '')
        await handle_editor_single_chapter(conv, cap_id)

async def handle_editor_single_chapter(conv, cap_id):
    doc = db.collection('videos').document(cap_id).get()
    if not doc.exists: return
    data = doc.to_dict()
    
    msg = await conv.send_message(
        f"🎞️ **Editando Capítulo:**\\n`{data.get('title')}`",
        buttons=[
            [Button.inline("✏️ Renombrar", b"renombrar")],
            [Button.inline("🗑️ Eliminar", b"eliminar")],
            [Button.inline("⬅️ Volver", b"volver")]
        ]
    )
    resp = await wait_for_message_or_callback(conv, timeout=300)
    if isinstance(resp, events.CallbackQuery.Event):
        await resp.answer()
        await msg.edit(buttons=None)
        if resp.data == b"volver": return
        if resp.data == b"renombrar":
            await conv.send_message("Escribe el **nuevo nombre** del capítulo:")
            new_title = await conv.get_response()
            db.collection('videos').document(cap_id).update({"title": new_title.raw_text})
            await conv.send_message(f"✅ Capítulo renombrado a: **{new_title.raw_text}**")
        if resp.data == b"eliminar":
            db.collection('videos').document(cap_id).delete()
            await conv.send_message("✅ Capítulo eliminado.")

async def handle_editor_add_chapters(conv, series_id, series_title):
    uid_done = str(uuid.uuid4()).encode()
    videos = []
    
    msg_v = await conv.send_message(
        f"➕ **Añadiendo capítulos a: {series_title}**\\n\\nEnvía los videos. Cuando termines presiona el botón.",
        buttons=[[Button.inline("📁 Terminar y Guardar", uid_done)]]
    )
    
    debounce_task = None
    async def update_button():
        await asyncio.sleep(0.8)
        nonlocal msg_v
        try: await msg_v.delete()
        except: pass
        msg_v = await conv.send_message(
            f"➕ **Añadiendo capítulos a: {series_title}**\\n\\n({len(videos)} recibidos). Envía más o termina.",
            buttons=[[Button.inline("📁 Terminar y Guardar", uid_done)]]
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
            if debounce_task: debounce_task.cancel()
            debounce_task = asyncio.create_task(update_button())

    client.add_event_handler(video_receiver, events.NewMessage(chats=conv.chat_id, incoming=True))
    try:
        while True:
            event = await wait_for_message_or_callback(conv, timeout=3600)
            if isinstance(event, events.CallbackQuery.Event):
                if event.data == uid_done:
                    if not videos:
                        await event.answer("No has enviado videos.", alert=True)
                        return
                    await event.answer("Guardando...")
                    if debounce_task: debounce_task.cancel()
                    await msg_v.edit(f"✅ Se recibieron {len(videos)} capítulos.", buttons=None)
                    break
    finally:
        client.remove_event_handler(video_receiver, events.NewMessage(chats=conv.chat_id, incoming=True))

    if not videos: return

    uid_title = str(uuid.uuid4()).encode()
    uid_file = str(uuid.uuid4()).encode()
    msg_n = await conv.send_message(
        "📁 ¿Cómo nombrar estos capítulos extra?",
        buttons=[
            [Button.inline("📁 Continuar enumeración general", uid_title)],
            [Button.inline("📁 Usar nombres de archivos originales", uid_file)]
        ]
    )
    
    naming_strategy = "title"
    while True:
        event = await wait_for_message_or_callback(conv, timeout=300)
        if isinstance(event, events.CallbackQuery.Event):
            if event.data == uid_title:
                naming_strategy = "title"
                await msg_n.edit("Formato: Serie - Capítulo X", buttons=None)
                break
            elif event.data == uid_file:
                naming_strategy = "file"
                await msg_n.edit("Formato: Archivo original", buttons=None)
                break
        else:
            naming_strategy = "manual"
            manual_prefix = event.raw_text
            await msg_n.edit(f"Formato: {manual_prefix}...", buttons=None)
            break

    status_msg = await conv.send_message("📁 **Procesando capítulos extra...**")
    
    caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
    max_ep = 0
    for c in caps:
        ep = c.to_dict().get('episode', 0)
        if ep > max_ep: max_ep = ep

    for i, video_msg in enumerate(videos):
        max_ep += 1
        
        if naming_strategy == "title":
            ep_title = f"{series_title} - Capítulo {max_ep}"
        elif naming_strategy == "manual":
            ep_title = f"{manual_prefix} - Capítulo {max_ep}"
        else:
            doc_name = "Episodio"
            if hasattr(video_msg.media, 'document'):
                for attr in video_msg.media.document.attributes:
                    if hasattr(attr, 'file_name'):
                        import os
                        doc_name = os.path.splitext(attr.file_name)[0]
                        break
            ep_title = doc_name

        await status_msg.edit(f"📁 Subiendo extra: **{ep_title}** ({i+1}/{len(videos)})")
        caption = f"**Twisted Streaming Brody Data**\\n\\n📁 **Serie:** {series_title}\\n📁 **Episodio:** {ep_title}"
        sent_to_channel = await client.send_file(CHANNEL_ID, video_msg.media, caption=caption)
        clean_channel_id = str(CHANNEL_ID).replace("-100", "")
        file_url = f"https://t.me/c/{clean_channel_id}/{sent_to_channel.id}"

        db.collection('videos').add({
            "title": ep_title, 
            "section": "series",
            "is_folder": False, 
            "folder_id": series_id,
            "episode": max_ep,
            "season": 1,
            "video_url": file_url, 
            "telegram_file_id": str(sent_to_channel.id),
            "description": "",
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
    await status_msg.edit(f"✅ **¡{len(videos)} capítulos extra añadidos con éxito!**")

if __name__ == '__main__':
"""
code = code.replace("if __name__ == '__main__':", editor_logic)

old_cmds = """                    BotCommand(command="app", description="Abrir la Mini App de Catálogo"),
                    BotCommand(command="setting", description="Configurar envío de videos"),
                    BotCommand(command="cancelar", description="Cancelar proceso de subida")"""
new_cmds = """                    BotCommand(command="app", description="Abrir la Mini App de Catálogo"),
                    BotCommand(command="setting", description="Configurar envío de videos"),
                    BotCommand(command="cancelar", description="Cancelar proceso de subida"),
                    BotCommand(command="activar_modo_editor", description="Activar Modo Editor"),
                    BotCommand(command="desactivar_modo_editor", description="Desactivar Modo Editor")"""
code = code.replace(old_cmds, new_cmds)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Patch applied successfully.")
