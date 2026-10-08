import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

old_logic = """                elif getattr(resp, 'raw_text', ''):
                    txt = resp.raw_text.strip()
                    if txt.startswith('/'): continue
                    try:
                        await msg.delete()
                    except:
                        await msg.edit(buttons=None)
                    
                    doc = db.collection('videos').document(txt).get()
                    if doc.exists:
                        data = doc.to_dict()
                        if data.get('is_folder', False) or data.get('section') == 'series':
                            await handle_editor_series_action(conv, txt)
                        else:
                            await handle_editor_movie_action(conv, txt)
                    else:
                        await conv.send_message(f"❌ El ID proporcionado (`{txt}`) no fue encontrado en la base de datos.")"""

new_logic = """                elif getattr(resp, 'raw_text', ''):
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
                            
                        # Resend the main menu immediately so they can input something else
                        msg = await conv.send_message(
                            "🛠️ **Modo Editor Activado**\\n\\n¿Qué más deseas gestionar?",
                            buttons=[
                                [Button.inline("🎬 Gestionar Películas", b"ed_mov")],
                                [Button.inline("📺 Gestionar Series", b"ed_ser")],
                                [Button.inline("❌ Salir del Editor", b"ed_exit")]
                            ]
                        )
                    else:
                        await conv.send_message(f"❌ El ID proporcionado (`{txt}`) no fue encontrado en la base de datos.")"""

code = code.replace(old_logic, new_logic)


# ALSO need to fix handle_document_id so that if editor_mode_active is True, it DOES NOT return, 
# wait, actually handle_document_id SHOULD return if editor mode is active, 
# because we are catching /start ID inside handle_editor_mode's loop!
# We just need to make sure handle_document_id still returns as it currently does.

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Concurrent editor patch applied successfully.")
