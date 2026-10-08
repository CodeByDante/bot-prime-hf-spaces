import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add search_mode_active dictionary
if "search_mode_active = {}" not in code:
    code = code.replace("editor_mode_active = {}", "editor_mode_active = {}\nsearch_mode_active = {}")

# 2. Update handle_document_id to ONLY work if search_mode_active is True
old_handle_doc = """@client.on(events.NewMessage(pattern=r'^/start (folder_)?[a-zA-Z0-9_-]{20}$'))
@client.on(events.NewMessage(pattern=r'^(folder/|folder_)?[a-zA-Z0-9_-]{20}$'))
async def handle_document_id(event):
    if editor_mode_active.get(event.chat_id, False):
        return"""

new_handle_doc = """@client.on(events.NewMessage(pattern=r'^/start (folder_)?[a-zA-Z0-9_-]{20}$'))
@client.on(events.NewMessage(pattern=r'^(folder/|folder_)?[a-zA-Z0-9_-]{20}$'))
async def handle_document_id(event):
    if editor_mode_active.get(event.chat_id, False):
        return
        
    if not search_mode_active.get(event.chat_id, False):
        return # Ignore links/IDs if search mode is OFF"""

code = code.replace(old_handle_doc, new_handle_doc)

# 3. Add /buscador_on and /buscador_off and the text search handler
new_search_logic = """
# --- MODO BUSCADOR ---
@client.on(events.NewMessage(pattern='^/buscador_on$'))
async def enable_search_mode(event):
    chat_id = event.chat_id
    
    # Desactivar editor y cancelar subidas
    editor_mode_active[chat_id] = False
    if chat_id in active_tasks:
        for t in active_tasks[chat_id]:
            t.cancel()
        del active_tasks[chat_id]
        
    search_mode_active[chat_id] = True
    await event.respond("🔍 **Modo Buscador Activado**\\n\\nAhora puedes buscar enviando el título de una película, serie o capítulo. También puedes pegar enlaces directos o IDs.\\n\\nEnvía /buscador_off para salir.")

@client.on(events.NewMessage(pattern='^/buscador_off$'))
async def disable_search_mode(event):
    chat_id = event.chat_id
    search_mode_active[chat_id] = False
    await event.respond("❌ **Modo Buscador Desactivado**.")

@client.on(events.NewMessage(func=lambda e: not e.text.startswith('/') and len(e.text) != 20))
async def handle_text_search(event):
    chat_id = event.chat_id
    if not search_mode_active.get(chat_id, False):
        return
    if editor_mode_active.get(chat_id, False):
        return
        
    query = event.raw_text.strip().lower()
    if not query: return
    
    msg = await event.respond("🔍 Buscando...")
    
    # Buscar en Firestore (limitado en memoria por diseño simple de Firebase)
    docs = db.collection('videos').get()
    results = []
    for d in docs:
        data = d.to_dict()
        title = data.get('title', '').lower()
        if query in title:
            results.append((d.id, data))
            
    if not results:
        await msg.edit("❌ No se encontraron resultados para tu búsqueda.")
        return
        
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
    if not search_mode_active.get(event.chat_id, False):
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
"""

# Insert the search logic before handlers
if "# --- MODO BUSCADOR ---" not in code:
    handler_marker = "# --- MANEJADORES ---"
    if handler_marker in code:
        code = code.replace(handler_marker, handler_marker + "\n" + new_search_logic)
    else:
        # Just append at the end
        code += new_search_logic

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Search mode added successfully.")
