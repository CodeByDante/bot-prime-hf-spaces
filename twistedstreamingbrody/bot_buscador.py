import asyncio
import uuid
import time
from telethon import events, Button
from telethon.tl.types import KeyboardButtonSimpleWebView, KeyboardButtonWebView
from google.cloud.firestore_v1.base_query import FieldFilter
from core import *

# --- MODO BUSCADOR ---
@client.on(events.NewMessage(pattern='^/buscador_on$'))
async def enable_search_mode(event):
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    if user_modes.get(chat_id) != 'buscador': return
    chat_id = event.chat_id
    
    # Desactivar editor y cancelar subidas
    editor_mode_active[chat_id] = False
    if chat_id in active_tasks:
        for t in active_tasks[chat_id]:
            t.cancel()
        del active_tasks[chat_id]
        
    search_mode_active[chat_id] = True
    await event.respond("🔍 **Modo Buscador Activado**\n\nAhora puedes buscar enviando el título de una película, serie o capítulo. También puedes pegar enlaces directos o IDs.\n\nEnvía /buscador_off para salir.")

@client.on(events.NewMessage(pattern='^/buscador_off$'))
async def disable_search_mode(event):
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    if user_modes.get(chat_id) != 'buscador': return
    chat_id = event.chat_id
    search_mode_active[chat_id] = False
    await event.respond("❌ **Modo Buscador Desactivado**.")

@client.on(events.NewMessage(func=lambda e: not e.text.startswith('/') and len(e.text) != 20))
async def handle_text_search(event):
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    if user_modes.get(chat_id) != 'buscador': return
    chat_id = event.chat_id
    if not True:
        return
    if editor_mode_active.get(chat_id, False):
        return
        
    query = event.raw_text.strip().lower()
    if not query: return
    
    msg = await event.respond("🔍 Buscando...")
    
    # Buscar en Firestore (limitado en memoria por diseño simple de Firebase)
    docs = db.collection('videos').get()
    
    matched_docs = []
    for d in docs:
        data = d.to_dict()
        title = data.get('title', '').lower()
        if query in title:
            matched_docs.append((d.id, data))
            
    if not matched_docs:
        await msg.edit("❌ No se encontraron resultados para tu búsqueda.")
        return

    # Buscar si hay alguna coincidencia EXACTA (para evitar que "Capítulo 1" muestre el "10", "11", etc.)
    exact_matches = [m for m in matched_docs if m[1].get('title', '').lower() == query]
    if len(exact_matches) == 1:
        matched_docs = exact_matches

    # Si hay exactamente 1 resultado, lo enviamos directamente
    if len(matched_docs) == 1:
        doc_id, data = matched_docs[0]
        class DummyEvent:
            def __init__(self, chat_id, raw_text):
                self.chat_id = chat_id
                self.raw_text = raw_text
            async def respond(self, *args, **kwargs):
                return await client.send_message(self.chat_id, *args, **kwargs)
                
        dummy = DummyEvent(event.chat_id, doc_id)
        await msg.delete()
        await handle_document_id(dummy)
        return

    # Si hay múltiples, filtramos para dar prioridad a las Carpetas (Series) y Películas
    # Esto evita mostrar una lista gigante de subcapítulos
    folders_and_movies = []
    chapters = []
    
    for r_id, data in matched_docs:
        if data.get('section') == 'peliculas' or data.get('is_folder'):
            folders_and_movies.append((r_id, data))
        else:
            chapters.append((r_id, data))
            
    # Mostrar carpetas/pelis si hay, sino mostrar capítulos sueltos
    results = folders_and_movies if folders_and_movies else chapters

    # Ordenar los resultados alfabéticamente por el título
    results.sort(key=lambda x: x[1].get('title', '').lower())

    # Mostrar resultados en botones
    results = results[:20] # Limitar a 20 resultados para no exceder limite de botones
    buttons = []
    for r_id, data in results:
        t = data.get('title', 'Sin titulo')[:40]
        icon = "🎬" if data.get('section') == 'peliculas' else ("📺" if data.get('is_folder') else "🎞️")
        buttons.append([Button.inline(f"{icon} {t}", f"get_vid_{r_id}".encode('utf-8'))])
        
    await msg.edit(f"📌 **Resultados para:** `{query}`", buttons=buttons)

@client.on(events.CallbackQuery(pattern=b'^get_vid_'))
async def handle_search_result_click(event):
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    if user_modes.get(chat_id) != 'buscador': return
    if not True:
        await event.answer("El modo buscador está desactivado.", alert=True)
        return
        
    doc_id = event.data.decode('utf-8').replace('get_vid_', '')
    await event.answer()
    
    # Simulamos como si el usuario hubiera enviado el ID directamente
    class DummyEvent:
        def __init__(self, chat_id, raw_text):
            self.chat_id = chat_id
            self.raw_text = raw_text
        async def respond(self, *args, **kwargs):
            return await client.send_message(self.chat_id, *args, **kwargs)
            
    dummy = DummyEvent(event.chat_id, doc_id)
    await handle_document_id(dummy)

# --------------------------


# --- CONFIGURACIÓN Y FUNCIONES DE BÚSQUEDA POR ID ---

bot_settings = {
    "send_title": True,
    "send_description": True,
    "ask_series": True
}

try:
    doc_settings = db.collection('settings').document('delivery').get()
    if doc_settings.exists:
        s_data = doc_settings.to_dict()
        bot_settings['send_title'] = s_data.get('send_title', True)
        bot_settings['send_description'] = s_data.get('send_description', True)
        bot_settings['ask_series'] = s_data.get('ask_series', True)
except Exception as e:
    print(f"📁 Error cargando settings: {e}")

@client.on(events.NewMessage(pattern='/(settings|setting|config)$'))
async def settings_handler(event):
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    if user_modes.get(chat_id) != 'buscador': return
    await show_settings_menu(event)

async def show_settings_menu(event_or_query):
    title_status = "✅ PRENDIDO" if bot_settings['send_title'] else "❌ APAGADO"
    desc_status = "✅ PRENDIDO" if bot_settings['send_description'] else "❌ APAGADO"
    ask_status = "✅ PRENDIDO" if bot_settings['ask_series'] else "❌ APAGADO"
    
    botones = [
        [Button.inline(f"Título: {title_status}", b"toggle_title")],
        [Button.inline(f"Descripción: {desc_status}", b"toggle_desc")],
        [Button.inline(f"Preguntar Temporada/Capítulo: {ask_status}", b"toggle_ask")]
    ]
    
    text = "⚙️ **Configuración de Envío de Videos**\n\nElige cómo quieres que el bot entregue los videos:"
    
    if isinstance(event_or_query, events.CallbackQuery.Event):
        await event_or_query.edit(text, buttons=botones)
    else:
        await event_or_query.respond(text, buttons=botones)

from telethon.tl.types import KeyboardButtonWebView

@client.on(events.NewMessage(pattern='/(twistedstreamingbrodybot|app)$'))
async def miniapp_handler(event):
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    if user_modes.get(chat_id) != 'buscador': return
    # Usamos KeyboardButtonWebView para forzar a Telegram a abrirlo como Mini App
    botones = [[KeyboardButtonWebView(text="🍿 Abrir Catálogo", url="https://codebybrody-twistedstreamingbrody.hf.space")]]
        
    await event.respond(
        "🍿 **¡Twisted Streaming Brody!**\n\nToca el botón abajo para abrir nuestra Mini App y navegar por todas las películas y series directamente desde Telegram.",
        buttons=botones
    )

button_cooldowns = {}

@client.on(events.CallbackQuery(pattern=b'^toggle_(title|desc|ask)$'))
async def toggle_settings_handler(event):
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    if user_modes.get(chat_id) != 'buscador': return
    chat_id = event.chat_id
    now = time.time()
    if now - button_cooldowns.get(chat_id, 0) < 0.5:
        await event.answer()
        return
    button_cooldowns[chat_id] = now
    
    action = event.pattern_match.group(1).decode()
    if action == 'title':
        bot_settings['send_title'] = not bot_settings['send_title']
    elif action == 'desc':
        bot_settings['send_description'] = not bot_settings['send_description']
    elif action == 'ask':
        bot_settings['ask_series'] = not bot_settings['ask_series']
        
    try:
        db.collection('settings').document('delivery').set(bot_settings)
    except: pass
    
    await event.answer()
    await show_settings_menu(event)

async def send_movie(chat_id, file_id, data):
    cover = data.get('cover_url') or data.get('thumbnail_url')
    caption_parts = []
    if bot_settings['send_title'] and data.get('title'):
        caption_parts.append(f"📁 **{data.get('title')}**")
    if bot_settings['send_description'] and data.get('description'):
        caption_parts.append(f"{data.get('description')}")
    
    custom_caption = "\n\n".join(caption_parts)
    
    if cover:
        try:
            await client.send_file(chat_id, cover, caption=custom_caption)
        except Exception:
            if custom_caption: await client.send_message(chat_id, custom_caption)
    elif custom_caption:
        await client.send_message(chat_id, custom_caption)
    
    try:
        msg = await client.get_messages(CHANNEL_ID, ids=int(file_id))
        if msg and getattr(msg, 'media', None):
            await client.send_file(chat_id, msg.media, caption="")
        else:
            await client.send_message(chat_id, "📁 Video no encontrado en el canal.")
    except Exception as e:
        print("Error enviando película:", e)

async def send_series_cover(chat_id, folder_id):
    if not folder_id: return
    try:
        s_doc = db.collection('videos').document(folder_id).get()
        if s_doc.exists:
            s_data = s_doc.to_dict()
            cover = s_data.get('thumbnail_url') or s_data.get('cover_url')
            
            caption = ""
            if bot_settings['send_title'] and s_data.get('title'):
                caption = f"📁 **{s_data.get('title')}**"
                
            if cover:
                try:
                    await client.send_file(chat_id, cover, caption=caption)
                except Exception:
                    if caption: await client.send_message(chat_id, caption)
            elif caption:
                await client.send_message(chat_id, caption)
    except Exception as e:
        print("Error al enviar portada de serie:", e)

async def send_episode_video(chat_id, file_id, ep_data):
    try:
        msg = await client.get_messages(CHANNEL_ID, ids=int(file_id))
        if not msg or not getattr(msg, 'media', None):
            await client.send_message(chat_id, "📁 Capítulo no encontrado en el canal.")
            return

        caption_parts = []
        if bot_settings['send_title'] and ep_data.get('title'):
            caption_parts.append(f"📁 **{ep_data.get('title')}**")
        if bot_settings['send_description'] and ep_data.get('description'):
            caption_parts.append(f"{ep_data.get('description')}")
            
        custom_caption = "\n\n".join(caption_parts)
        await client.send_file(chat_id, msg.media, caption=custom_caption)
    except Exception as e:
        print("Error enviando capítulo:", e)

async def send_full_season(chat_id, folder_id, status_msg=None):
    if not status_msg:
        status_msg = await client.send_message(chat_id, "📁 Preparando los capítulos...")
    else:
        try:
            await status_msg.edit("📁 Preparando los capítulos...", buttons=None)
        except Exception:
            pass

    episodes = db.collection('videos').where(filter=FieldFilter('folder_id', '==', folder_id)).get()
    if not episodes:
        await status_msg.edit("📁 No se encontraron capítulos.")
        return
        
    await send_series_cover(chat_id, folder_id)
    
    episodes_sorted = sorted(episodes, key=lambda x: x.to_dict().get('episode', 0))
    for ep in episodes_sorted:
        data = ep.to_dict()
        file_id = data.get('telegram_file_id')
        if file_id:
            await send_episode_video(chat_id, file_id, data)
            await asyncio.sleep(0.5)
    await status_msg.edit("📁 **¡Temporada enviada!**")

@client.on(events.NewMessage(pattern=r'^/start (folder_)?[a-zA-Z0-9_-]{20}$'))
@client.on(events.NewMessage(pattern=r'^(folder/|folder_)?[a-zA-Z0-9_-]{20}$'))
async def handle_document_id(event):
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    if user_modes.get(chat_id) != 'buscador': return
    
    if editor_mode_active.get(event.chat_id, False):
        return
        
    text = event.raw_text.strip()
    is_folder_request = False
    
    if text.startswith('/start '):
        payload = text.split(' ')[1]
        if payload.startswith('folder_'):
            is_folder_request = True
            doc_id = payload.replace('folder_', '', 1)
        else:
            doc_id = payload
    else:
        if text.startswith('folder/') or text.startswith('folder_'):
            is_folder_request = True
            doc_id = text.replace('folder/', '', 1).replace('folder_', '', 1)
        else:
            doc_id = text
    
    try:
        doc = db.collection('videos').document(doc_id).get()
        if not doc.exists:
            return
            
        data = doc.to_dict()
        section = data.get('section')
        is_folder = data.get('is_folder')
        
        if section == 'peliculas':
            file_id = data.get('telegram_file_id')
            if file_id:
                await send_movie(event.chat_id, file_id, data)
            else:
                await event.respond("📁 No se encontró el archivo en Telegram para esta película.")
                
        elif section == 'series':
            folder_id = doc_id if is_folder else data.get('folder_id')
            
            if is_folder_request:
                await send_full_season(event.chat_id, folder_id)
                return
            
            if not bot_settings.get('ask_series', True):
                if is_folder:
                    await send_full_season(event.chat_id, folder_id)
                else:
                    file_id = data.get('telegram_file_id')
                    if file_id:
                        await send_series_cover(event.chat_id, folder_id)
                        await send_episode_video(event.chat_id, file_id, data)
                    else:
                        await event.respond("📁 Archivo no encontrado.")
                return
            
            if is_folder:
                episodes = db.collection('videos').where(filter=FieldFilter('folder_id', '==', doc_id)).get()
                episodes_sorted = sorted(episodes, key=lambda x: x.to_dict().get('episode', 0))
                
                botones = []
                row = []
                for ep in episodes_sorted:
                    ep_data = ep.to_dict()
                    ep_num = ep_data.get('episode', '?')
                    ep_id = ep.id
                    row.append(Button.inline(f"Cap {ep_num}", f"this_cap_{ep_id}".encode()))
                    if len(row) == 3:
                        botones.append(row)
                        row = []
                if row:
                    botones.append(row)
                    
                botones.append([Button.inline("📁 Enviar Temporada Completa", f"all_caps_{doc_id}".encode())])
                
                await event.respond(f"📁 **Serie:** {data.get('title')}\nSelecciona un capítulo o envía la temporada completa:", buttons=botones)
            else:
                botones = [
                    [Button.inline("📁 Enviar solo este video", f"this_cap_{doc_id}".encode())],
                    [Button.inline("📁 Enviar Temporada Completa", f"all_caps_{folder_id}".encode())]
                ]
                await event.respond(f"📁 **Capítulo:** {data.get('title')}\n¿Qué deseas hacer?", buttons=botones)
                
    except Exception as e:
        print(f"Error buscando documento {doc_id}: {e}")

@client.on(events.CallbackQuery(pattern=b'^(this_cap_|all_caps_|choose_cap_)(.*)'))
async def handle_series_delivery(event):
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    if user_modes.get(chat_id) != 'buscador': return
    chat_id = event.chat_id
    now = time.time()
    if now - button_cooldowns.get(chat_id, 0) < 1.0:
        await event.answer("Procesando...", alert=False)
        return
    button_cooldowns[chat_id] = now
    
    action = event.pattern_match.group(1).decode()
    target_id = event.pattern_match.group(2).decode()
    
    try:
        if action == "this_cap_":
            await event.answer("📁 Enviando capítulo...", alert=False)
            doc = db.collection('videos').document(target_id).get()
            if doc.exists:
                data = doc.to_dict()
                file_id = data.get('telegram_file_id')
                folder_id = data.get('folder_id')
                if file_id:
                    await send_series_cover(event.chat_id, folder_id)
                    await send_episode_video(event.chat_id, file_id, data)
                else:
                    await event.respond("📁 Archivo no encontrado.")
                    
        elif action == "all_caps_":
            await event.answer("📁 Preparando temporada...", alert=False)
            await send_full_season(chat_id, target_id, status_msg=event)
            
        elif action == "choose_cap_":
            await event.answer("📁 Cargando capítulos...", alert=False)
            episodes = db.collection('videos').where(filter=FieldFilter('folder_id', '==', target_id)).get()
            if not episodes:
                await event.answer("No se encontraron capítulos.", alert=True)
                return
                
            episodes_sorted = sorted(episodes, key=lambda x: x.to_dict().get('episode', 0))
            
            botones = []
            row = []
            for ep in episodes_sorted:
                data = ep.to_dict()
                ep_num = data.get('episode', '?')
                ep_id = ep.id
                row.append(Button.inline(f"Cap {ep_num}", f"this_cap_{ep_id}".encode()))
                if len(row) == 3:
                    botones.append(row)
                    row = []
            if row:
                botones.append(row)
                
            await event.edit("📁 **Selecciona el capítulo:**", buttons=botones)
            
    except Exception as e:
        print(f"Error en delivery: {e}")
        await event.respond("📁 Hubo un error procesando la solicitud.")


