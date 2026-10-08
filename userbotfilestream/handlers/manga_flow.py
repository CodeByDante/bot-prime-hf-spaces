import os
import re
import shutil
import tempfile
import zipfile
import asyncio
from telethon import events
from core.client import client, client_pool
from utils.helpers import safe_edit_status

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import cv2

# Definir ruta de manera dinámica para que funcione tanto en Windows como en Hugging Face (Linux)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "manga flow data")
TELEGRAM_DATA_CHAT_ID = -1003824889674

def search_manga_in_db(manga_id):
    """Busca recursivamente el ID en los .txt y retorna (filepath, titulo, original_links, webp_links)"""
    for root, dirs, files in os.walk(DATA_DIR):
        for file in files:
            if file.endswith('.txt'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if f"ID: {manga_id}" in content:
                            return parse_manga_file(content, filepath)
                except Exception as e:
                    print(f"[Error leyendo {file}] {e}")
                    pass
    return None

def parse_manga_file(content, filepath):
    titulo = "Sin Título"
    title_match = re.search(r'(?i)titutlo:\s*(.+)', content)
    if title_match:
        titulo = title_match.group(1).strip()
    
    original_msg_ids = []
    if '---- ORIGINAL LINKS ----' in content:
        orig_section = content.split('---- ORIGINAL LINKS ----')[1]
        if '----' in orig_section:
            orig_section = orig_section.split('----')[0]
        matches = re.findall(r'https://t\.me/c/\d+/(\d+)', orig_section)
        original_msg_ids = [int(m) for m in matches]

    webp_msg_ids = []
    if '---- WEB P LINKS ----' in content:
        webp_section = content.split('---- WEB P LINKS ----')[1]
        if '----' in webp_section:
            webp_section = webp_section.split('----')[0]
        matches = re.findall(r'https://t\.me/c/\d+/(\d+)', webp_section)
        webp_msg_ids = [int(m) for m in matches]
        
    return filepath, titulo, original_msg_ids, webp_msg_ids

async def download_messages(msg_ids, temp_dir, status_msg):
    downloaded_paths = []
    total = len(msg_ids)
    
    await safe_edit_status(status_msg, f"📥 **[Bot Prime]** Iniciando descarga de {total} páginas desde la base de datos...")
    
    batch_size = 100
    for i in range(0, total, batch_size):
        batch_ids = msg_ids[i:i+batch_size]
        print(f"[Manga Flow] Intentando obtener {len(batch_ids)} mensajes del chat {TELEGRAM_DATA_CHAT_ID}...")
        try:
            messages = await client.get_messages(TELEGRAM_DATA_CHAT_ID, ids=batch_ids)
            print(f"[Manga Flow] Se obtuvieron {len(messages)} mensajes.")
        except Exception as get_err:
            print(f"[Manga Flow] Error en get_messages: {get_err}")
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error de acceso al canal de datos: {get_err}")
            return []
        
        tasks = []
        for m_idx, msg in enumerate(messages):
            if msg and getattr(msg, 'media', None):
                ext = ".jpg"
                if getattr(msg, 'document', None):
                    mime = msg.document.mime_type or ""
                    if "png" in mime: ext = ".png"
                    elif "webp" in mime: ext = ".webp"
                
                real_idx = i + m_idx + 1
                filename = f"{str(real_idx).zfill(3)}_pagina{ext}"
                filepath = os.path.join(temp_dir, filename)
                
                async def _download(msg_to_dl, path_to_save):
                    try:
                        print(f"[Manga Flow] Descargando mensaje {msg_to_dl.id}...")
                        dl_client = client_pool.get_client()
                        await dl_client.download_media(msg_to_dl.media, file=path_to_save)
                        if os.path.exists(path_to_save):
                            print(f"[Manga Flow] Descargado: {path_to_save}")
                            return path_to_save
                    except Exception as e:
                        print(f"Error descargando msj {msg_to_dl.id}: {e}")
                    return None

                tasks.append(_download(msg, filepath))
                
        # Ejecutar descargas de este lote en paralelo
        if tasks:
            results = await asyncio.gather(*tasks)
            for res in results:
                if res:
                    downloaded_paths.append(res)
                    
        await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Descargando imágenes: **{len(downloaded_paths)}/{total}**...")
                
    # Ordenar los paths porque la concurrencia puede desordenarlos
    downloaded_paths.sort()
    return downloaded_paths

def create_pdf(image_paths, output_pdf_path):
    if not image_paths:
        return False
        
    c = canvas.Canvas(output_pdf_path)
    for img_path in image_paths:
        try:
            img = cv2.imread(img_path)
            if img is not None:
                h, w = img.shape[:2]
                c.setPageSize((w, h))
                c.drawImage(img_path, 0, 0, width=w, height=h)
                c.showPage()
            else:
                c.setPageSize(A4)
                c.drawImage(img_path, 0, 0, width=A4[0], height=A4[1])
                c.showPage()
        except Exception as e:
            print(f"Error añadiendo imagen al PDF: {e}")
    c.save()
    return True

async def process_manga_flow(event, formato="album", usar_webp=False):
    chat_id = event.chat_id
    command_text = event.message.message
    parts = command_text.split(maxsplit=1)
    
    if len(parts) < 2:
        await event.reply("❌ Debes proporcionar al menos un ID de manga. Ejemplo: `/manga_flow id1, id2`")
        return
        
    manga_ids = [m_id.strip() for m_id in parts[1].split(',') if m_id.strip()]
    
    for manga_id in manga_ids:
        status_msg = await event.reply(f"🔍 **[Bot Prime]** Buscando el manga `{manga_id}` en la base de datos...")
        
        result = search_manga_in_db(manga_id)
        if not result:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** No se encontró ningún manga con el ID `{manga_id}`.")
            continue
            
        filepath, titulo, original_msg_ids, webp_msg_ids = result
        
        target_ids = webp_msg_ids if usar_webp else original_msg_ids
        if not target_ids:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** El manga `{titulo}` no tiene enlaces {'WebP' if usar_webp else 'Originales'}.")
            continue

        temp_dir = tempfile.mkdtemp(prefix="manga_flow_")
        try:
            downloaded_paths = await download_messages(target_ids, temp_dir, status_msg)
            if not downloaded_paths:
                await safe_edit_status(status_msg, "❌ **[Bot Prime]** Ocurrió un error y no se pudo descargar ninguna imagen de Telegram.")
                continue

            cover_path = downloaded_paths[0]
            content_paths = downloaded_paths  # Enviamos TODAS las imágenes (incluida la 1) en el álbum/ZIP/PDF
            
            caption_portada = f"📚 **Título:** {titulo}\n🆔 **ID:** `{manga_id}`\u200b"

            if formato == "album":
                await safe_edit_status(status_msg, f"⬆️ **[Bot Prime]** Subiendo manga como álbum...")
                await client.send_file(chat_id, cover_path, caption=caption_portada)
                
                for i in range(0, len(content_paths), 10):
                    chunk = content_paths[i:i+10]
                    # Para asegurar que Telethon ponga la marca en el álbum, pasamos una lista de captions
                    captions = ["\u200b"] + [""] * (len(chunk) - 1)
                    await client.send_file(chat_id, chunk, caption=captions)
                    await asyncio.sleep(1)
                
                await safe_edit_status(status_msg, "✅ **[Bot Prime]** Manga subido correctamente.\u200b")
                
            elif formato == "zip":
                await safe_edit_status(status_msg, f"📦 **[Bot Prime]** Comprimiendo {len(content_paths)} imágenes en ZIP...")
                zip_filename = f"{manga_id}.zip"
                zip_path = os.path.join(temp_dir, zip_filename)
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for fpath in content_paths:
                        zipf.write(fpath, arcname=os.path.basename(fpath))
                
                await client.send_file(chat_id, cover_path, caption=caption_portada)
                
                await safe_edit_status(status_msg, f"⬆️ **[Bot Prime]** Subiendo archivo ZIP...")
                await client.send_file(chat_id, zip_path, caption="\u200b")
                await safe_edit_status(status_msg, "✅ **[Bot Prime]** Manga ZIP subido correctamente.\u200b")
                
            elif formato == "pdf":
                await safe_edit_status(status_msg, f"📄 **[Bot Prime]** Generando archivo PDF con {len(content_paths)} imágenes...")
                pdf_filename = f"{manga_id}.pdf"
                pdf_path = os.path.join(temp_dir, pdf_filename)
                
                create_pdf(content_paths, pdf_path)
                
                await client.send_file(chat_id, cover_path, caption=caption_portada)
                
                await safe_edit_status(status_msg, f"⬆️ **[Bot Prime]** Subiendo archivo PDF...")
                await client.send_file(chat_id, pdf_path, caption="\u200b")
                await safe_edit_status(status_msg, "✅ **[Bot Prime]** Manga PDF subido correctamente.\u200b")

        except Exception as e:
            print(f"[Error Manga Flow] {e}")
            try:
                await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Ocurrió un error interno: {e}")
            except:
                pass
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            await asyncio.sleep(2) # Pausa entre mangas

async def handle_manga_flow(event):
    await process_manga_flow(event, formato="album", usar_webp=False)

async def handle_manga_flow_pdf(event):
    await process_manga_flow(event, formato="pdf", usar_webp=False)
    
async def handle_manga_flow_zip(event):
    await process_manga_flow(event, formato="zip", usar_webp=False)
    
async def handle_manga_flow_webp(event):
    await process_manga_flow(event, formato="album", usar_webp=True)

async def handle_manga_flow_pdf_webp(event):
    await process_manga_flow(event, formato="pdf", usar_webp=True)

async def handle_manga_flow_zip_webp(event):
    await process_manga_flow(event, formato="zip", usar_webp=True)
