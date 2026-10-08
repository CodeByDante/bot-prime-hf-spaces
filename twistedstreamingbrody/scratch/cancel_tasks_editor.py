import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

old_enable_editor = """@client.on(events.NewMessage(pattern='/(activar_modo_editor)$'))
async def enable_editor(event):
    chat_id = event.chat_id
    editor_mode_active[chat_id] = True
    await handle_editor_mode(event)"""

new_enable_editor = """@client.on(events.NewMessage(pattern='/(activar_modo_editor)$'))
async def enable_editor(event):
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
"""

code = code.replace(old_enable_editor, new_enable_editor)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Task cancellation patch applied to editor mode.")
