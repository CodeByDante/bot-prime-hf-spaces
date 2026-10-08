import os
import re
import time
import asyncio
import urllib.parse
import random
from curl_cffi import requests
from bs4 import BeautifulSoup
from telethon import events
from telethon.errors import FloodWaitError
from core.client import client
from utils.helpers import clean_comparison_string, safe_edit_status
from utils.channel_resolver import matches_channel


# Expresión regular para códigos JAV (ej: PRED-769, DVDMS-149, GVG-707, etc.)
JAV_REGEX = re.compile(r'\b([a-zA-Z0-9]{2,10}-\d{2,7})\b')

# Prefijos excluidos comunes para evitar falsos positivos
EXCLUDED_PREFIXES = {
    'ep', 'pt', 'part', 'cap', 'vol', 'v', 'ed', 'id', 'p',
    'dvd', 'cd', 'mp4', 'mkv', 'avi', 'gif', 'png', 'jpg'
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def determine_censorship(text):
    text_lower = text.lower()
    # Buscar "sin censura", "uncensored" o "s/c"
    if "sin censura" in text_lower or "uncensored" in text_lower or re.search(r'\b(?:s/c|sin_censura)\b', text_lower):
        return "sin censura"
    # Buscar "con censura", "tiene censura", "censored" o "c/c"
    if "con censura" in text_lower or "tiene censura" in text_lower or "censored" in text_lower or re.search(r'\b(?:c/c|con_censura)\b', text_lower):
        return "con censura"
    return None

def extract_part(text):
    # Buscar formato "1/2", "[1/2]", "(1/2)" o "1 de 2"
    match = re.search(r'\[?(\d+)\s*(?:/|de)\s*(\d+)\]?', text, re.IGNORECASE)
    if match:
        p_num = int(match.group(1))
        p_tot = int(match.group(2))
        return f"[{p_num}/{p_tot}]", (p_num, p_tot)
    
    # Buscar formato "parte 1", "part 2", "pt 3"
    match = re.search(r'\b(?:part|parte|pt)\.?\s*(\d+)\b', text, re.IGNORECASE)
    if match:
        p_num = int(match.group(1))
        return f"[{p_num}]", (p_num, 99)
        
    return "", (0, 0)

def check_cover_exists(photo_caption, code, censorship):
    if not photo_caption:
        return False
    caption_clean = clean_comparison_string(photo_caption)
    code_clean = clean_comparison_string(code)
    
    # El código debe estar en la descripción de la foto
    if code_clean not in caption_clean:
        return False
        
    # Si se especificó censura, la descripción debe contenerla (ej: "sin censura")
    if censorship:
        censorship_clean = clean_comparison_string(censorship)
        if censorship_clean not in caption_clean:
            return False
            
    return True



def download_image_direct(url, filepath):
    headers = {"User-Agent": USER_AGENT, "Referer": "https://missav.ws/"}
    hd_url = url
    if "cover-t.jpg" in url: hd_url = url.replace("cover-t.jpg", "cover.jpg")
    elif "cover-t." in url: hd_url = url.replace("cover-t.", "cover.")
    elif "-t." in url: hd_url = url.replace("-t.", ".")
        
    try:
        r = requests.get(hd_url, headers=headers, timeout=15, impersonate="chrome")
        if r.status_code == 200:
            with open(filepath, 'wb') as f: f.write(r.content)
            return True
        elif hd_url != url:
            r = requests.get(url, headers=headers, timeout=15, impersonate="chrome")
            if r.status_code == 200:
                with open(filepath, 'wb') as f: f.write(r.content)
                return True
    except Exception as e:
        print(f"[-] Error descargando imagen: {e}")
    return False

def check_direct_url(search_code, force_uncensored):
    headers = {"User-Agent": USER_AGENT, "Referer": "https://missav.ws/"}
    urls_to_try = []
    if force_uncensored is True:
        urls_to_try.append((f"https://missav.ws/en/{search_code.lower()}-uncensored-leak", True))
    elif force_uncensored is False:
        urls_to_try.append((f"https://missav.ws/en/{search_code.lower()}", False))
    else:
        urls_to_try.append((f"https://missav.ws/en/{search_code.lower()}-uncensored-leak", True))
        urls_to_try.append((f"https://missav.ws/en/{search_code.lower()}", False))
        
    matches = []
    for target_url, is_uncensored in urls_to_try:
        try:
            time.sleep(random.uniform(0.5, 1.0))
            r = requests.get(target_url, headers=headers, timeout=15, impersonate="chrome")
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                video = soup.find('video', class_='player')
                if video and video.get('data-poster'):
                    matches.append({'img_url': video.get('data-poster'), 'is_uncensored': is_uncensored})
        except Exception:
            pass
    return matches

def search_code_in_page(url, search_code):
    headers = {"User-Agent": USER_AGENT, "Referer": "https://missav.ws/"}
    for attempt in range(3):
        try:
            time.sleep(random.uniform(0.5, 1.5))
            r = requests.get(url, headers=headers, timeout=15, impersonate="chrome")
            if r.status_code in [403, 429, 503]:
                time.sleep(random.uniform(3.0, 5.0))
                continue
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, "html.parser")
            if soup.title and "Just a moment" in soup.title.text:
                time.sleep(random.uniform(4.0, 6.0))
                continue
                
            matches = []
            thumbnails = soup.find_all(class_=lambda x: x and 'thumbnail' in x)
            for thumb in thumbnails:
                card_text = thumb.get_text(strip=True).upper()
                if search_code in card_text:
                    img = thumb.find('img')
                    if img and not (img.get('data-src') or img.get('src')).startswith("data:image"):
                        img_url = img.get('data-src') or img.get('src')
                        video_href = ""
                        video_title = ""
                        for a in thumb.find_all('a'):
                            if a.get('href'): video_href = a.get('href')
                            if a.get('title'): video_title = a.get('title')
                        lower_text = f"{video_href} {video_title} {card_text}".lower()
                        is_uncensored = "uncensored" in lower_text or "sin censura" in lower_text or "無碼" in lower_text
                        matches.append({'img_url': img_url, 'is_uncensored': is_uncensored})
            return matches
        except Exception:
            time.sleep(random.uniform(2.0, 4.0))
    return []

def search_and_download_missav(search_code, censorship, filepath):
    # force_uncensored: True para sin censura, False para con censura
    force_uncensored = None
    if censorship == "sin censura":
        force_uncensored = True
    elif censorship == "con censura":
        force_uncensored = False
        
    search_url = f"https://missav.ws/en/search/{search_code}"
    matches = search_code_in_page(search_url, search_code)
    
    if matches:
        if force_uncensored is True:
            matches = [m for m in matches if m['is_uncensored']]
        elif force_uncensored is False:
            matches = [m for m in matches if not m['is_uncensored']]
            
    if not matches:
        matches = check_direct_url(search_code, force_uncensored)
        
    if matches:
        match = matches[0]
        if download_image_direct(match['img_url'], filepath):
            return True
            
    return False


async def procesar_comando_portada_jav(event):
    chat_id = event.chat_id
    
    # Obtener información del chat
    chat = await event.get_chat()
    chat_title = getattr(chat, 'title', '') or ''
    is_private = event.is_private
    
    # Exclusivo de "JAV PREMIUM"
    if not is_private and not matches_channel(chat_id, chat_title, "jav_premium"):
        error_msg = await event.reply("❌ **[Bot Prime]** Este comando es exclusivo para el canal **JAV PREMIUM**.")
        await asyncio.sleep(5)
        await client.delete_messages(chat_id, [event.id, error_msg.id])
        return

    # Parsear límite opcional de mensajes a escanear (por defecto None para escanear todo)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Analizando videos en {limit_desc}...")
    
    try:
        messages = []
        last_update = time.time()
        
        # 1. Escanear mensajes
        async for m in client.iter_messages(chat_id, limit=limit):
            messages.append(m)
            
            # Throttling de la actualización de estado
            now = time.time()
            if now - last_update > 4.0:
                await safe_edit_status(status_msg, f"🔍 **[Bot Prime]** Analizando mensajes... ({len(messages)} analizados)")
                last_update = now
                
        # 2. Agrupar videos por (code, censorship)
        groups = {}
        for msg in messages:
            if not msg.video:
                continue
                
            text_sources = []
            if msg.message:
                text_sources.append(msg.message)
            if msg.file and msg.file.name:
                text_sources.append(msg.file.name)
                
            full_text = " ".join(text_sources)
            if not full_text:
                continue
                
            matches = JAV_REGEX.findall(full_text)
            if not matches:
                continue
                
            code = matches[0].upper()
            prefix = code.split('-')[0]
            if prefix.lower() in EXCLUDED_PREFIXES:
                continue
                
            censorship = determine_censorship(full_text)
            part_str, part_tuple = extract_part(full_text)
            
            key = (code, censorship)
            if key not in groups:
                groups[key] = []
            groups[key].append({
                'msg': msg,
                'part_sort': part_tuple,
                'full_text': full_text
            })
            
        if not groups:
            await safe_edit_status(status_msg, "❌ **[Bot Prime]** No se encontraron videos con códigos JAV válidos.")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        await safe_edit_status(status_msg, f"📦 **[Bot Prime]** Detectados {len(groups)} grupos de videos JAV. Verificando portadas...")
        await asyncio.sleep(2)
        
        # 3. Procesar cada grupo de JAV
        OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "capturas")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        processed_count = 0
        skipped_count = 0
        
        for (code, censorship), group_items in groups.items():
            # Título esperado de la portada (ej: GVG-707 (sin censura))
            expected_caption = f"{code} ({censorship})" if censorship else code
            
            # Verificar si ya existe un mensaje de foto con esta portada en los escaneados
            cover_exists = False
            for m in messages:
                if m.photo and check_cover_exists(m.message, code, censorship):
                    cover_exists = True
                    break
                        
            if not cover_exists:
                # Comprobar historial más atrás buscando por el código JAV
                async for m in client.iter_messages(chat_id, search=code, limit=20):
                    if m.photo and check_cover_exists(m.message, code, censorship):
                        cover_exists = True
                        break
                            
            if cover_exists:
                print(f"[Portadas] '{expected_caption}' ya tiene portada. Saltando.")
                skipped_count += 1
                continue
                
            # No tiene portada -> Buscarla
            await safe_edit_status(status_msg, f"🌐 **[Bot Prime]** Buscando portada para: '{expected_caption}'...")
            
            clean_code = re.sub(r'[\\/*?:"<>|]', "", code)
            filename = f"portada_{clean_code}.jpg"
            filepath = os.path.join(OUTPUT_DIR, filename)
            
            # Descargar portada de MissAV de forma asíncrona
            downloaded = await asyncio.to_thread(search_and_download_missav, code, censorship, filepath)
            
            if not downloaded:
                print(f"[Portadas] Falló descarga de portada en MissAV para '{expected_caption}'.")
                continue
                
            # Enviar la portada
            await safe_edit_status(status_msg, f"📤 **[Bot Prime]** Enviando portada para: '{expected_caption}'...")
            try:
                cover_msg = await client.send_file(
                    chat_id,
                    file=filepath,
                    caption=expected_caption
                )
            except Exception as e:
                print(f"[Portadas] Error enviando portada: {e}")
                if os.path.exists(filepath):
                    os.remove(filepath)
                continue
                
            if os.path.exists(filepath):
                os.remove(filepath)
                
            # Reenviar las partes de video ordenadas
            group_items.sort(key=lambda x: (x['part_sort'], x['msg'].id))
            
            sent_successfully = []
            for item in group_items:
                msg = item['msg']
                await safe_edit_status(status_msg, f"📤 **[Bot Prime]** Reenviando video part/id {msg.id} de '{expected_caption}'...")
                
                retries = 2
                while retries > 0:
                    try:
                        new_msg = await client.send_file(
                            chat_id,
                            file=msg.media,
                            caption=msg.message,
                            formatting_entities=msg.entities
                        )
                        sent_successfully.append((msg.id, new_msg))
                        break
                    except FloodWaitError as e:
                        print(f"[Portadas] FloodWait: esperando {e.seconds} seg...")
                        await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite. Esperando {e.seconds} seg...")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"[Portadas] Error reenviando video: {e}")
                        retries -= 1
                        await asyncio.sleep(2)
                        
                await asyncio.sleep(2.5)
                
            # Borrar los videos antiguos si se completó con éxito
            if len(sent_successfully) == len(group_items):
                old_ids = [item[0] for item in sent_successfully]
                await client.delete_messages(chat_id, old_ids)
                processed_count += 1
            else:
                print(f"[Portadas] Advertencia: No se reenviaron todos los videos de '{expected_caption}'. No eliminados.")
                
            await asyncio.sleep(2)
            
        summary_text = (
            f"✅ **[Bot Prime]** Proceso de portadas completado.\n\n"
            f"• Procesados con portada nueva: {processed_count}\n"
            f"• Ya contaban con portada (omitidos): {skipped_count}"
        )
        await safe_edit_status(status_msg, summary_text)
        await asyncio.sleep(15)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(10)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
