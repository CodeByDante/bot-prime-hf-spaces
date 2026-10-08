import asyncio
import uuid
import time
from telethon import events, Button
from telethon.tl.types import KeyboardButtonSimpleWebView, KeyboardButtonWebView
from google.cloud.firestore_v1.base_query import FieldFilter
from core import *

# --- MODO EDITOR ---
@client.on(events.NewMessage(pattern='/(activar_modo_editor)$'))
async def enable_editor(event):
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    if user_modes.get(chat_id) != 'editor': return
    import asyncio
    chat_id = event.chat_id
    
    # Cancel previous tasks to prevent "Botón expirado" background overlap
    if chat_id in active_tasks:
        for old_task in active_tasks[chat_id]:
            if not old_task.done():
                if not getattr(old_task, 'is_uploading', False):
                    old_task.cancel()
        try: await asyncio.sleep(0.1)
        except: pass
        
    current_task = asyncio.current_task()
    current_task.is_uploading = False
    
    if chat_id not in active_tasks:
        active_tasks[chat_id] = []
    active_tasks[chat_id].append(current_task)

    editor_mode_active[chat_id] = True
    try:
        await handle_editor_mode(event)
    finally:
        if current_task in active_tasks.get(chat_id, []):
            active_tasks[chat_id].remove(current_task)
            if not active_tasks[chat_id]:
                del active_tasks[chat_id]


@client.on(events.NewMessage(pattern='/(desactivar_modo_editor)$'))
async def disable_editor(event):
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    if user_modes.get(chat_id) != 'editor': return
    chat_id = event.chat_id
    editor_mode_active[chat_id] = False
    await event.respond("✅ **Modo editor desactivado.** Ya puedes usar los comandos normales.")

async def process_editor_id(conv, txt):
    doc = db.collection('videos').document(txt).get()
    if doc.exists:
        data = doc.to_dict()
        if data.get('section') == 'peliculas':
            await handle_editor_movie_action(conv, txt)
        elif data.get('is_folder', False):
            await handle_editor_series_action(conv, txt)
        elif data.get('section') == 'series' and not data.get('is_folder', False):
            await handle_editor_single_chapter(conv, txt)
        else:
            await conv.send_message("❌ Tipo de documento no reconocido.")
    else:
        # Búsqueda por texto si no es un ID exacto
        all_videos = db.collection('videos').get()
        results = [v for v in all_videos if txt.lower() in v.to_dict().get('title', '').lower()]
        
        if not results:
            from telethon.tl.types import KeyboardButtonWebView
            btn_webapp = KeyboardButtonWebView(text="🍿 Buscar en Catálogo", url="https://codebybrody-twistedstreamingbrody.hf.space")
            await conv.send_message(
                f"❌ No se encontró ningún contenido con el nombre o ID: `{txt}`\n\n🔍 **Sugerencia:** Puedes buscar el nombre o ID exacto directamente en la Mini App:",
                buttons=[[btn_webapp]]
            )
            return
            
        results = results[:10]
        buttons = []
        for r in results:
            data = r.to_dict()
            icon = "🎬" if data.get('section') == 'peliculas' else "📺" if data.get('is_folder', False) else "🎞️"
            title = data.get('title', 'Sin título')[:30]
            buttons.append([Button.inline(f"{icon} {title}", f"ed_jump_{r.id}".encode('utf-8'))])
            
        buttons.append([Button.inline("❌ Cancelar", b"ed_cancel")])
        
        msg_res = await conv.send_message("📌 **Resultados de Búsqueda:**", buttons=buttons)
        resp_res = await wait_for_message_or_callback(conv, timeout=300)
        
        if isinstance(resp_res, events.CallbackQuery.Event):
            await resp_res.answer()
            try: await msg_res.edit(buttons=None)
            except: pass
            
            if resp_res.data == b"ed_cancel": return
            
            selected_id = resp_res.data.decode().replace('ed_jump_', '')
            await process_editor_id(conv, selected_id)

async def handle_editor_mode(event, initial_txt=None):
    chat_id = event.chat_id
    async with client.conversation(chat_id, timeout=3600, exclusive=False) as conv:
        current_jump_id = initial_txt
        
        while True:
            try:
                if current_jump_id:
                    jump = current_jump_id
                    current_jump_id = None
                    await process_editor_id(conv, jump)
                    
                    from telethon.tl.types import KeyboardButtonWebView
                    btn_webapp = KeyboardButtonWebView(text="🍿 Twisted Streaming Brody", url="https://codebybrody-twistedstreamingbrody.hf.space")
                    await conv.send_message("🛠️ **Modo Editor**\nEnvíame otro ID para editar, o busca en la Mini App:", buttons=[[btn_webapp]])
                    continue
                
                if not initial_txt and not current_jump_id:
                    msg_main = await conv.send_message(
                        "🛠️ **Modo Editor Activado**\n\n"
                        "Envíame el **ID** del contenido que deseas editar..."
                    )
                
                resp = await wait_for_message_or_callback(conv, timeout=3600)
                
                if isinstance(resp, events.CallbackQuery.Event):
                    await resp.answer("Botón expirado o inválido.", alert=True)
                    continue

                if getattr(resp, 'raw_text', ''):
                    txt = resp.raw_text.strip()
                    if txt.startswith('/start '):
                        txt = txt.replace('/start ', '').replace('folder_', '').strip()
                        
                    if txt.startswith('/'):
                        if txt == '/desactivar_modo_editor':
                            break
                        continue
                        
                    await process_editor_id(conv, txt)
                    
                    # Prompt user again after finishing an edit
                    from telethon.tl.types import KeyboardButtonWebView
                    btn_webapp = KeyboardButtonWebView(text="🍿 Twisted Streaming Brody", url="https://codebybrody-twistedstreamingbrody.hf.space")
                    await conv.send_message("🛠️ **Modo Editor**\nEnvíame otro ID para editar, o busca en la Mini App:", buttons=[[btn_webapp]])

            except EditorJumpException as e:
                current_jump_id = e.jump_id
            except CancelUploadException:
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                print("Editor error:", e)
                break

async def handle_editor_movie_search(conv):
    from telethon.tl.types import KeyboardButtonWebView
    try:
        tmp = await conv.send_message("🔄 Actualizando...", buttons=Button.clear())
        await tmp.delete()
    except: pass
    uid_back = str(uuid.uuid4()).encode()
    btn_webapp = KeyboardButtonWebView(text="🍿 Buscar ID en Catálogo", url="https://codebybrody-twistedstreamingbrody.hf.space")
    msg = await conv.send_message("🔍 Escribe el **nombre o el ID** de la película que deseas buscar:", buttons=[
        [btn_webapp],
        [Button.inline("⬅️ Cancelar", uid_back)]
    ])
    
    resp = await wait_for_message_or_callback(conv, timeout=300)
    if isinstance(resp, events.CallbackQuery.Event) and resp.data == uid_back:
        await resp.answer("Cancelado")
        await msg.edit("Búsqueda cancelada.", buttons=None)
        return
        
    query = resp.raw_text.strip()
    await msg.delete()
    
    movies_ref = db.collection('videos').where(filter=FieldFilter('section', '==', 'peliculas')).get()
    results = [m for m in movies_ref if query.lower() in m.to_dict().get('title', '').lower() or query == m.id]
    
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
        f"🎬 **Editando Película:**\n`{data.get('title')}`",
        buttons=[
            [Button.inline("✏️ Renombrar Título", b"renombrar")],
            [Button.inline("📝 Editar Descripción", b"edit_desc")],
            [Button.inline("🖼️ Editar Portada", b"edit_cover")],
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
        elif resp.data == b"edit_desc":
            uid_del = str(uuid.uuid4()).encode()
            msg_d = await conv.send_message("Escribe la **nueva descripción** para la película:", buttons=[[Button.inline("❌ Eliminar Descripción", uid_del)]])
            resp_d = await wait_for_message_or_callback(conv, timeout=300)
            if isinstance(resp_d, events.CallbackQuery.Event):
                await resp_d.answer("Eliminando...")
                db.collection('videos').document(movie_id).update({"description": ""})
                await msg_d.edit("✅ Descripción eliminada.", buttons=None)
            else:
                db.collection('videos').document(movie_id).update({"description": resp_d.raw_text})
                await msg_d.edit("✅ Descripción actualizada.", buttons=None)
        elif resp.data == b"edit_cover":
            msg_cover = await conv.send_message("🖼️ Envía la nueva portada como imagen (no archivo):")
            resp_cover = await wait_for_message_or_callback(conv, timeout=300)
            if getattr(resp_cover, 'photo', None):
                await msg_cover.edit("🖼️ Subiendo portada...", buttons=None)
                cover_url = await upload_to_imgbb(resp_cover.photo)
                if cover_url:
                    db.collection('videos').document(movie_id).update({"cover_url": cover_url, "thumbnail_url": cover_url})
                    await conv.send_message("✅ Portada actualizada con éxito.")
                else:
                    await conv.send_message("❌ Hubo un error al subir la portada.")
            else:
                if isinstance(resp_cover, events.CallbackQuery.Event):
                    await resp_cover.answer("Cancelado")
                else:
                    await conv.send_message("❌ No se recibió una imagen válida.")
        elif resp.data == b"eliminar":
            msg_conf = await conv.send_message(
                f"⚠️ ¿Estás seguro de que deseas eliminar la película **{data.get('title')}**?\nEsta acción no se puede deshacer.",
                buttons=[
                    [Button.inline("⚠️ Sí, eliminar definitivamente", b"confirm_del")],
                    [Button.inline("❌ Cancelar", b"cancel_del")]
                ]
            )
            resp_conf = await wait_for_message_or_callback(conv, timeout=120)
            if isinstance(resp_conf, events.CallbackQuery.Event):
                await resp_conf.answer()
                await msg_conf.edit(buttons=None)
                if resp_conf.data == b"confirm_del":
                    db.collection('videos').document(movie_id).delete()
                    await conv.send_message("✅ Película eliminada exitosamente.")
                else:
                    await conv.send_message("✅ Eliminación cancelada.")

async def handle_editor_series_search(conv):
    from telethon.tl.types import KeyboardButtonWebView
    try:
        tmp = await conv.send_message("🔄 Actualizando...", buttons=Button.clear())
        await tmp.delete()
    except: pass
    uid_back = str(uuid.uuid4()).encode()
    btn_webapp = KeyboardButtonWebView(text="🍿 Buscar ID en Catálogo", url="https://codebybrody-twistedstreamingbrody.hf.space")
    msg = await conv.send_message("🔍 Escribe el **nombre o el ID** de la serie que deseas buscar:", buttons=[
        [btn_webapp],
        [Button.inline("⬅️ Cancelar", uid_back)]
    ])
    
    resp = await wait_for_message_or_callback(conv, timeout=300)
    if isinstance(resp, events.CallbackQuery.Event) and resp.data == uid_back:
        await resp.answer()
        await msg.edit("Búsqueda cancelada.", buttons=None)
        return
        
    query = resp.raw_text.strip()
    await msg.delete()
    
    series_ref = db.collection('videos').where(filter=FieldFilter('is_folder', '==', True)).get()
    results = [s for s in series_ref if query.lower() in s.to_dict().get('title', '').lower() or query == s.id]
    
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
    while True:
        doc = db.collection('videos').document(series_id).get()
        if not doc.exists: return
        data = doc.to_dict()
        title = data.get('title')
        
        msg = await conv.send_message(
            f"📺 **Editando Serie:**\n`{title}`",
            buttons=[
                [Button.inline("✏️ Renombrar Serie", b"renombrar")],
                [Button.inline("🖼️ Editar Portada General", b"edit_cover")],
                [Button.inline("📝 Edición Masiva de Descripciones", b"edit_desc_masiva")],
                [Button.inline("📑 Ver y Editar Capítulos", b"ver_caps")],
                [Button.inline("📝 Edición Masiva de Capítulos", b"editar_lista")],
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
            elif resp.data == b"edit_cover":
                msg_cover = await conv.send_message("🖼️ Envía la nueva portada general de la serie como imagen (no archivo):")
                resp_cover = await wait_for_message_or_callback(conv, timeout=300)
                if getattr(resp_cover, 'photo', None):
                    await msg_cover.edit("🖼️ Subiendo portada...", buttons=None)
                    cover_url = await upload_to_imgbb(resp_cover.photo)
                    if cover_url:
                        db.collection('videos').document(series_id).update({"thumbnail_url": cover_url, "cover_url": cover_url})
                        await conv.send_message("✅ Portada de la serie actualizada con éxito.")
                    else:
                        await conv.send_message("❌ Hubo un error al subir la portada.")
                else:
                    if isinstance(resp_cover, events.CallbackQuery.Event):
                        await resp_cover.answer("Cancelado")
                    else:
                        await conv.send_message("❌ No se recibió una imagen válida.")
            elif resp.data == b"edit_desc_masiva":
                uid_del = str(uuid.uuid4()).encode()
                msg_d = await conv.send_message("Escribe la **nueva descripción** para aplicarla a TODOS los capítulos de esta serie:", buttons=[[Button.inline("❌ Eliminar Todas las Descripciones", uid_del)]])
                resp_d = await wait_for_message_or_callback(conv, timeout=300)
                caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
                updated_count = 0
                
                if isinstance(resp_d, events.CallbackQuery.Event):
                    await resp_d.answer("Eliminando...")
                    for c in caps:
                        db.collection('videos').document(c.id).update({"description": ""})
                        updated_count += 1
                    await msg_d.edit(f"✅ Descripciones eliminadas masivamente en {updated_count} capítulos.", buttons=None)
                else:
                    for c in caps:
                        db.collection('videos').document(c.id).update({"description": resp_d.raw_text})
                        updated_count += 1
                    await msg_d.edit(f"✅ Descripción aplicada masivamente a {updated_count} capítulos.", buttons=None)
            elif resp.data == b"eliminar":
                msg_conf = await conv.send_message(
                    f"⚠️ ¿Estás seguro de que deseas eliminar la serie completa **{title}** y **TODOS** sus capítulos?\nEsta acción no se puede deshacer.",
                    buttons=[
                        [Button.inline("⚠️ Sí, eliminar serie y capítulos", b"confirm_del")],
                        [Button.inline("❌ Cancelar", b"cancel_del")]
                    ]
                )
                resp_conf = await wait_for_message_or_callback(conv, timeout=120)
                if isinstance(resp_conf, events.CallbackQuery.Event):
                    await resp_conf.answer()
                    await msg_conf.edit(buttons=None)
                    if resp_conf.data == b"confirm_del":
                        caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
                        for c in caps: db.collection('videos').document(c.id).delete()
                        db.collection('videos').document(series_id).delete()
                        await conv.send_message("✅ Serie y todos sus capítulos eliminados exitosamente.")
                        return
                    else:
                        await conv.send_message("✅ Eliminación cancelada.")
            elif resp.data == b"ver_caps":
                await handle_editor_series_chapters(conv, series_id, title)
            elif resp.data == b"editar_lista":
                caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
                caps = sorted(caps, key=lambda x: x.to_dict().get('episode', 0))
                if not caps:
                    await conv.send_message("❌ Esta serie no tiene capítulos.")
                    continue
                
                template = f"{{TITULO_GENERAL}} {title}\n\n"
                for c in caps:
                    template += f"{{{c.id}}} {c.to_dict().get('title')}\n"
                
                await conv.send_message(
                    "📝 **EDICIÓN MASIVA**\n\n"
                    "1. Toca el siguiente mensaje para copiarlo.\n"
                    "2. Pégalo en el chat y edita el nombre de la serie o de los capítulos como desees.\n"
                    "3. Envíamelo.\n\n"
                    "⚠️ **MUY IMPORTANTE:** ¡NO borres ni modifiques los códigos entre llaves `{ }`!"
                )
                await conv.send_message(f"```{template}```")
                
                await conv.send_message("⏳ Esperando tu mensaje con la plantilla editada... (O envía `/cancelar` para abortar)")
                
                resp_text = await wait_for_message_or_callback(conv, timeout=3600)
                if isinstance(resp_text, events.CallbackQuery.Event):
                    await resp_text.answer("Operación cancelada")
                    continue
                if resp_text.raw_text.strip().lower() == '/cancelar':
                    await conv.send_message("✅ Edición masiva cancelada.")
                    continue
                if getattr(resp_text, 'raw_text', '').startswith('/'): return
                    
                new_text = resp_text.raw_text
                import re
                matches = re.findall(r'\{(.*?)\}\s*(.*)', new_text)
                
                if not matches:
                    await conv.send_message("❌ No se detectó el formato correcto. Recuerda no borrar las llaves { }.")
                    continue
                    
                status_m = await conv.send_message("⚙️ Guardando cambios...")
                updated_count = 0
                for doc_id, new_title in matches:
                    doc_id = doc_id.strip()
                    new_title = new_title.strip()
                    if new_title:
                        if doc_id == "TITULO_GENERAL":
                            try:
                                db.collection('videos').document(series_id).update({"title": new_title})
                                title = new_title # update variable
                            except: pass
                        else:
                            try:
                                db.collection('videos').document(doc_id).update({"title": new_title})
                                updated_count += 1
                            except: pass
                        
                await status_m.edit(f"✅ **¡Listo!** Se actualizó el título general y {updated_count} capítulos correctamente.")
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
    
    msg = await conv.send_message(f"📑 **Capítulos de {series_title}**\nSelecciona uno para editar:", buttons=buttons)
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
        f"🎞️ **Editando Capítulo:**\n`{data.get('title')}`",
        buttons=[
            [Button.inline("✏️ Renombrar", b"renombrar")],
            [Button.inline("📝 Editar Descripción", b"edit_desc")],
            [Button.inline("🗑️ Eliminar Capítulo", b"eliminar")],
            [Button.inline("🚨 Eliminar Serie Completa", b"elim_serie")],
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
        if resp.data == b"edit_desc":
            uid_del = str(uuid.uuid4()).encode()
            msg_d = await conv.send_message("Escribe la **nueva descripción** del capítulo:", buttons=[[Button.inline("❌ Eliminar Descripción", uid_del)]])
            resp_d = await wait_for_message_or_callback(conv, timeout=300)
            if isinstance(resp_d, events.CallbackQuery.Event):
                await resp_d.answer("Eliminando...")
                db.collection('videos').document(cap_id).update({"description": ""})
                await msg_d.edit("✅ Descripción eliminada.", buttons=None)
            else:
                db.collection('videos').document(cap_id).update({"description": resp_d.raw_text})
                await msg_d.edit("✅ Descripción actualizada.", buttons=None)
        if resp.data == b"eliminar":
            msg_conf = await conv.send_message(
                f"⚠️ ¿Estás seguro de que deseas eliminar el capítulo **{data.get('title')}**?\nEsta acción no se puede deshacer.",
                buttons=[
                    [Button.inline("⚠️ Sí, eliminar capítulo", b"confirm_del")],
                    [Button.inline("❌ Cancelar", b"cancel_del")]
                ]
            )
            resp_conf = await wait_for_message_or_callback(conv, timeout=120)
            if isinstance(resp_conf, events.CallbackQuery.Event):
                await resp_conf.answer()
                await msg_conf.edit(buttons=None)
                if resp_conf.data == b"confirm_del":
                    db.collection('videos').document(cap_id).delete()
                    await conv.send_message("✅ Capítulo eliminado exitosamente.")
                else:
                    await conv.send_message("✅ Eliminación cancelada.")
        if resp.data == b"elim_serie":
            series_id = data.get('folder_id')
            if not series_id:
                await conv.send_message("❌ Error: Este capítulo no pertenece a una serie.")
                return
                
            series_doc = db.collection('videos').document(series_id).get()
            series_title = series_doc.to_dict().get('title') if series_doc.exists else "Desconocida"
            
            msg_conf = await conv.send_message(
                f"🚨 **¡PELIGRO!**\n¿Estás seguro de que deseas eliminar la serie completa **{series_title}** y **TODOS** sus capítulos?\nEsta acción te dejará sin nada y no se puede deshacer.",
                buttons=[
                    [Button.inline("🚨 Sí, eliminar serie y capítulos", b"confirm_del_serie")],
                    [Button.inline("❌ Cancelar", b"cancel_del")]
                ]
            )
            resp_conf = await wait_for_message_or_callback(conv, timeout=120)
            if isinstance(resp_conf, events.CallbackQuery.Event):
                await resp_conf.answer()
                await msg_conf.edit(buttons=None)
                if resp_conf.data == b"confirm_del_serie":
                    caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
                    for c in caps: db.collection('videos').document(c.id).delete()
                    if series_doc.exists:
                        db.collection('videos').document(series_id).delete()
                    await conv.send_message("✅ Serie y todos sus capítulos eliminados exitosamente.")
                    raise CancelUploadException() # Fuerza salida limpia al menú principal
                else:
                    await conv.send_message("✅ Eliminación cancelada.")


async def handle_editor_add_chapters(conv, series_id, series_title):
    uid_done = str(uuid.uuid4()).encode()
    videos = []
    
    msg_v = await conv.send_message(
        f"➕ **Añadiendo capítulos a: {series_title}**\n\nEnvía los videos. Cuando termines presiona el botón.",
        buttons=[[Button.inline("📁 Terminar y Guardar", uid_done)]]
    )
    
    debounce_task = None
    async def update_button():
        await asyncio.sleep(0.8)
        nonlocal msg_v
        try: await msg_v.delete()
        except: pass
        msg_v = await conv.send_message(
            f"➕ **Añadiendo capítulos a: {series_title}**\n\n({len(videos)} recibidos). Envía más o termina.",
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
    
    sample_names = ""
    for v in videos[:2]:
        doc_name = "Video_desconocido.mp4"
        if hasattr(v.media, 'document'):
            for attr in v.media.document.attributes:
                if hasattr(attr, 'file_name'):
                    doc_name = attr.file_name
                    break
        sample_names += f"- {doc_name}\n"
        
    msg_n = await conv.send_message(
        "📁 ¿Cómo nombrar estos capítulos extra?\n\n"
        "Si usas nombres originales, se verán así:\n"
        f"{sample_names}",
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
        caption = f"**Twisted Streaming Brody Data**\n\n📁 **Serie:** {series_title}\n📁 **Episodio:** {ep_title}"
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

@client.on(events.NewMessage())
async def global_editor_listener(event):
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    if user_modes.get(chat_id) != 'editor': return
    
    # Si ya hay tareas activas en este chat, la conversación interceptará el mensaje sola
    if chat_id in active_tasks and active_tasks[chat_id]:
        return
        
    txt = getattr(event, 'raw_text', '').strip()
    if txt.startswith('/start '):
        txt = txt.replace('/start ', '').replace('folder_', '').strip()
        
    if txt.startswith('/'):
        return
        
    # Iniciar ciclo del editor inyectando el ID directamente
    import asyncio
    current_task = asyncio.current_task()
    if chat_id not in active_tasks:
        active_tasks[chat_id] = []
    active_tasks[chat_id].append(current_task)
    try:
        await handle_editor_mode(event, initial_txt=txt)
    finally:
        if current_task in active_tasks.get(chat_id, []):
            active_tasks[chat_id].remove(current_task)
