import os
import shutil
import zipfile
import tempfile
import asyncio
from telethon import events
from core.client import client
from utils.helpers import safe_edit_status

def is_image_message(msg):
    if not msg:
        return False
    if msg.photo:
        return True
    if msg.document:
        mime = msg.document.mime_type or ""
        if mime.startswith('image/'):
            return True
        for attr in msg.document.attributes:
            if hasattr(attr, 'file_name') and attr.file_name:
                if attr.file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
                    return True
    return False

async def procesar_comando_zip_imagenes(event):
    chat_id = event.chat_id
    
    # Extraer argumento opcional (cantidad de imágenes)
    command_text = event.message.message
    parts = command_text.split(maxsplit=1)
    
    limit = None  # None significa TODAS las imágenes del canal
    if len(parts) >= 2:
        try:
            val = int(parts[1].strip())
            if val > 0:
                limit = val
        except ValueError:
            pass

    status_msg = await event.reply(
        f"🔍 **[Bot Prime]** Escaneando el canal en busca de "
        f"{f'las últimas **{limit}**' if limit else '**TODAS las**'} imágenes..."
    )

    temp_dir = tempfile.mkdtemp(prefix="zip_img_")
    zip_path = None

    try:
        # Obtener título del canal para nombrar el archivo zip
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', None) or f"canal_{abs(chat_id)}"
        clean_title = "".join(c for c in chat_title if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
        if not clean_title:
            clean_title = f"canal_{abs(chat_id)}"

        img_messages = []

        # 1. Escanear mensajes
        async for m in client.iter_messages(chat_id):
            if is_image_message(m):
                img_messages.append(m)
                if limit and len(img_messages) >= limit:
                    break

        if not img_messages:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontraron imágenes en este canal.")
            return

        total_found = len(img_messages)
        # Invertir para que se ordenen de la más antigua a la más reciente (cronológico)
        img_messages.reverse()

        await safe_edit_status(
            status_msg, 
            f"📥 **[Bot Prime]** Se encontraron **{total_found}** imágenes. Iniciando descarga..."
        )

        downloaded_paths = []
        digits = max(3, len(str(total_found)))

        for idx, m in enumerate(img_messages, start=1):
            ext = ".jpg"
            if m.document and m.document.mime_type:
                if "png" in m.document.mime_type:
                    ext = ".png"
                elif "webp" in m.document.mime_type:
                    ext = ".webp"
                elif "gif" in m.document.mime_type:
                    ext = ".gif"

            file_number = str(idx).zfill(digits)
            filename = f"{file_number}_foto_{m.id}{ext}"
            file_path = os.path.join(temp_dir, filename)

            try:
                await client.download_media(m, file=file_path)
                if os.path.exists(file_path):
                    downloaded_paths.append(file_path)
            except Exception as e:
                print(f"[Zip Img] Error al descargar imagen {m.id}: {e}")

            # Actualizar progreso cada 10 imágenes o al final
            if idx % 10 == 0 or idx == total_found:
                await safe_edit_status(
                    status_msg,
                    f"⏳ **[Bot Prime]** Descargando imágenes: **{idx}/{total_found}**..."
                )

        if not downloaded_paths:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** Ocurrió un error y no se pudo descargar ninguna imagen.")
            return

        # 2. Compresión a archivo ZIP
        await safe_edit_status(status_msg, f"📦 **[Bot Prime]** Comprimiendo **{len(downloaded_paths)}** imágenes en archivo ZIP...")
        zip_filename = f"imagenes_{clean_title}_{len(downloaded_paths)}.zip"
        zip_path = os.path.join(tempfile.gettempdir(), zip_filename)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for fpath in downloaded_paths:
                arcname = os.path.basename(fpath)
                zipf.write(fpath, arcname=arcname)

        zip_size_bytes = os.path.getsize(zip_path)
        zip_size_mb = round(zip_size_bytes / (1024 * 1024), 2)

        # 3. Subir archivo ZIP al canal de Telegram
        await safe_edit_status(
            status_msg, 
            f"⬆️ **[Bot Prime]** Subiendo archivo ZIP (**{zip_size_mb} MB**) al canal..."
        )

        caption = (
            f"📦 **[Bot Prime] Compresión de Imágenes**\n\n"
            f"📁 **Canal:** {chat_title}\n"
            f"🖼️ **Total de imágenes:** {len(downloaded_paths)}\n"
            f"💾 **Tamaño del ZIP:** {zip_size_mb} MB"
        )

        await client.send_file(
            chat_id,
            zip_path,
            caption=caption
        )

        await safe_edit_status(
            status_msg,
            f"✅ **[Bot Prime]** ¡Proceso completado! Se subió el archivo ZIP con **{len(downloaded_paths)}** imágenes numeradas ordenadamente."
        )

    except Exception as e:
        print(f"[Error Zip Imagenes] {e}")
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Ocurrió un error al procesar el ZIP: {e}")
        except Exception:
            pass
    finally:
        # Limpieza de archivos temporales
        shutil.rmtree(temp_dir, ignore_errors=True)
        if zip_path and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except Exception:
                pass
