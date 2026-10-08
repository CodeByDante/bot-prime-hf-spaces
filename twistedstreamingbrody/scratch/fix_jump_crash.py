import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

old_func = """async def handle_editor_mode(event):
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


new_func = """async def handle_editor_mode(event):
    chat_id = event.chat_id
    async with client.conversation(chat_id, timeout=3600, exclusive=False) as conv:
        current_jump_id = None
        last_msg = None
        
        while editor_mode_active.get(chat_id, False):
            try:
                if current_jump_id:
                    jump = current_jump_id
                    current_jump_id = None
                    if last_msg:
                        try: await last_msg.delete()
                        except: pass
                    await process_editor_id(conv, jump)
                    continue # Go back to start of loop

                last_msg = await conv.send_message(
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
                    try: await last_msg.delete()
                    except: pass
                    
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
                        
                    try: await last_msg.delete()
                    except: pass
                    
                    await process_editor_id(conv, txt)

            except EditorJumpException as e:
                # A jump occurred from anywhere (main menu or submenu)! Loop back and handle it.
                current_jump_id = e.jump_id
            except Exception as e:
                print("Editor error:", e)
                break"""

code = code.replace(old_func, new_func)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Infinite robust loop applied.")
