import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

# MOVIE SEARCH
old_movie_search = """async def handle_editor_movie_search(conv):
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
    results = [m for m in movies_ref if query.lower() in m.to_dict().get('title', '').lower()]"""

new_movie_search = """async def handle_editor_movie_search(conv):
    uid_back = str(uuid.uuid4()).encode()
    msg = await conv.send_message("🔍 Escribe el **nombre o el ID** de la película que deseas buscar:", buttons=[[Button.inline("⬅️ Cancelar", uid_back)]])
    
    resp = await wait_for_message_or_callback(conv, timeout=300)
    if isinstance(resp, events.CallbackQuery.Event) and resp.data == uid_back:
        await resp.answer("Cancelado")
        await msg.edit("Búsqueda cancelada.", buttons=None)
        return
        
    query = resp.raw_text.strip()
    await msg.delete()
    
    movies_ref = db.collection('videos').where(filter=FieldFilter('section', '==', 'peliculas')).get()
    results = [m for m in movies_ref if query.lower() in m.to_dict().get('title', '').lower() or query == m.id]"""

code = code.replace(old_movie_search, new_movie_search)


# SERIES SEARCH
old_series_search = """async def handle_editor_series_search(conv):
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
    results = [s for s in series_ref if query.lower() in s.to_dict().get('title', '').lower()]"""

new_series_search = """async def handle_editor_series_search(conv):
    uid_back = str(uuid.uuid4()).encode()
    msg = await conv.send_message("🔍 Escribe el **nombre o el ID** de la serie que deseas buscar:", buttons=[[Button.inline("⬅️ Cancelar", uid_back)]])
    
    resp = await wait_for_message_or_callback(conv, timeout=300)
    if isinstance(resp, events.CallbackQuery.Event) and resp.data == uid_back:
        await resp.answer()
        await msg.edit("Búsqueda cancelada.", buttons=None)
        return
        
    query = resp.raw_text.strip()
    await msg.delete()
    
    series_ref = db.collection('videos').where(filter=FieldFilter('is_folder', '==', True)).get()
    results = [s for s in series_ref if query.lower() in s.to_dict().get('title', '').lower() or query == s.id]"""

code = code.replace(old_series_search, new_series_search)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("ID Search patch applied successfully.")
