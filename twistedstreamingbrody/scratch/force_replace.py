import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

old_code = """async def handle_editor_mode(event):
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

new_code = """async def process_editor_id(conv, txt):
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
        try:
            while editor_mode_active.get(chat_id, False):
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
                        
                    msg = await conv.send_message(
                        "🛠️ **Modo Editor Activado**\\n\\n¿Qué deseas gestionar?",
                        buttons=[
                            [Button.inline("🎬 Gestionar Películas", b"ed_mov")],
                            [Button.inline("📺 Gestionar Series", b"ed_ser")],
                            [Button.inline("❌ Salir del Editor", b"ed_exit")]
                        ]
                    )
                elif getattr(resp, 'raw_text', ''):
                    txt = resp.raw_text.strip()
                    if txt.startswith('/start '):
                        txt = txt.replace('/start ', '').replace('folder_', '').strip()
                        
                    if txt.startswith('/'):
                        if txt == '/desactivar_modo_editor':
                            break
                        continue
                        
                    try: await msg.delete()
                    except: pass
                    
                    await process_editor_id(conv, txt)
                    
                    msg = await conv.send_message(
                        "🛠️ **Modo Editor Activado**\\n\\n¿Qué deseas gestionar?",
                        buttons=[
                            [Button.inline("🎬 Gestionar Películas", b"ed_mov")],
                            [Button.inline("📺 Gestionar Series", b"ed_ser")],
                            [Button.inline("❌ Salir del Editor", b"ed_exit")]
                        ]
                    )

        except EditorJumpException as e:
            try: await msg.delete()
            except: pass
            await process_editor_id(conv, e.jump_id)
            # Re-spawn cleanly after processing the jump
            await handle_editor_mode(event)
        except Exception as e:
            print("Editor error:", e)"""

code = code.replace(old_code, new_code)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Forced replacement applied!")
