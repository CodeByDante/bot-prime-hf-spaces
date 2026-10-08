import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

# Replace block in handle_series_upload (around line 540)
old_series_upload = """            uid_back = str(uuid.uuid4()).encode()
            msg_n = await conv.send_message(
                "📁 **Paso 3:** ¿Qué nombre llevarán los capítulos?\\n\\n"
                "Escribe un nombre base y se enumerarán automáticamente.\\n\\n"
                f"Por ejemplo, si escribes un nombre o usas el botón **Usar nombre del título general** (`{series_title}`), se nombrarán así:\\n"
                f"- {series_title} - Capítulo 1\\n"
                f"- {series_title} - Capítulo 2\\n"
                f"- {series_title} - Capítulo 3\\n\\n"
                "Si usas el botón **Usar nombres originales de los archivos**, se vería así:\\n"
                "- video_ep1_720p.mp4\\n"
                "- episodio_2_sub.mkv\\n\\n"
                "Elige un atajo rápido o escribe tu propio nombre base:",
                buttons=["""

new_series_upload = """            uid_back = str(uuid.uuid4()).encode()
            
            sample_names = ""
            for v in videos[:2]:
                doc_name = "Video_desconocido.mp4"
                if hasattr(v.media, 'document'):
                    for attr in v.media.document.attributes:
                        if hasattr(attr, 'file_name'):
                            doc_name = attr.file_name
                            break
                sample_names += f"- {doc_name}\\n"
                
            msg_n = await conv.send_message(
                "📁 **Paso 3:** ¿Qué nombre llevarán los capítulos?\\n\\n"
                "Escribe un nombre base y se enumerarán automáticamente.\\n\\n"
                f"Por ejemplo, si escribes un nombre o usas el botón **Usar nombre del título general** (`{series_title}`), se nombrarán así:\\n"
                f"- {series_title} - Capítulo 1\\n"
                f"- {series_title} - Capítulo 2\\n"
                f"- {series_title} - Capítulo 3\\n\\n"
                "Si usas el botón **Usar nombres originales de los archivos**, se usarán los nombres reales que acabas de subir:\\n"
                f"{sample_names}\\n"
                "Elige un atajo rápido o escribe tu propio nombre base:",
                buttons=["""

code = code.replace(old_series_upload, new_series_upload)

# Replace block in handle_editor_add_chapters (around line 1400)
old_editor_upload = """    uid_file = str(uuid.uuid4()).encode()
    msg_n = await conv.send_message(
        "📁 ¿Cómo nombrar estos capítulos extra?",
        buttons=[
            [Button.inline("📁 Continuar enumeración general", uid_title)],
            [Button.inline("📁 Usar nombres de archivos originales", uid_file)]
        ]
    )"""

new_editor_upload = """    uid_file = str(uuid.uuid4()).encode()
    
    sample_names = ""
    for v in videos[:2]:
        doc_name = "Video_desconocido.mp4"
        if hasattr(v.media, 'document'):
            for attr in v.media.document.attributes:
                if hasattr(attr, 'file_name'):
                    doc_name = attr.file_name
                    break
        sample_names += f"- {doc_name}\\n"
        
    msg_n = await conv.send_message(
        "📁 ¿Cómo nombrar estos capítulos extra?\\n\\n"
        "Si usas nombres originales, se verán así:\\n"
        f"{sample_names}",
        buttons=[
            [Button.inline("📁 Continuar enumeración general", uid_title)],
            [Button.inline("📁 Usar nombres de archivos originales", uid_file)]
        ]
    )"""

code = code.replace(old_editor_upload, new_editor_upload)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Text replaced successfully.")
