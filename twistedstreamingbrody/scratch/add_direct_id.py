import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

old_handle_editor = """                if isinstance(resp, events.CallbackQuery.Event):
                    await resp.answer()
                    await msg.edit(buttons=None)
                    
                    if resp.data == b"ed_exit":
                        editor_mode_active[chat_id] = False
                        await conv.send_message("✅ **Modo editor desactivado.**")
                        break
                    elif resp.data == b"ed_mov":
                        await handle_editor_movie_search(conv)
                    elif resp.data == b"ed_ser":
                        await handle_editor_series_search(conv)"""

new_handle_editor = """                if isinstance(resp, events.CallbackQuery.Event):
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
                    if txt.startswith('/'): continue
                    await msg.edit(buttons=None)
                    
                    doc = db.collection('videos').document(txt).get()
                    if doc.exists:
                        data = doc.to_dict()
                        if data.get('is_folder', False) or data.get('section') == 'series':
                            await handle_editor_series_action(conv, txt)
                        else:
                            await handle_editor_movie_action(conv, txt)
                    else:
                        await conv.send_message(f"❌ El ID proporcionado (`{txt}`) no fue encontrado en la base de datos.")
"""

code = code.replace(old_handle_editor, new_handle_editor)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Editor direct ID search applied successfully.")
