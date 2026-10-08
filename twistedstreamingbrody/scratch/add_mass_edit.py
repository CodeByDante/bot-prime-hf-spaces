import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

# 1. ADD BUTTON
old_series_buttons = """        msg = await conv.send_message(
            f"📺 **Editando Serie:**\\n`{title}`",
            buttons=[
                [Button.inline("✏️ Renombrar Serie", b"renombrar")],
                [Button.inline("📑 Ver y Editar Capítulos", b"ver_caps")],
                [Button.inline("➕ Agregar Nuevos Capítulos", b"add_caps")],
                [Button.inline("🗑️ Eliminar Serie Completa", b"eliminar")],
                [Button.inline("⬅️ Volver al menú principal", b"volver")]
            ]
        )"""

new_series_buttons = """        msg = await conv.send_message(
            f"📺 **Editando Serie:**\\n`{title}`",
            buttons=[
                [Button.inline("✏️ Renombrar Serie", b"renombrar")],
                [Button.inline("📑 Ver y Editar Capítulos", b"ver_caps")],
                [Button.inline("📝 Edición Masiva de Capítulos", b"editar_lista")],
                [Button.inline("➕ Agregar Nuevos Capítulos", b"add_caps")],
                [Button.inline("🗑️ Eliminar Serie Completa", b"eliminar")],
                [Button.inline("⬅️ Volver al menú principal", b"volver")]
            ]
        )"""

code = code.replace(old_series_buttons, new_series_buttons)

# 2. ADD LOGIC
old_series_logic = """            elif resp.data == b"ver_caps":
                await handle_editor_series_chapters(conv, series_id, title)"""

new_series_logic = """            elif resp.data == b"ver_caps":
                await handle_editor_series_chapters(conv, series_id, title)
            elif resp.data == b"editar_lista":
                caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
                caps = sorted(caps, key=lambda x: x.to_dict().get('episode', 0))
                if not caps:
                    await conv.send_message("❌ Esta serie no tiene capítulos.")
                    continue
                
                template = f"--- {title} ---\\n"
                for c in caps:
                    template += f"{{{c.id}}} {c.to_dict().get('title')}\\n"
                
                await conv.send_message(
                    "📝 **EDICIÓN MASIVA**\\n\\n"
                    "1. Toca el siguiente mensaje para copiarlo.\\n"
                    "2. Pégalo en el chat y edita los nombres de los capítulos.\\n"
                    "3. Envíamelo.\\n\\n"
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
                    
                new_text = resp_text.raw_text
                import re
                matches = re.findall(r'\\{(.*?)\\}\\s*(.*)', new_text)
                
                if not matches:
                    await conv.send_message("❌ No se detectó el formato correcto. Recuerda no borrar las llaves { }.")
                    continue
                    
                status_m = await conv.send_message("⚙️ Guardando cambios...")
                updated_count = 0
                for doc_id, new_title in matches:
                    doc_id = doc_id.strip()
                    new_title = new_title.strip()
                    if new_title:
                        try:
                            db.collection('videos').document(doc_id).update({"title": new_title})
                            updated_count += 1
                        except: pass
                        
                await status_m.edit(f"✅ **¡Listo!** Se actualizaron {updated_count} capítulos correctamente.")"""

code = code.replace(old_series_logic, new_series_logic)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Mass edit feature applied successfully.")
