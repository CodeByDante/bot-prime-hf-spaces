import os
import re

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Movie rename
old_movie_rename = """                if isinstance(resp_text, events.CallbackQuery.Event):
                    await resp_text.answer("Cancelado")
                    continue
                new_title = resp_text.raw_text.strip()"""

new_movie_rename = """                if isinstance(resp_text, events.CallbackQuery.Event):
                    await resp_text.answer("Cancelado")
                    continue
                if getattr(resp_text, 'raw_text', '').startswith('/'): return
                new_title = resp_text.raw_text.strip()"""

code = code.replace(old_movie_rename, new_movie_rename)

# 2. Series rename
old_series_rename = """                if isinstance(resp_text, events.CallbackQuery.Event):
                    await resp_text.answer("Cancelado")
                    continue
                new_title = resp_text.raw_text.strip()"""

new_series_rename = """                if isinstance(resp_text, events.CallbackQuery.Event):
                    await resp_text.answer("Cancelado")
                    continue
                if getattr(resp_text, 'raw_text', '').startswith('/'): return
                new_title = resp_text.raw_text.strip()"""

code = code.replace(old_series_rename, new_series_rename)

# 3. Series mass edit
old_mass_edit = """                if isinstance(resp_text, events.CallbackQuery.Event):
                    await resp_text.answer("Operación cancelada")
                    continue
                if resp_text.raw_text.strip().lower() == '/cancelar':
                    await conv.send_message("✅ Edición masiva cancelada.")
                    continue
                    
                new_text = resp_text.raw_text"""

new_mass_edit = """                if isinstance(resp_text, events.CallbackQuery.Event):
                    await resp_text.answer("Operación cancelada")
                    continue
                if resp_text.raw_text.strip().lower() == '/cancelar':
                    await conv.send_message("✅ Edición masiva cancelada.")
                    continue
                if getattr(resp_text, 'raw_text', '').startswith('/'): return
                    
                new_text = resp_text.raw_text"""

code = code.replace(old_mass_edit, new_mass_edit)


# 4. Chapter rename
old_chapter_rename = """                if isinstance(resp_text, events.CallbackQuery.Event):
                    await resp_text.answer("Cancelado")
                    continue
                new_title = resp_text.raw_text.strip()"""

new_chapter_rename = """                if isinstance(resp_text, events.CallbackQuery.Event):
                    await resp_text.answer("Cancelado")
                    continue
                if getattr(resp_text, 'raw_text', '').startswith('/'): return
                new_title = resp_text.raw_text.strip()"""

code = code.replace(old_chapter_rename, new_chapter_rename)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Editor robust text input patch applied.")
