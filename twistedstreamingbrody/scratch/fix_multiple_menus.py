import os
import re

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add EditorJumpException at the top of handlers
exception_def = """class CancelUploadException(Exception):
    pass"""
new_exception_def = """class CancelUploadException(Exception):
    pass

class EditorJumpException(Exception):
    def __init__(self, jump_id):
        self.jump_id = jump_id"""
code = code.replace(exception_def, new_exception_def)

# 2. Modify wait_for_message_or_callback
old_wait = """    try:
        event = await asyncio.wait_for(future, timeout=timeout)
        if getattr(event, 'raw_text', getattr(event, 'text', '')) == '/cancelar':
            await client.send_message(chat_id, "📁 **Proceso cancelado.**")
            raise CancelUploadException()
        return event"""

new_wait = """    try:
        event = await asyncio.wait_for(future, timeout=timeout)
        txt = getattr(event, 'raw_text', getattr(event, 'text', '')).strip()
        
        if txt == '/cancelar':
            await client.send_message(chat_id, "📁 **Proceso cancelado.**")
            raise CancelUploadException()
            
        # Global intercept for editor mode jumps
        if editor_mode_active.get(chat_id, False):
            if txt.startswith('/start '):
                extracted = txt.replace('/start ', '').replace('folder_', '').strip()
                raise EditorJumpException(extracted)
            elif len(txt) == 20 and txt.isalnum() and not txt.startswith('/'):
                # Heuristic for Firebase ID jump
                raise EditorJumpException(txt)
                
        return event"""
code = code.replace(old_wait, new_wait)


# 3. Refactor handle_editor_mode
old_editor_loop = """                        # Helper for concurrent editing
                        async def spawn_edit(chat_id, func, t_id):
                            async with client.conversation(chat_id, timeout=3600, exclusive=False) as c:
                                try: await func(c, t_id)
                                except Exception as e: print("Concur error:", e)
                                
                        if data.get('section') == 'peliculas':
                            import asyncio
                            asyncio.create_task(spawn_edit(chat_id, handle_editor_movie_action, txt))
                        elif data.get('is_folder', False):
                            import asyncio
                            asyncio.create_task(spawn_edit(chat_id, handle_editor_series_action, txt))
                        elif data.get('section') == 'series' and not data.get('is_folder', False):
                            import asyncio
                            asyncio.create_task(spawn_edit(chat_id, handle_editor_single_chapter, txt))
                        else:
                            await conv.send_message("❌ Tipo de documento no reconocido.")
                    else:
                        await conv.send_message(f"❌ El ID proporcionado (`{txt}`) no fue encontrado en la base de datos.")

        except Exception as e:
            print("Editor error:", e)"""

new_editor_loop = """                        if data.get('section') == 'peliculas':
                            await handle_editor_movie_action(conv, txt)
                        elif data.get('is_folder', False):
                            await handle_editor_series_action(conv, txt)
                        elif data.get('section') == 'series' and not data.get('is_folder', False):
                            await handle_editor_single_chapter(conv, txt)
                        else:
                            await conv.send_message("❌ Tipo de documento no reconocido.")
                    else:
                        await conv.send_message(f"❌ El ID proporcionado (`{txt}`) no fue encontrado en la base de datos.")

        except EditorJumpException as e:
            # We caught a jump from a sub-menu! Resimulate raw_text input at the top level
            class DummyResp:
                raw_text = e.jump_id
            resp = DummyResp()
            # We can't jump directly inside the loop from an except block cleanly if we break, 
            # so we'll handle the ID recursively.
            await process_editor_id(conv, e.jump_id)
        except Exception as e:
            print("Editor error:", e)"""

# Wait, `process_editor_id` doesn't exist. I need to define it or refactor cleanly.
# Let's write the whole handle_editor_mode loop structure perfectly.

old_handle_editor = """async def handle_editor_mode(event):
    chat_id = event.chat_id
    async with client.conversation(chat_id, timeout=3600, exclusive=False) as conv:
        msg = await conv.send_message(
            "🛠️ **Modo Editor Activado**\\n\\n¿Qué deseas gestionar?",
            buttons=[
                [Button.inline("🎬 Gestionar Películas", b"ed_mov")],
                [Button.inline("📺 Gestionar Series", b"ed_ser")],
                [Button.inline("❌ Salir del Editor", b"ed_exit")]
            ]
        )
        
        try:
            while True:
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
                elif getattr(resp, 'raw_text', ''):
                    txt = resp.raw_text.strip()
                    
                    if txt.startswith('/start '):
                        txt = txt.replace('/start ', '').replace('folder_', '').strip()
                        
                    if txt.startswith('/'):
                        if txt == '/desactivar_modo_editor':
                            break
                        continue
                        
                    try:
                        await msg.delete()
                    except:
                        pass # if it can't delete, just ignore or edit
                    
                    doc = db.collection('videos').document(txt).get()
                    if doc.exists:
                        data = doc.to_dict()
                        
                        # Helper for concurrent editing
                        async def spawn_edit(chat_id, func, t_id):
                            async with client.conversation(chat_id, timeout=3600, exclusive=False) as c:
                                try: await func(c, t_id)
                                except Exception as e: print("Concur error:", e)
                                
                        if data.get('section') == 'peliculas':
                            import asyncio
                            asyncio.create_task(spawn_edit(chat_id, handle_editor_movie_action, txt))
                        elif data.get('is_folder', False):
                            import asyncio
                            asyncio.create_task(spawn_edit(chat_id, handle_editor_series_action, txt))
                        elif data.get('section') == 'series' and not data.get('is_folder', False):
                            import asyncio
                            asyncio.create_task(spawn_edit(chat_id, handle_editor_single_chapter, txt))
                        else:
                            await conv.send_message("❌ Tipo de documento no reconocido.")
                    else:
                        await conv.send_message(f"❌ El ID proporcionado (`{txt}`) no fue encontrado en la base de datos.")

        except Exception as e:
            print("Editor error:", e)"""

new_handle_editor = """async def process_editor_id(conv, txt):
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
        await conv.send_message(f"❌ El ID proporcionado (`{txt}`) no fue encontrado en la base de datos.")

async def handle_editor_mode(event):
    chat_id = event.chat_id
    async with client.conversation(chat_id, timeout=3600, exclusive=False) as conv:
        msg = await conv.send_message(
            "🛠️ **Modo Editor Activado**\\n\\n¿Qué deseas gestionar?",
            buttons=[
                [Button.inline("🎬 Gestionar Películas", b"ed_mov")],
                [Button.inline("📺 Gestionar Series", b"ed_ser")],
                [Button.inline("❌ Salir del Editor", b"ed_exit")]
            ]
        )
        
        while True:
            try:
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
                elif getattr(resp, 'raw_text', ''):
                    txt = resp.raw_text.strip()
                    
                    if txt.startswith('/start '):
                        txt = txt.replace('/start ', '').replace('folder_', '').strip()
                        
                    if txt.startswith('/'):
                        if txt == '/desactivar_modo_editor':
                            break
                        continue
                        
                    try:
                        await msg.delete()
                    except:
                        pass
                    
                    await process_editor_id(conv, txt)

            except EditorJumpException as e:
                # We caught a jump! Abort whatever sub-menu we were in and process the new ID globally.
                await process_editor_id(conv, e.jump_id)
            except Exception as e:
                print("Editor error:", e)
                break"""

code = code.replace(old_handle_editor, new_handle_editor)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Architecture refactored successfully.")
