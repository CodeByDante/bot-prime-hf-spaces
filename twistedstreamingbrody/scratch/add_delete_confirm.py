import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

# MOVIE DELETE
old_movie_del = """        elif resp.data == b"eliminar":
            db.collection('videos').document(movie_id).delete()
            await conv.send_message("✅ Película eliminada.")"""

new_movie_del = """        elif resp.data == b"eliminar":
            msg_conf = await conv.send_message(
                f"⚠️ ¿Estás seguro de que deseas eliminar la película **{data.get('title')}**?\\nEsta acción no se puede deshacer.",
                buttons=[
                    [Button.inline("⚠️ Sí, eliminar definitivamente", b"confirm_del")],
                    [Button.inline("❌ Cancelar", b"cancel_del")]
                ]
            )
            resp_conf = await wait_for_message_or_callback(conv, timeout=120)
            if isinstance(resp_conf, events.CallbackQuery.Event):
                await resp_conf.answer()
                await msg_conf.edit(buttons=None)
                if resp_conf.data == b"confirm_del":
                    db.collection('videos').document(movie_id).delete()
                    await conv.send_message("✅ Película eliminada exitosamente.")
                else:
                    await conv.send_message("✅ Eliminación cancelada.")"""

code = code.replace(old_movie_del, new_movie_del)

# SERIES DELETE
old_series_del = """            elif resp.data == b"eliminar":
                caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
                for c in caps: db.collection('videos').document(c.id).delete()
                db.collection('videos').document(series_id).delete()
                await conv.send_message("✅ Serie y todos sus capítulos eliminados.")
                return"""

new_series_del = """            elif resp.data == b"eliminar":
                msg_conf = await conv.send_message(
                    f"⚠️ ¿Estás seguro de que deseas eliminar la serie completa **{title}** y **TODOS** sus capítulos?\\nEsta acción no se puede deshacer.",
                    buttons=[
                        [Button.inline("⚠️ Sí, eliminar serie y capítulos", b"confirm_del")],
                        [Button.inline("❌ Cancelar", b"cancel_del")]
                    ]
                )
                resp_conf = await wait_for_message_or_callback(conv, timeout=120)
                if isinstance(resp_conf, events.CallbackQuery.Event):
                    await resp_conf.answer()
                    await msg_conf.edit(buttons=None)
                    if resp_conf.data == b"confirm_del":
                        caps = db.collection('videos').where(filter=FieldFilter('folder_id', '==', series_id)).get()
                        for c in caps: db.collection('videos').document(c.id).delete()
                        db.collection('videos').document(series_id).delete()
                        await conv.send_message("✅ Serie y todos sus capítulos eliminados exitosamente.")
                        return
                    else:
                        await conv.send_message("✅ Eliminación cancelada.")"""

code = code.replace(old_series_del, new_series_del)

# CHAPTER DELETE
old_chapter_del = """        if resp.data == b"eliminar":
            db.collection('videos').document(cap_id).delete()
            await conv.send_message("✅ Capítulo eliminado.")"""

new_chapter_del = """        if resp.data == b"eliminar":
            msg_conf = await conv.send_message(
                f"⚠️ ¿Estás seguro de que deseas eliminar el capítulo **{data.get('title')}**?\\nEsta acción no se puede deshacer.",
                buttons=[
                    [Button.inline("⚠️ Sí, eliminar capítulo", b"confirm_del")],
                    [Button.inline("❌ Cancelar", b"cancel_del")]
                ]
            )
            resp_conf = await wait_for_message_or_callback(conv, timeout=120)
            if isinstance(resp_conf, events.CallbackQuery.Event):
                await resp_conf.answer()
                await msg_conf.edit(buttons=None)
                if resp_conf.data == b"confirm_del":
                    db.collection('videos').document(cap_id).delete()
                    await conv.send_message("✅ Capítulo eliminado exitosamente.")
                else:
                    await conv.send_message("✅ Eliminación cancelada.")"""

code = code.replace(old_chapter_del, new_chapter_del)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Delete confirmation patch applied successfully.")
