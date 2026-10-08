import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

old_mass_edit = """                template = f"--- {title} ---\\n"
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

new_mass_edit = """                template = f"{{TITULO_GENERAL}} {title}\\n\\n"
                for c in caps:
                    template += f"{{{c.id}}} {c.to_dict().get('title')}\\n"
                
                await conv.send_message(
                    "📝 **EDICIÓN MASIVA**\\n\\n"
                    "1. Toca el siguiente mensaje para copiarlo.\\n"
                    "2. Pégalo en el chat y edita el nombre de la serie o de los capítulos como desees.\\n"
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
                        if doc_id == "TITULO_GENERAL":
                            try:
                                db.collection('videos').document(series_id).update({"title": new_title})
                                title = new_title # update variable
                            except: pass
                        else:
                            try:
                                db.collection('videos').document(doc_id).update({"title": new_title})
                                updated_count += 1
                            except: pass
                        
                await status_m.edit(f"✅ **¡Listo!** Se actualizó el título general y {updated_count} capítulos correctamente.")"""

code = code.replace(old_mass_edit, new_mass_edit)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Mass edit title patch applied.")
