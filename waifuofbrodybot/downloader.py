
import re
import math
import os
import time
import asyncio
import yt_dlp
import shutil
import subprocess
import aiohttp
import random
from bs4 import BeautifulSoup
from curl_cffi import requests as c_requests
from pyrogram import enums
from config import LIMIT_2GB, HAS_FAST, DOWNLOAD_DIR, TOOLS_DIR, FAST_PATH
from database import get_config, downloads_db, guardar_db, add_active, remove_active, update_progress, url_storage
from utils import sel_cookie, traducir_texto, format_bytes, split_video_by_size, split_file_into_volumes
from utils_chat_actions import chat_action_loop
from tools_media import get_thumb, get_meta, get_audio_dur, progreso, fast_remux_mp4
from firebase_service import get_cached_file, save_cached_file, get_bot_config, delete_cached_file, save_user_config_fb, get_cached_file_strict, save_cached_file_strict

# --- HELPER: SAFE BACKUP ---
 


# Límite real de Telegram para dividir (1.9 GB para ir seguros)
TG_LIMIT = int(1.9 * 1024 * 1024 * 1024)

# --- USER-AGENT ROTATION SYSTEM ---
USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    # Firefox macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    # Safari iPhone/iOS
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1",
    # Chrome Android
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

# --- SEMAFORO GLOBAL DE DESCARGAS (Max 5) ---
SEM_DOWNLOAD = asyncio.Semaphore(5)

# --- SEMAFORO EXCLUSIVO PARA SURRIT/MISSAV (Max 10) ---
SEM_SURRIT = asyncio.Semaphore(10)

USER_SEMAPHORES = {}

def get_user_semaphore(chat_id, is_surrit, max_downloads):
    # Determine the limit
    if max_downloads == 5:
        limit = 5
    elif max_downloads == 10:
        limit = 10
    else: # 'default' / None / 'predeterminado'
        limit = 10 if is_surrit else 5
        
    key = (chat_id, limit)
    
    # If not exists, create the semaphore
    if key not in USER_SEMAPHORES:
        USER_SEMAPHORES[key] = asyncio.Semaphore(limit)
        
    return USER_SEMAPHORES[key]


# Detectamos si tienes la herramienta Turbo instalada (Cross-Platform)
# Priorizamos tools/
RE_NAME = "N_m3u8DL-RE.exe" if os.name == 'nt' else "N_m3u8DL-RE"
RE_PATH = os.path.join(TOOLS_DIR, RE_NAME)

if not os.path.exists(RE_PATH):
    RE_PATH = shutil.which("N_m3u8DL-RE") 
    if not RE_PATH:
         if os.path.exists("N_m3u8DL-RE.exe"): RE_PATH = "N_m3u8DL-RE.exe"
         elif os.path.exists("N_m3u8DL-RE"): RE_PATH = "./N_m3u8DL-RE"

HAS_RE = RE_PATH is not None and os.path.exists(RE_PATH)

async def get_mediafire_link(url):
    try:
        from utils import load_cookies_dict
        cookies = load_cookies_dict(sel_cookie(url))
        async with aiohttp.ClientSession(cookies=cookies) as session:
            headers = {"User-Agent": get_random_user_agent()}
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200: return None
                text = await resp.text()
                match = re.search(r'href="([^"]+)"\s+id="downloadButton"', text)
                if match: return match.group(1)
                match2 = re.search(r'href="([^"]+)"[^>]+aria-label="Download file"', text)
                if match2: return match2.group(1)
    except Exception as e: print(f"Error Mediafire: {e}")
    return None

async def get_all_hentaila_episodes(url):
    try:
        from utils import load_cookies_dict
        cookies = load_cookies_dict(sel_cookie(url))
        headers = {"User-Agent": get_random_user_agent()}
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200: return [url]
                text = await resp.text()
                
                # Check JSON for episodes array like: episodes:[{id:2089,number:1},{id:2090,number:2}]
                match = re.search(r'episodes:\[(.*?)\]', text)
                if match:
                    episodes_raw = match.group(1)
                    numbers = re.findall(r'number:(\d+)', episodes_raw)
                    if numbers:
                        # Ensure we get clean base URL, strip trailing slash and numbers
                        base_url = re.sub(r'/\d+/?$', '', url.strip('/'))
                        return [f"{base_url}/{num}" for num in numbers]
                        
    except Exception as e:
        print(f"Error extracting hentaila episodes: {e}")
    return [url] # return original if failed

async def get_hentaila_link(url):
    try:
        from utils import load_cookies_dict
        cookies = load_cookies_dict(sel_cookie(url))
        headers = {"User-Agent": get_random_user_agent()}
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200: return None, None
                text = await resp.text()
                
                # Extraer título "Anime Episodio X" -> "Anime\nEpisodio X"
                hl_title = None
                match_title = re.search(r'<title>(.*?)\s+HentaiLA\s*-', text, re.IGNORECASE)
                if match_title:
                    raw_t = match_title.group(1).strip()
                    hl_title = re.sub(r'\s+(Episodio\s+\d+)$', r' \1', raw_t, flags=re.IGNORECASE)
                elif re.search(r'<title>(.*?)</title>', text, re.IGNORECASE):
                    # Fallback si cambia el título de la página
                    raw_t = re.search(r'<title>(.*?)</title>', text, re.IGNORECASE).group(1).split(" HentaiLA")[0].strip()
                    hl_title = re.sub(r'\s+(Episodio\s+\d+)$', r' \1', raw_t, flags=re.IGNORECASE)
                
                servers = re.findall(r'server\s*:\s*"([^"]+)"\s*,\s*url\s*:\s*"([^"]+)"', text, re.IGNORECASE)
                hl_servers = {s.upper(): u.replace('\\/', '/') for s, u in servers}
                return hl_servers, hl_title
    except Exception as e: print(f"Error HentaiLA: {e}")
    return None, None

async def get_fireload_link(url):
    try:
        from utils import load_cookies_dict
        cookies = load_cookies_dict(sel_cookie(url))
        headers = {"User-Agent": get_random_user_agent()}
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200: return None, None
                text = await resp.text()
                match = re.search(r'window\.Fl\s*=\s*({[^}]+})', text)
                if match:
                    import json
                    try:
                        data = json.loads(match.group(1))
                        dlink = data.get('dlink')
                        if dlink: return dlink, None
                    except: pass
    except Exception as e: print(f"Error FireLoad: {e}")
    return None, None

async def get_yourupload_link(url):
    try:
        from utils import load_cookies_dict
        cookies = load_cookies_dict(sel_cookie(url))
        headers = {"User-Agent": get_random_user_agent(), "Referer": url}
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200: return None
                text = await resp.text()
                match_og = re.search(r'property="og:video"\s+content="([^"]+)"', text)
                if match_og: return match_og.group(1)
                match_jw = re.search(r"file\s*:\s*['\"]([^'\"]+)['\"]", text)
                if match_jw:
                    link = match_jw.group(1)
                    return "https://www.yourupload.com" + link if link.startswith("/") else link
    except Exception as e: print(f"Error YourUpload: {e}")
    return None

async def get_mp4upload_link(url):
    try:
        if "embed-" not in url:
            vid_id = url.split("/")[-1].replace(".html", "")
            url = f"https://www.mp4upload.com/embed-{vid_id}.html"

        from utils import load_cookies_dict
        cookies = load_cookies_dict(sel_cookie(url))
        headers = {"User-Agent": get_random_user_agent(), "Referer": url}
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200: return None
                text = await resp.text()
                match = re.search(r'src:\s*"([^"]+\.mp4)"', text)
                if match: return match.group(1)
    except Exception as e: print(f"Error MP4Upload: {e}")
    return None

async def get_eporner_links(url):
    """Scrapes Eporner download links from a video page URL"""
    try:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        import re
        from curl_cffi.requests import AsyncSession
        
        # Normalize URL to www.eporner.com
        clean_url = re.sub(r'https?://\w+\.eporner\.com', 'https://www.eporner.com', url)
        
        from utils import load_cookies_dict, sel_cookie
        cookie_file = sel_cookie(clean_url)
        cookies = load_cookies_dict(cookie_file) if cookie_file else {}
        
        html = None
        r_status = None
        impersonate_targets = ["chrome120", "chrome124", "safari18_0", "chrome119"]
        
        for attempt in range(1, 11):
            try:
                print(f"🔄 [Eporner Extractor] Intento {attempt}/10 con cookies...")
                imp = impersonate_targets[attempt % len(impersonate_targets)]
                
                async with AsyncSession(impersonate=imp, cookies=cookies) as session:
                    resp = await session.get(clean_url, timeout=15)
                    r_status = resp.status_code
                    if resp.status_code not in [403, 503]:
                        html = resp.text
                        print(f"✅ [Eporner Extractor] Intento {attempt} exitoso! (HTTP {resp.status_code})")
                        break
                    else:
                        print(f"⚠️ [Eporner Extractor] Intento {attempt} bloqueado por Cloudflare o error (HTTP {resp.status_code})")
            except Exception as e_att:
                print(f"⚠️ [Eporner Extractor] Intento {attempt} falló con error: {e_att}")
            
            if not html and attempt < 10:
                await asyncio.sleep(2)
                
        if not html:
            print(f"❌ [Eporner Extractor] Todos los intentos de bypass fallaron (Último status: {r_status})")
            return "Eporner Video", []

                
        soup = BeautifulSoup(html, "html.parser")
        
        # Get Title
        title_el = soup.find('h1')
        if title_el:
            title = "".join([t for t in title_el.contents if isinstance(t, str)]).strip()
            if not title:
                title = title_el.text.strip()
        else:
            title = "Eporner Video"
            
        downloaddiv = soup.find(id="downloaddiv")
        a_tags = downloaddiv.find_all('a', href=re.compile(r'/dload/')) if downloaddiv else soup.find_all('a', href=re.compile(r'/dload/'))
        
        links = []
        for a in a_tags:
            href = a['href']
            download_url = urljoin("https://www.eporner.com", href)
            text = a.text.strip()
            
            match = re.search(r'(\d+p)\s*,\s*([\w\d]+)\s*,\s*([\d\.]+\s*[KMGT]?B)', text, re.I)
            if match:
                quality = match.group(1)
                codec = match.group(2)
                size = match.group(3)
            else:
                q_match = re.search(r'/(\d{3,4})/', href)
                quality = f"{q_match.group(1)}p" if q_match else "unknown"
                codec = "AV1" if "av1" in href.lower() else "h264"
                size = "unknown size"
                
            label = f"{quality} ({codec}, {size})"
            
            links.append({
                'url': download_url,
                'quality': quality,
                'codec': codec,
                'size': size,
                'label': label,
                'res': label
            })
            
        return title, links
    except Exception as e:
        print(f"Error scraping Eporner: {e}")
        return "Eporner Video", []

def find_best_quality_index(links):
    # Filter for h264 first, falling back to all links if not available
    h264_links = [(idx, l) for idx, l in enumerate(links) if l['codec'].lower() == 'h264']
    candidates = h264_links if h264_links else list(enumerate(links))
    
    best_idx = 0
    best_val = -1
    for idx, l in candidates:
        try:
            val = int(l['quality'].replace('p', ''))
        except:
            val = 0
        if val > best_val:
            best_val = val
            best_idx = idx
    return best_idx

def find_worst_quality_index(links):
    # Filter for h264 first, falling back to all links if not available
    h264_links = [(idx, l) for idx, l in enumerate(links) if l['codec'].lower() == 'h264']
    candidates = h264_links if h264_links else list(enumerate(links))
    
    worst_idx = 0
    worst_val = 999999
    for idx, l in candidates:
        try:
            val = int(l['quality'].replace('p', ''))
        except:
            val = 999999
        if val < worst_val:
            worst_val = val
            worst_idx = idx
    return worst_idx

def find_fixed_quality_index(links, target_res):
    # Filter for h264 first, falling back to all links if not available
    h264_links = [(idx, l) for idx, l in enumerate(links) if l['codec'].lower() == 'h264']
    candidates = h264_links if h264_links else list(enumerate(links))
    
    below = []
    for idx, l in candidates:
        try:
            val = int(l['quality'].replace('p', ''))
        except:
            val = 0
        if val <= target_res:
            below.append((val, idx))
            
    if below:
        below.sort(key=lambda x: x[0], reverse=True)
        return below[0][1]
    else:
        # Sort ascending to get the lowest of the higher resolutions
        with_res = []
        for idx, l in candidates:
            try:
                val = int(l['quality'].replace('p', ''))
            except:
                val = 999999
            with_res.append((val, idx))
        with_res.sort(key=lambda x: x[0])
        return with_res[0][1]

async def get_xhamster_link(url):
    """Extrae el link m3u8 directo de xhamster usando curl_cffi para evitar bloqueos"""
    try:
        from curl_cffi.requests import AsyncSession
        import re
        import json
        from utils import load_cookies_dict
        
        cookies_dict = load_cookies_dict(sel_cookie(url))
        async with AsyncSession(impersonate='chrome', cookies=cookies_dict) as s:
            r = await s.get(url)
            if r.status_code == 200:
                t = r.text
                
                # Si es una página de creador/shorts, buscar el primer short
                if "/creators/" in url and "/shorts" in url:
                    match_short = re.search(r'href="(https://[^\"\']+/shorts/[^\"\']+)"', t)
                    if match_short:
                        short_url = match_short.group(1)
                        print("Found short URL:", short_url)
                        r2 = await s.get(short_url)
                        if r2.status_code == 200:
                            t = r2.text
                
                m3u8_url = None
                
                # Buscar en JSON primero (evita problemas de escapes como \\/)
                match_json = re.search(r'window\.(?:initials|__INITIAL_STATE__)\s*=\s*(\{.*?\});', t)
                if match_json:
                    try:
                        data = json.loads(match_json.group(1))
                        data_str = json.dumps(data)
                        match_m3u8 = re.search(r'(https?://[^\s\"\']+\.m3u8)', data_str)
                        if match_m3u8:
                            m3u8_url = match_m3u8.group(1)
                    except Exception as e:
                        print("JSON parse error:", e)
                
                # Fallback regex directo
                if not m3u8_url:
                    match_url = re.search(r'(https?://[^\s\"\']+\.m3u8)', t)
                    if match_url:
                        m3u8_url = match_url.group(1).replace('\\/', '/')
                
                # Fallback regex con escaped slashes
                if not m3u8_url:
                    match_url = re.search(r'(https?:\/\/[^\s\"\']+\.m3u8)', t)
                    if match_url:
                        m3u8_url = match_url.group(1).replace('\\/', '/')
                        
                title = "Video de XHamster"
                match_title = re.search(r'<title[^>]*>(.*?)</title>', t, re.IGNORECASE)
                if match_title:
                    title = match_title.group(1).split('| xHamster')[0].replace('- xHamster', '').strip()
                
                if m3u8_url:
                    return m3u8_url, title
    except Exception as e:
        print(f"Error XHamster M3U8: {e}")
    return None, None

async def get_xvideos_link(url):
    """Extrae el link m3u8 directo de xvideos usando curl_cffi para evitar bloqueos"""
    try:
        from curl_cffi.requests import AsyncSession
        import re
        import html
        from utils import load_cookies_dict
        
        cookie_path = sel_cookie(url)
        cookies_dict = load_cookies_dict(cookie_path)
        print(f"🍪 [XVideos Extractor] Cargando cookies desde: {cookie_path} (Cargadas: {len(cookies_dict)})")
        async with AsyncSession(impersonate='chrome', cookies=cookies_dict) as s:
            r = await s.get(url)
            print(f"📥 [XVideos Extractor] HTTP Status: {r.status_code} (HTML length: {len(r.text) if r.text else 0})")
            if r.status_code == 200:
                t = r.text
                
                m3u8_url = None
                match_hls = re.search(r"html5player\.setVideoHLS\s*\(\s*['\"](https?://[^'\"]+\.m3u8[^'\"]*)['\"]\s*\)", t)
                if not match_hls:
                    match_hls = re.search(r"html5player\.setVideoHLS\s*\(\s*['\"](https?(?::\\/\\/|:\/\/)[^'\"]+\.m3u8[^'\"]*)['\"]\s*\)", t)
                
                if match_hls:
                    m3u8_url = match_hls.group(1).replace('\\/', '/')
                    
                title = "Video de XVideos"
                match_title_tag = re.search(r'<title[^>]*>(.*?)</title>', t, re.IGNORECASE)
                if match_title_tag:
                    title = match_title_tag.group(1)
                    title = re.split(r'\s+-\s+xvideos', title, flags=re.IGNORECASE)[0].strip()
                else:
                    match_player_title = re.search(r"html5player\.setVideoTitle\s*\(\s*['\"](.*?)['\"]\s*\)", t)
                    if match_player_title:
                        title = match_player_title.group(1)
                        
                title = html.unescape(title).strip()
                
                if m3u8_url:
                    return m3u8_url, title
    except Exception as e:
        print(f"Error XVideos M3U8: {e}")
    return None, None

async def get_pornhub_link(url, calidad='best'):
    """Extrae el link m3u8 directo de Pornhub usando curl_cffi para evitar bloqueos"""
    try:
        from curl_cffi.requests import AsyncSession
        import re
        import html
        from utils import load_cookies_dict
        
        cookie_path = sel_cookie(url)
        cookies_dict = load_cookies_dict(cookie_path)
        print(f"🍪 [Pornhub Extractor] Cargando cookies desde: {cookie_path} (Cargadas: {len(cookies_dict)})")
        async with AsyncSession(impersonate='chrome', cookies=cookies_dict) as s:
            r = await s.get(url)
            print(f"📥 [Pornhub Extractor] HTTP Status: {r.status_code} (HTML length: {len(r.text) if r.text else 0})")
            if r.status_code == 200:
                t = r.text
                
                # Find all video URLs
                matches = re.findall(r'"videoUrl"\s*:\s*"([^"]+?)"', t)
                m3u8_links = []
                for m in matches:
                    m_clean = m.replace('\\/', '/')
                    if 'm3u8' in m_clean:
                        if m_clean not in m3u8_links:
                            m3u8_links.append(m_clean)
                
                print(f"🔍 [Pornhub Extractor] Enlaces HLS encontrados: {len(m3u8_links)}")
                if not m3u8_links:
                    return None, None
                
                # Parse qualities
                parsed_links = []
                for link in m3u8_links:
                    res_match = re.search(r'/(\d+)P_', link, re.IGNORECASE)
                    res = int(res_match.group(1)) if res_match else 0
                    parsed_links.append({'res': res, 'url': link})
                
                # Sort descending
                parsed_links.sort(key=lambda x: x['res'], reverse=True)
                
                # Select URL
                selected_url = None
                if calidad == 'best' or calidad == 'direct':
                    selected_url = parsed_links[0]['url']
                elif calidad == 'worst':
                    selected_url = parsed_links[-1]['url']
                else:
                    try:
                        target_res = int(calidad)
                        best_match = None
                        for pl in parsed_links:
                            if pl['res'] <= target_res:
                                best_match = pl['url']
                                break
                        selected_url = best_match or parsed_links[-1]['url']
                    except:
                        selected_url = parsed_links[0]['url']
                        
                title = "Video de Pornhub"
                match_title = re.search(r'<title[^>]*>(.*?)</title>', t, re.IGNORECASE)
                if match_title:
                    title = match_title.group(1)
                    title = re.split(r'\s+-\s+Pornhub', title, flags=re.IGNORECASE)[0].strip()
                title = html.unescape(title).strip()
                
                return selected_url, title
    except Exception as e:
        print(f"Error Pornhub M3U8: {e}")
    return None, None

async def get_cobalt_link(url, quality='1080'):
    """
    Usa la API de Cobalt v10 para obtener un link directo.
    Disabled: API requires auth now.
    """
    return None

async def get_tikwm_data(url):
    """
    Fallback for TikTok using TikWM API (Supports Images/Slideshows).
    """
    try:
        api_url = f"https://www.tikwm.com/api/?url={url}"
        print(f"🎵 TikWM Request: {api_url}")
        
        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": get_random_user_agent()}
            async with session.get(api_url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('code') == 0:
                        return data.get('data')
                    else:
                        print(f"⚠️ TikWM API Error: {data}")
    except Exception as e:
        print(f"❌ TikWM Error: {e}")
    return None

def clean_filename_thumb(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

def download_image_direct(url, filepath):
    headers = {
        "User-Agent": get_random_user_agent(),
        "Referer": "https://missav.ws/"
    }
    hd_url = url
    if "cover-t.jpg" in url: hd_url = url.replace("cover-t.jpg", "cover.jpg")
    elif "cover-t." in url: hd_url = url.replace("cover-t.", "cover.")
    elif "-t." in url: hd_url = url.replace("-t.", ".")
    try:
        r = c_requests.get(hd_url, headers=headers, timeout=15, impersonate="chrome")
        if r.status_code == 200:
            with open(filepath, 'wb') as f: f.write(r.content)
            return True
        elif hd_url != url:
            r = c_requests.get(url, headers=headers, timeout=15, impersonate="chrome")
            if r.status_code == 200:
                with open(filepath, 'wb') as f: f.write(r.content)
                return True
    except Exception as e:
        print(f"[-] Error descargando miniatura directa: {e}")
    return False

def check_direct_url(search_code, force_uncensored):
    headers = {"User-Agent": get_random_user_agent(), "Referer": "https://missav.ws/"}
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
            r = c_requests.get(target_url, headers=headers, timeout=15, impersonate="chrome")
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                video = soup.find('video', class_='player')
                if video and video.get('data-poster'):
                    matches.append({'img_url': video.get('data-poster'), 'is_uncensored': is_uncensored})
        except:
            pass
    return matches

def search_code_in_page(url, search_code):
    headers = {"User-Agent": get_random_user_agent(), "Referer": "https://missav.ws/"}
    for attempt in range(3):
        try:
            time.sleep(random.uniform(0.5, 1.5))
            r = c_requests.get(url, headers=headers, timeout=15, impersonate="chrome")
            if r.status_code in [403, 429, 503]:
                time.sleep(random.uniform(3.0, 5.0))
                continue
            if r.status_code != 200: return []
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
                    if img and img.get('data-src'):
                        img_url = img.get('data-src')
                        lower_text = card_text.lower()
                        is_uncensored = "uncensored" in lower_text or "sin censura" in lower_text or "無修正" in lower_text
                        matches.append({'img_url': img_url, 'is_uncensored': is_uncensored})
            return matches
        except:
            time.sleep(random.uniform(2.0, 4.0))
    return []

def download_missav_thumbnail(search_code, force_uncensored, output_dir):
    print(f"[*] Buscando miniatura para {search_code}...")
    code_clean = clean_filename_thumb(search_code)
    
    possible_names = []
    if force_uncensored is True: possible_names = [f"{code_clean} (sin censura).jpg"]
    elif force_uncensored is False: possible_names = [f"{code_clean} (con censura).jpg"]
    else: possible_names = [f"{code_clean} (sin censura).jpg", f"{code_clean}.jpg"]
    
    for p_name in possible_names:
        if os.path.exists(os.path.join(output_dir, p_name)):
            print(f"[*] Miniatura ya existe: {p_name}")
            return ('success', p_name, '')

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
        suffix = " (sin censura)" if force_uncensored is True else (" (con censura)" if force_uncensored is False else (" (sin censura)" if match['is_uncensored'] else ""))
        filename = f"{code_clean}{suffix}.jpg"
        filepath = os.path.join(output_dir, filename)
        if download_image_direct(match['img_url'], filepath):
            print(f"[+] Miniatura guardada: {filename}")
            return ('success', filename, '')
            
    return ('failed', '', '')

async def download_surrit_custom(url_descarga, pure_name, chat_id, status, datos, task_key):
    import urllib.parse
    import re
    import time
    import aiofiles
    from curl_cffi.requests import AsyncSession
    
    referer = "https://missav.ws/"
    
    if status:
        try: await status.edit("🔄 [Surrit Turbo] Analizando enlace de video...")
        except: pass

    try:
        async with AsyncSession() as session:
            impersonate_targets = ["chrome120", "chrome124", "safari18_0", "chrome119", "chrome116", "edge120"]
            headers = {
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://missav.ws",
                "Referer": referer,
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "cross-site",
                "Connection": "keep-alive"
            }
            
            # 1. Fetch master playlist
            r = None
            working_imp = "chrome120"
            for attempt in range(1, 21):
                try:
                    imp = impersonate_targets[attempt % len(impersonate_targets)]
                    print(f"[Surrit Turbo] Fetching master playlist (Attempt {attempt}/20, imp={imp})...")
                    if status:
                        try: await status.edit(f"🔄 [Surrit Turbo] Obteniendo playlist (Intento {attempt}/20)...")
                        except: pass
                        
                    res = await session.get(url_descarga, headers=headers, impersonate=imp, timeout=15)
                    if res.status_code == 200:
                        r = res
                        working_imp = imp
                        break
                    else:
                        print(f"[Surrit Turbo] Attempt {attempt} returned {res.status_code}")
                except Exception as e:
                    print(f"[Surrit Turbo] Attempt {attempt} failed: {e}")
                await asyncio.sleep(2)
                
            if not r:
                print("[Surrit Turbo] Error: Failed to fetch master playlist after 20 attempts.")
                return None
                
            lines = r.text.splitlines()
            streams = []
            base_url = url_descarga.rsplit('/', 1)[0] + '/'
            
            current_inf = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("#EXT-X-STREAM-INF:"):
                    current_inf = line
                elif not line.startswith("#"):
                    sub_url = urllib.parse.urljoin(base_url, line)
                    resolution = "unknown"
                    if current_inf:
                        res_match = re.search(r'RESOLUTION=(\d+x\d+)', current_inf)
                        if res_match:
                            resolution = res_match.group(1)
                    streams.append((resolution, sub_url))
                    current_inf = None
                    
            if not streams:
                print("[Surrit Turbo] No streams found in master playlist.")
                return None
                
            best_res, best_url = streams[-1]
            print(f"[Surrit Turbo] Selected stream: {best_res} -> {best_url}")
            
            # 2. Fetch sub-playlist
            r_sub = None
            for attempt in range(1, 21):
                try:
                    imp = impersonate_targets[attempt % len(impersonate_targets)]
                    print(f"[Surrit Turbo] Fetching sub-playlist (Attempt {attempt}/20, imp={imp})...")
                    if status:
                        try: await status.edit(f"🔄 [Surrit Turbo] Obteniendo segmentos (Intento {attempt}/20)...")
                        except: pass
                        
                    res = await session.get(best_url, headers=headers, impersonate=imp, timeout=15)
                    if res.status_code == 200:
                        r_sub = res
                        working_imp = imp
                        break
                    else:
                        print(f"[Surrit Turbo] Attempt {attempt} returned {res.status_code}")
                except Exception as e:
                    print(f"[Surrit Turbo] Attempt {attempt} failed: {e}")
                await asyncio.sleep(2)
                
            if not r_sub:
                print("[Surrit Turbo] Error: Failed to fetch sub-playlist after 20 attempts.")
                return None
                
            sub_lines = r_sub.text.splitlines()
            segments = []
            sub_base_url = best_url.rsplit('/', 1)[0] + '/'
            
            for line in sub_lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                segment_url = urllib.parse.urljoin(sub_base_url, line)
                segments.append(segment_url)
                
            total_segments = len(segments)
            if total_segments == 0:
                print("[Surrit Turbo] No segments found in sub-playlist.")
                return None
                
            print(f"[Surrit Turbo] Total segments: {total_segments}")
            
            # Create temp directory
            temp_dir = os.path.join("tmp", f"temp_surrit_{pure_name}")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Download segments concurrently
            sem = asyncio.Semaphore(16)
            failed_segments = []
            downloaded_count = 0
            downloaded_bytes = 0
            last_edit = time.time()
            last_bytes = 0
            last_speed_time = time.time()
            
            async def download_segment(idx, seg_url):
                nonlocal downloaded_count, downloaded_bytes, last_edit, last_bytes, last_speed_time
                seg_path = os.path.join(temp_dir, f"{idx}.ts")
                
                # Support resume/check
                if os.path.exists(seg_path) and os.path.getsize(seg_path) > 0:
                    sz = os.path.getsize(seg_path)
                    downloaded_bytes += sz
                    downloaded_count += 1
                    return
                
                async with sem:
                    for attempt in range(5):
                        try:
                            if attempt == 0:
                                res = await session.get(seg_url, headers=headers, impersonate=working_imp, timeout=15)
                            else:
                                # Usar una sesión fresca exclusiva para este segmento en reintentos para evadir Broken Pipe / Connection Reset
                                async with AsyncSession() as local_session:
                                    res = await local_session.get(seg_url, headers=headers, impersonate=working_imp, timeout=15)
                            if res.status_code == 200:
                                async with aiofiles.open(seg_path, "wb") as f_seg:
                                    await f_seg.write(res.content)
                                downloaded_bytes += len(res.content)
                                downloaded_count += 1
                                
                                # Progress updates
                                now_t = time.time()
                                if (now_t - last_edit) > 4:
                                    elapsed = now_t - last_speed_time
                                    bytes_diff = downloaded_bytes - last_bytes
                                    speed_bps = bytes_diff / elapsed if elapsed > 0 else 0
                                    
                                    if speed_bps > 1024 * 1024:
                                        speed_str = f"{speed_bps / (1024 * 1024):.2f} MB/s"
                                    elif speed_bps > 1024:
                                        speed_str = f"{speed_bps / 1024:.2f} KB/s"
                                    else:
                                        speed_str = f"{speed_bps:.2f} B/s"
                                        
                                    last_bytes = downloaded_bytes
                                    last_speed_time = now_t
                                    last_edit = now_t
                                    
                                    perc = (downloaded_count / total_segments) * 100
                                    perc_str = f"{perc:.1f}%"
                                    
                                    downloaded_mb = downloaded_bytes / (1024 * 1024)
                                    if downloaded_count > 0:
                                        estimated_total_bytes = (downloaded_bytes / downloaded_count) * total_segments
                                    else:
                                        estimated_total_bytes = 0
                                    estimated_total_mb = estimated_total_bytes / (1024 * 1024)
                                    
                                    txt = f"⬇️ Descargando 📁 `{downloaded_mb:.1f}/{estimated_total_mb:.1f} MB` (`{perc_str}`) a `{speed_str}`"
                                    if status:
                                        try: await status.edit(txt)
                                        except: pass
                                    try:
                                        update_progress(chat_id, status.id, percent=perc, speed=speed_str, status="Descargando 📁", name=datos.get('titulo','Video'), url=url_descarga)
                                    except: pass
                                return
                            else:
                                print(f"[Surrit Turbo] [{idx}] HTTP {res.status_code} (attempt {attempt+1}/5)")
                        except Exception as e:
                            print(f"[Surrit Turbo] [{idx}] Error (attempt {attempt+1}/5): {e}")
                        await asyncio.sleep(1)
                    
                    failed_segments.append(idx)
            
            tasks = [download_segment(i, url) for i, url in enumerate(segments)]
            await asyncio.gather(*tasks)
            
            if failed_segments:
                print(f"[Surrit Turbo] Retrying {len(failed_segments)} failed segments...")
                retry_tasks = [download_segment(idx, segments[idx]) for idx in failed_segments]
                failed_segments.clear()
                await asyncio.gather(*retry_tasks)
                
            if failed_segments:
                print(f"[Surrit Turbo] Failed to download {len(failed_segments)} segments.")
                if status:
                    try: await status.edit("❌ Error: Algunos segmentos fallaron al descargar.")
                    except: pass
                return None
                
            # Merge
            if status:
                try: await status.edit("🔄 [Surrit Turbo] Uniendo partes del video...")
                except: pass
                
            final_path = os.path.join(DOWNLOAD_DIR, f"{pure_name}.ts")
            with open(final_path, "wb") as f_out:
                for idx in range(total_segments):
                    seg_path = os.path.join(temp_dir, f"{idx}.ts")
                    with open(seg_path, "rb") as f_in:
                        f_out.write(f_in.read())
                        
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"[Surrit Turbo] Merged and cleaned up: {final_path}")
            return final_path
            
    except asyncio.CancelledError:
        print("[Surrit Turbo] Canceled. Cleaning up...")
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as e:
        print(f"[Surrit Turbo] Exception: {e}")
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        if status:
            try: await status.edit(f"❌ Error en descarga: {str(e)[:100]}")
            except: pass
        return None

async def enviar_portada_missav(client, chat_id, datos, msg_orig):
    source_url = datos.get('url', '')
    if not source_url or "missav" not in source_url.lower():
        return None
        
    url_clean = source_url.split('?')[0].split('#')[0].rstrip('/')
    search_code = url_clean.split('/')[-1].replace('-uncensored-leak', '').upper()
    is_uncensored = "uncensored" in url_clean.lower()
    
    censura_text = "(sin censura)" if is_uncensored else "(con censura)"
    cover_caption = f"{search_code} {censura_text}"
    
    temp_dir = "downloads"
    if not os.path.exists(temp_dir):
        try: os.makedirs(temp_dir)
        except: pass
        
    filename = f"cover_{chat_id}_{int(time.time())}_{random.randint(1000, 9999)}.jpg"
    filepath = os.path.join(temp_dir, filename)
    
    cover_url = datos.get('cover_url')
    success = False
    if cover_url:
        print(f"[*] Descargando portada directa: {cover_url}")
        success = download_image_direct(cover_url, filepath)
        
    if not success:
        print(f"[*] Descarga directa falló o no disponible. Buscando miniatura para {search_code}")
        thumb_status, thumb_name, _ = download_missav_thumbnail(search_code, is_uncensored, temp_dir)
        if thumb_status == 'success':
            filepath = os.path.join(temp_dir, thumb_name)
            success = True
            
    if success and os.path.exists(filepath):
        try:
            from pyrogram import enums
            from utils_chat_actions import chat_action_loop
            async with chat_action_loop(client, chat_id, enums.ChatAction.UPLOAD_PHOTO):
                sent_msg = await client.send_photo(chat_id, filepath, caption=cover_caption, reply_to_message_id=msg_orig.id)
                print(f"[+] Portada enviada exitosamente para {search_code}")
                try: os.remove(filepath)
                except: pass
                return sent_msg
        except Exception as e:
            print(f"[-] Error enviando portada MissAV: {e}")
            try: os.remove(filepath)
            except: pass
    else:
        print(f"[-] No se pudo descargar la portada para {search_code}")
    return None

def generate_caption(d_datos, d_conf, extra_tag=None):
    """
    Genera el caption estandarizado. 
    Maneja un formato exclusivo limpio para MissAV y el normal para todo lo demás.
    """
    MAX_CAPTION_LEN = 1024
    
    t = d_datos.get('titulo', 'Video')
    source_url = d_datos.get('url', '')
    
    # --- LÓGICA EXCLUSIVA PARA MISSAV ---
    if source_url and "missav" in source_url.lower():
        url_clean = source_url.split('?')[0].split('#')[0].rstrip('/')
        code = url_clean.split('/')[-1].replace('-uncensored-leak', '').upper()
        censura_str = "(sin censura)" if "uncensored" in url_clean.lower() else "(con censura)"
        
        # Clean code from start of title
        clean_title = t
        if clean_title.upper().startswith(code):
            clean_title = clean_title[len(code):].strip()
        # Remove any leading dashes/spaces/colons/brackets
        clean_title = re.sub(r'^[\s\-_:.]+', '', clean_title)
        
        part_str = ""
        if extra_tag:
            match = re.search(r'\[\d+/\d+\]', extra_tag)
            if match:
                part_str = f" {match.group(0)}"
        
        header = f"{code} {censura_str}{part_str}\n{clean_title}"
        
        cache_hit = ""
        if extra_tag:
            vid_id_match = re.search(r'`([^`]+)`', extra_tag)
            if "Cache Hit" in extra_tag or "Memoria" in extra_tag:
                if vid_id_match:
                    cache_hit = f"\n\n✨ _Cache Hit_ `{vid_id_match.group(1)}`"
                else:
                    cache_hit = f"\n\n✨ _Cache Hit_"
        
        final_cap = f"{header}{cache_hit}"
        if len(final_cap) > MAX_CAPTION_LEN:
            final_cap = final_cap[:MAX_CAPTION_LEN-3] + "..."
        return final_cap
        
    # --- LÓGICA EXCLUSIVA PARA HENTAILA ---
    elif source_url and "hentaila" in source_url.lower():
        header = f"{t}"
        
        cache_hit = ""
        if extra_tag:
            match = re.search(r'\[\d+/\d+\]', extra_tag)
            if match:
                header += f" {match.group(0)}"
            
            vid_id_match = re.search(r'`([^`]+)`', extra_tag)
            if "Cache Hit" in extra_tag or "Memoria" in extra_tag:
                if vid_id_match:
                    cache_hit = f"\n\n✨ _Cache Hit_ `{vid_id_match.group(1)}`"
                else:
                    cache_hit = f"\n\n✨ _Cache Hit_"
        
        footer = cache_hit
        final_cap = f"{header}{footer}"
        
        if len(final_cap) > MAX_CAPTION_LEN:
            final_cap = final_cap[:MAX_CAPTION_LEN-3] + "..."
        return final_cap

    # --- LÓGICA NORMAL (Otras Páginas) ---
    uploader = d_datos.get('uploader')
    uploader_url = d_datos.get('uploader_url')
    
    header = f"**{t}**"
    if uploader and uploader_url:
        header += f"\n[{uploader}]({uploader_url})"
    elif uploader:
        header += f"\n{uploader}"

    if extra_tag:
        header += f" {extra_tag}"
        
    footer = ""
    
    tags = d_datos.get('hashtags')
    if tags and d_conf.get('meta', True):
        footer += f"\n\n{tags}"
        
    w = d_datos.get('width')
    h = d_datos.get('height')
    if w and h:
         footer += f"\n\nDimensiones: {w} x {h}"
         
    if source_url:
         # Si es XVideos y guardamos la URL web original, mostrar ambas
         xv_orig = d_datos.get('xvideos_original_url')
         if xv_orig:
             footer += f"\n\n🔗 {xv_orig}\n📺 M3U8: {source_url}"
         else:
             footer += f"\n\n🔗 {source_url}"
         
    current_len = len(header) + len(footer)
    remaining = MAX_CAPTION_LEN - current_len - 10
    
    body = ""
    if d_conf.get('meta', True):
        desc = d_datos.get('descripcion')
        if desc:
            if len(desc) <= remaining:
                body = f"\n\n{desc}"
            else:
                if remaining > 20:
                    cut_desc = desc[:remaining-3] + "..."
                    body = f"\n\n{cut_desc}"

    final_cap = f"{header}{body}{footer}"
    
    if len(final_cap) > MAX_CAPTION_LEN:
        final_cap = final_cap[:MAX_CAPTION_LEN-3] + "..."
        
    return final_cap

async def procesar_descarga(client, chat_id, url, calidad, datos, msg_orig, context_config=None, return_paths=False):
    from main import get_config, url_storage, DATA_DIR
    from utils import download_parallel
    from tools_media import get_meta, get_thumb, progreso
    
    # --- CONTEXT CONFIG (Frozen) ---
    # Si viene con configuración congelada, la usamos. Si no, cargamos dynamic (legacy behavior)
    if context_config:
        conf = context_config
    else:
        conf = get_config(chat_id)
        
    cover_msg = None
    # Enviar portada de JAV si aplica antes de cualquier otra cosa (incluso cache hit)
    if url and "missav" in url.lower():
        try:
            cover_msg = await enviar_portada_missav(client, chat_id, datos, msg_orig)
        except Exception as e_cover:
            print(f"⚠️ Error enviando portada al inicio: {e_cover}")
        
    vid_id = datos.get('id')
    
    vid_id = datos.get('id')
    
    final = None
    multi_files = [] # For Slideshows
    thumb = None

    # Identificador único (Timestamp ns + Random 4 digits) para max individualidad
    ts = f"{time.time_ns()}_{random.randint(1000, 9999)}"
    
    # Crear directorio de trabajo aislado para evitar colisiones de archivos y artifacts
    # Structure: downloads/url_downloads/job_{id}_{ts}/
    tool_folder = os.path.join(DOWNLOAD_DIR, "url_downloads")
    if not os.path.exists(tool_folder): os.makedirs(tool_folder)

    job_dir = os.path.join(tool_folder, f"job_{chat_id}_{ts}")
    job_dir_to_clean = job_dir
    if not os.path.exists(job_dir):
        try: os.makedirs(job_dir)
        except: pass

    # Usar directorio de descargas aislado
    base_name = os.path.join(job_dir, f"dl_{chat_id}_{ts}")
    # Limpiamos base_name de posibles caracteres raros por si acaso (aunque es solo ID_TS)

    url_descarga = url
    ckey = calidad
    
    # Si viene del Sniffer/JAV Extractor
    if calidad.startswith("html_"):
        idx = int(calidad.split("_")[1])
        if 'html_links_data' in datos and len(datos['html_links_data']) > idx:
            # Check if it is Eporner and needs refreshing to avoid token expiration
            orig_url = datos.get('url', '')
            if "eporner.com" in orig_url and "/video-" in orig_url:
                print(f"🔄 [Eporner] Refreshing download links dynamically for: {orig_url}")
                try:
                    fresh_title, fresh_links = await get_eporner_links(orig_url)
                    if fresh_links:
                        datos['html_links_data'] = fresh_links
                        print("✅ [Eporner] Links refreshed successfully!")
                except Exception as e_ref:
                    print(f"⚠️ [Eporner] Failed to refresh links: {e_ref}")
            
            url_descarga = datos['html_links_data'][idx]['url']
            ckey = f"html_{idx}" 
        else:
            await client.send_message(chat_id, "❌ **Enlace expirado (Datos perdidos).**\nPor favor, reenvía el enlace y prueba de nuevo.")
            return
    else:
        ckey = "mp3" if calidad == "mp3" else calidad

    # FIX: Diferenciar cache si es modo documento (Usando conf congelada o fresca)
    is_doc_mode = conf.get('doc_mode', False)
    if is_doc_mode and calidad != "mp3":
        ckey += "_doc"

    # --- ZONA DE CACHE (FIREBASE STRICT) ---
    cached_fid = None
    if vid_id:
        # Use URL + Quality + DocMode strict check
        print(f"🔍 [Downloader Debug] Checking Strict Cache: ID={vid_id} | URL={url_descarga} | Q={ckey} | Doc={is_doc_mode}")
        cached_fid = await get_cached_file_strict(vid_id, url_descarga, ckey, is_doc_mode)

    # Determinar qué semáforo usar según la fuente (Surrit/MissAV es pesado, limite de 1)
    is_surrit = "surrit" in url.lower() or "missav" in url.lower()
    max_dl = conf.get('max_downloads', 'default')
    active_semaphore = get_user_semaphore(chat_id, is_surrit, max_dl)

    # --- SEMAPHORE CHECK & FEEDBACK ---
    if active_semaphore.locked():
        # Si el semáforo está rojo (ocupado), avisar que entra en cola
        if msg_orig and conf.get('preview_mode', True):
            try:
                # Count waiters approx
                n = len(getattr(active_semaphore, '_waiters', [])) + 1
                s = "s" if n != 1 else ""
                tipo_cola = "Surrit" if is_surrit else "descarga"
                q_msg = await client.send_message(chat_id, f"⬇️ En cola: {n} {tipo_cola}{s} 📁...", reply_to_message_id=msg_orig.id)
            except: pass
    
    async with active_semaphore:
        if 'q_msg' in locals() and q_msg:
            try: await q_msg.delete()
            except: pass

        # Validar si el mensaje original fue borrado (cancelación manual usuario)
        # ... (Resto del código)
    # Removed generate_caption from here because it was moved to module level.

    if cached_fid:
        try:
            print(f"✨ Firebase Cache Hit: {vid_id} [{ckey}]")
            
            # --- SUPPORT FOR SPLIT CACHE (List of IDs) ---
            file_ids_to_send = []
            if isinstance(cached_fid, list):
                file_ids_to_send = cached_fid
            else:
                file_ids_to_send = [cached_fid]
                
            total_parts_cache = len(file_ids_to_send)
            
            uploaded_cache_msgs = []
            
            for idx, f_id in enumerate(file_ids_to_send):
                part_tag = f"[{idx+1}/{total_parts_cache}]" if total_parts_cache > 1 else ""
                
                # Generar Caption Consistente
                cache_tag = f"\n✨ _Cache Hit_{part_tag} `{vid_id}`"
                if conf.get('lang') == 'es': cache_tag = f"\n✨ _Desde Memoria_{part_tag} `{vid_id}`"
                
                final_caption = generate_caption(datos, conf, extra_tag=cache_tag)
                
                # SEND CACHED DIRECTLY (No Semaphore needed)
                try:
                    if is_doc_mode:
                        async with chat_action_loop(client, chat_id, enums.ChatAction.UPLOAD_DOCUMENT):
                            sent = await client.send_document(chat_id, f_id, caption=final_caption, reply_to_message_id=msg_orig.id)
                            uploaded_cache_msgs.append(sent)
                    else:
                         async with chat_action_loop(client, chat_id, enums.ChatAction.UPLOAD_VIDEO):
                             sent = await client.send_video(chat_id, f_id, caption=final_caption, reply_to_message_id=msg_orig.id)
                             uploaded_cache_msgs.append(sent)
                except Exception as e_part:
                    print(f"❌ Error sending cached part {idx}: {e_part}")
            final_messages = []
            if cover_msg:
                final_messages.append(cover_msg)
            final_messages.extend(uploaded_cache_msgs)
            return final_messages
        except Exception as e:
            print(f"Cache Send Error: {e}")
            cached_fid = None

    # NO CACHE - PROCEED TO DOWNLOAD
    status = None
    # NO CACHE - PROCEED TO DOWNLOAD
    status = None
    # Removed "Esperando turno" message per user request (Empty start)
    if conf.get('preview_mode', True):
        # Placeholder startup message
        status = await client.send_message(chat_id, "⬇️ Descargando 📁...", reply_to_message_id=msg_orig.id)
    
    # SEMAPHORE LIMIT
    # Register Task for Anti-Spam / Cancellation
    curr_task = asyncio.current_task()
    task_key = f"{msg_orig.id}_{ts}" if msg_orig else ts
    add_active(chat_id, task_key, curr_task)

    try:
        # Variables de control de progreso
        last_edit = 0
        start_time = time.time()
        loop = client.loop
        
        # --- DOWNLOAD BLOCK (SEMAPHORED) ---
        async with active_semaphore:
            # Removed "Iniciando descarga..." edit
            
            def progress_hook(d):
                nonlocal last_edit
                nonlocal status
                now = time.time()
                
                # Filtro Anti-Flood (Editar cada 4 segundos máx o al finalizar)
                if d['status'] == 'finished' or (now - last_edit) > 4:
                    last_edit = now
                    
                    # Extraer datos de YT-DLP / Fast
                    percent = d.get('_percent_str', '0%').strip()
                    # Limpiar caracteres ANSI si Fast los mete
                    percent = re.sub(r'\x1b\[[0-9;]*m', '', percent)
                    
                    speed = d.get('_speed_str', 'N/A').strip()
                    eta = d.get('_eta_str', 'N/A').strip()
                    
                    # Fallback simple si no hay speed string
                    if speed == 'N/A' and d.get('speed'):
                        speed = format_bytes(d.get('speed')) + "/s"
                        
                    try:
                        from utils import render_bar
                        
                        # Safe parse percent
                        try: p_val = float(percent.replace('%','')) 
                        except: p_val = 0
                        
                        # Parse bytes to get total estimation if needed, or just bar 0-100
                        # For yt-dlp, let's trust percent
                        bar = render_bar(p_val, 100)
                        
                        # Calculate MB (Safe)
                        cur_bytes = d.get('downloaded_bytes') or 0
                        tot_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                        
                        try: c_mb = float(cur_bytes) / (1024*1024)
                        except: c_mb = 0
                        
                        try: t_mb = float(tot_bytes) / (1024*1024)
                        except: t_mb = 0
                        
                        msg_text = f"⬇️ Descargando 📁 `{c_mb:.1f}/{t_mb:.1f} MB` (`{percent}`)"
                        
                        # FIX: Use call_soon_threadsafe to schedule create_task (Fire-and-forget)
                        # This avoids 'Future attached to different loop' errors with run_coroutine_threadsafe
                        if status:
                            loop.call_soon_threadsafe(lambda: loop.create_task(status.edit(msg_text)))
                        
                        # Stats update safe
                        try: update_progress(chat_id, task_key, percent=p_val, speed=speed, status="Descargando 📥", name=datos.get('titulo','Video'), url=url_descarga)
                        except: pass
                        
                    except Exception as e:
                        print(f"⚠️ Progress Hook Error: {e}")

            if conf.get('preview_mode', True) and not status:
                status = await client.send_message(chat_id, f"⬇️ Descargando 📁...", reply_to_message_id=msg_orig.id)
            print(f"🚀 Iniciando proceso de descarga: {url_descarga}")
            
            # --- LOGICA DE SELECCIÓN DE MOTOR ---
            use_ytdlp_fallback = False
            engine_name = "Nativo (Estándar)"
            is_direct_download = False
            mediafire_link = None
            yourupload_link = None
            mp4_link = None
            fireload_cookie = None
            
            # 0. HentaiLA Check
            if "hentaila.com" in url_descarga:
                if status: await status.edit("🔍 **Buscando servidores en HentaiLA...**")
                hl_servers, hl_title = await get_hentaila_link(url_descarga)
                if hl_servers:
                    if hl_title:
                        datos['titulo'] = hl_title  # Sobrescribimos el título para que salga limpio en el bot
                    
                    found_link = None
                    
                    # 1. Intentar MediaFire
                    mf_base = hl_servers.get('MEDIAFIRE')
                    if mf_base:
                        mf_link = await get_mediafire_link(mf_base)
                        if mf_link:
                            found_link = mf_link
                            engine_name = "Mediafire (Directo)"
                            mediafire_link = True
                            print(f"🔗 HentaiLA usará MediaFire: {found_link}")
                            
                    # 2. Si MediaFire no está o falló, intentar MP4Upload
                    if not found_link:
                        mp4_base = hl_servers.get('MP4UPLOAD')
                        if mp4_base:
                            mp4_link = await get_mp4upload_link(mp4_base)
                            if mp4_link:
                                found_link = mp4_link
                                engine_name = "MP4Upload (Directo)"
                                print(f"🔗 HentaiLA usará MP4Upload: {found_link}")
                                
                    # 3. Si ambos fallan, intentar FireLoad
                    if not found_link:
                        fl_base = hl_servers.get('FIRELOAD')
                        if fl_base:
                            fl_link, fl_cookie = await get_fireload_link(fl_base)
                            if fl_link:
                                found_link = fl_link
                                fireload_cookie = fl_cookie
                                engine_name = "FireLoad (Directo)"
                                print(f"🔗 HentaiLA usará FireLoad: {found_link}")
                                
                    if found_link:
                        url_descarga = found_link
                        is_direct_download = True
                    else:
                        if status: await status.edit("❌ **Error:** HentaiLA no tiene MediaFire, MP4Upload ni FireLoad disponibles, o están caídos.")
                        return
                else:
                    if status: await status.edit("❌ **Error:** No se pudieron extraer servidores de HentaiLA.")
                    return
                    
            # 0.5 Fireload Check
            elif "fireload.com" in url_descarga:
                fl_link, fl_cookie = await get_fireload_link(url_descarga)
                if fl_link:
                    url_descarga = fl_link
                    fireload_cookie = fl_cookie
                    engine_name = "FireLoad (Directo)"
                    is_direct_download = True
                    print(f"🔗 FireLoad Link Directo: {url_descarga}")
                else:
                    if status: await status.edit("❌ **Error: FireLoad falló.**\nNo pude sacar el link directo.")
                    return 

            # 1. Mediafire Check
            elif "mediafire.com" in url_descarga:
                # Removed Check msg
                mf_link = await get_mediafire_link(url_descarga)
                if mf_link:
                    url_descarga = mf_link
                    engine_name = "Mediafire (Directo)"
                    is_direct_download = True
                    mediafire_link = True
                    print(f"🔗 MediaFire Link Directo: {url_descarga}")
                else:
                    if status: await status.edit("❌ **Error: Mediafire cambió.**\nNo pude sacar el link directo.")
                    return 

            # 2. YourUpload Check
            elif "yourupload.com" in url_descarga:
                # Removed Check msg
                yu_link = await get_yourupload_link(url_descarga)
                if yu_link:
                    url_descarga = yu_link
                    engine_name = "YourUpload (Directo)"
                    is_direct_download = True
                    yourupload_link = True
                else:
                    pass

            # 2a. XHamster Check (M3U8)
            elif "xhamster.com" in url_descarga:
                xh_link, xh_title = await get_xhamster_link(url_descarga)
                if xh_link:
                    url_descarga = xh_link
                    engine_name = "XHamster (M3U8)"
                    if xh_title:
                        datos['titulo'] = xh_title
                    # No ponemos is_direct_download = True porque M3U8 usa Turbo, y Turbo se activa con ".m3u8" in url_descarga
                else:
                    pass

            # 2a2. XVideos Check (M3U8)
            elif any(domain in url_descarga for domain in ["xvideos.com", "xvideos.es", "xvideos.red"]) and ".m3u8" not in url_descarga:
                xv_link, xv_title = await get_xvideos_link(url_descarga)
                if xv_link:
                    datos['xvideos_original_url'] = url_descarga
                    url_descarga = xv_link
                    engine_name = "XVideos (M3U8)"
                    if xv_title:
                        datos['titulo'] = xv_title
                else:
                    pass

            # 2a3. Pornhub Check (M3U8)
            elif any(domain in url_descarga for domain in ["pornhub.com", "pornhub.org", "pornhubpremium.com"]) and ".m3u8" not in url_descarga:
                ph_link, ph_title = await get_pornhub_link(url_descarga, calidad)
                if ph_link:
                    datos['pornhub_original_url'] = url_descarga
                    url_descarga = ph_link
                    engine_name = "Pornhub (M3U8)"
                    if ph_title:
                        datos['titulo'] = ph_title
                else:
                    pass

            # 2b. MP4Upload Check
            elif "mp4upload.com" in url_descarga:
                # Removed Check msg
                mp4_link = await get_mp4upload_link(url_descarga)
                if mp4_link:
                    url_descarga = mp4_link
                    engine_name = "MP4Upload (Directo)"
                    is_direct_download = True
                else:
                    if status: await status.edit("❌ **Error: MP4Upload falló.**\nNo pude sacar el video.")
                    return

            # 2c. Eporner Direct Check
            elif "eporner.com" in url_descarga and "/dload/" in url_descarga:
                # Limpiar URL (es.eporner -> www.eporner para evitar problemas de certificado/redirección)
                url_descarga = re.sub(r'https?://\w+\.eporner\.com', 'https://www.eporner.com', url_descarga)
                engine_name = "Eporner (Directo)"
                is_direct_download = True

            # 3. Turbo Check (Priority for m3u8 if tool exists)
            # Removed Owner Restriction per user request
            
            usar_turbo = (HAS_RE or "surrit.com" in url_descarga) and ".m3u8" in url_descarga and calidad != "mp3" and not mediafire_link and not yourupload_link

            if usar_turbo: 
                if "surrit.com" in url_descarga:
                    engine_name = "Turbo (Surrit Custom)"
                else:
                    engine_name = "Turbo (N_m3u8DL-RE)"
            elif is_direct_download or (HAS_FAST and not calidad.startswith("html_") and conf.get('fast_enabled', True) and "eporner" not in url_descarga):
                if not is_direct_download: 
                    engine_name = "Fast (Ultra)"

            # Removed "Descargando ... (Iniciando) 0%" msg

            if usar_turbo:
                # Es mucho más rápido que yt-dlp para unir segmentos
                pure_name = f"dl_{chat_id}_{ts}"
                if "surrit.com" in url_descarga:
                    final = await download_surrit_custom(url_descarga, pure_name, chat_id, status, datos, task_key)
                    if not final:
                        use_ytdlp_fallback = True
                else:
                    cmd = [
                        RE_PATH,
                        url_descarga,
                        "--save-name", pure_name,
                        "--save-dir", DOWNLOAD_DIR,      # Guardar en DOWNLOAD_DIR explicitamente
                        "--tmp-dir", "tmp",      # Temporales
                        "--no-log",              # No llenar la consola
                        "--auto-select",         # Elegir mejor video/audio auto
                        "--check-segments-count", "false", # No verificar cada segmento (Más velocidad)
                        "--thread-count", "16",  # 16 Hilos de descarga
                        "--download-retry-count", "10" # Reintentar si falla un trozo
                    ]
                    
                    if "xhcdn.com" in url_descarga or "xhamster.com" in url_descarga:
                        cmd.extend(["-H", "Referer: https://es.xhamster.com/"])
                        cmd.extend(["-H", f"User-Agent: {get_random_user_agent()}"])
                    
                    max_turbo_retries = 10 if ("missav" in url_descarga.lower() or "surrit.com" in url_descarga.lower()) else 1
                    
                    for attempt in range(max_turbo_retries):
                        if attempt > 0 and status:
                            try: await status.edit(f"🔄 Reintentando Turbo (Intento {attempt+1}/{max_turbo_retries})...")
                            except: pass
                            await asyncio.sleep(3) # Pausa entre reintentos para no bombardear el servidor
                            
                        # Ejecutamos el proceso CON PIPE para leer salida
                        process = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                        
                        # Registrar PID para Cancelar
                        add_active(chat_id, task_key, None, process.pid)
                        
                        # Loop para leer progreso de Turbo
                        while True:
                            line = await process.stdout.readline()
                            if not line: break
                            
                            line_str = line.decode('utf-8', errors='ignore').strip()
                            if line_str: print(f"Turbo: {line_str}") # Feedback en consola
                            
                            if "Progress:" in line_str or "%" in line_str:
                                now_t = time.time()
                                if (now_t - last_edit) > 4:
                                    last_edit = now_t
                                    # Try Standard Turbo Regex
                                    p_match = re.search(r'Progress:\s*([\d\.]+%?)', line_str)
                                    s_match = re.search(r'Speed:\s*([\d\.]+\s*\w+/s)', line_str)
                                    
                                    # Try Alternative Regex (Vid ... 71.24% ... 42.02MBps)
                                    if not p_match:
                                        p_match = re.search(r'(\d+(?:\.\d+)?%)', line_str)
                                    if not s_match:
                                        s_match = re.search(r'(\d+(?:\.\d+)?[KMGT]?Bps)', line_str)
                                    
                                    perc = p_match.group(1) if p_match else "..."
                                    spd = s_match.group(1) if s_match else "..."
                                    
                                    try:
                                        from utils import render_bar
                                        try: p_val = float(perc.replace('%',''))
                                        except: p_val = 0
                                        
                                        # Fake Totals for Turbo (It streams, hard to know total MB exactly unless parsed)
                                        # We can parse "1.04GB/1.51GB" in the string if present
                                        size_match = re.search(r'([\d\.]+[KMGT]?B)/([\d\.]+[KMGT]?B)', line_str)
                                        sz_curr = size_match.group(1) if size_match else "?"
                                        sz_tot = size_match.group(2) if size_match else "?"
                                        
                                        if status:
                                            # Formato Estandarizado: ⬇️ Descargando 📁 1.04GB/1.51GB (71.24%)
                                            # Si no hay size: ⬇️ Descargando 📁 (Turbo) (71.24%)
                                            if sz_curr != "?":
                                                txt = f"⬇️ Descargando 📁 `{sz_curr}/{sz_tot}` (`{perc}`)"
                                            else:
                                                txt = f"⬇️ Descargando 📁 (Turbo) `{perc}`" # Fallback
                                                
                                            await status.edit(txt)
                                        
                                        update_progress(chat_id, status.id, percent=p_val, speed=spd, status="Descargando 📁", name=datos.get('titulo','Video'), url=url_descarga)
                                    except: pass
                        
                        await process.wait()
                        
                        # Buscamos qué archivo creó (puede ser mp4 o mkv)
                        # Fix: Usar pure_name con DOWNLOAD_DIR que es lo que se le pasó al comando
                        check_base = os.path.join(DOWNLOAD_DIR, pure_name)
                        for ext in ['.mp4', '.mkv', '.ts']:
                            if os.path.exists(f"{check_base}{ext}"):
                                final = f"{check_base}{ext}"
                                break
                                
                        if final:
                            break # Salir del loop si la descarga fue exitosa
                        else:
                            print(f"⚠️ Turbo Falló (Intento {attempt+1}/{max_turbo_retries})")
                            
                    if not final:
                        use_ytdlp_fallback = True
            
            # --- M3U8 DIRECT FALLBACK TO YT-DLP ---
            # If it's a streaming playlist (.m3u8) but Turbo is disabled/unsupported (e.g. no N_m3u8DL-RE),
            # we must use yt-dlp to download it instead of downloading it as a raw file via aiohttp/aria2c.
            if not final and not use_ytdlp_fallback and ".m3u8" in url_descarga and not usar_turbo:
                use_ytdlp_fallback = True
            
                # --- MODO DIRECTO (FAST/MEDIAFIRE PURO) ---
            if not final and not use_ytdlp_fallback and (is_direct_download or str(vid_id).startswith("direct_")):
                
                # Usar chat_id + ID del video para permitir reanudar (resume) sin colisiones entre usuarios
                safe_vid_id = re.sub(r'[^a-zA-Z0-9_\-]', '', str(vid_id)) if vid_id else f"task_{ts}"
                temp_out = f"dl_{chat_id}_{safe_vid_id}_temp"
                final_temp = os.path.join(DOWNLOAD_DIR, temp_out)
                
                # FALLBACK: Si no hay aria2c o si es Eporner directamente, usar aiohttp (Python nativo)
                if (not HAS_FAST and not shutil.which("aria2c")) or "eporner.com" in url_descarga:
                    # Native fallback
                    try:
                        from utils import load_cookies_dict
                        cookies = load_cookies_dict(sel_cookie(url_descarga))
                        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36" if any(x in url_descarga for x in ["xhand.net", "xhamster.com", "xhcdn.com"]) else get_random_user_agent()
                        headers_fallback = {'User-Agent': ua}
                        if "fireload.com" in url_descarga:
                            headers_fallback['Referer'] = url
                        if "mp4upload.com" in url_descarga:
                            headers_fallback['Referer'] = "https://www.mp4upload.com/"
                        if "xhand.net" in url_descarga or "xhamster.com" in url_descarga or "xhcdn.com" in url_descarga:
                            headers_fallback['Referer'] = url
                        if fireload_cookie:
                            headers_fallback['Cookie'] = fireload_cookie
                        timeout_config = aiohttp.ClientTimeout(total=None, connect=60, sock_read=60)
                        async with aiohttp.ClientSession(cookies=cookies, headers=headers_fallback, timeout=timeout_config) as session:
                            max_retries = 3
                            fallback_success = False
                            last_exception = None
                            
                            for attempt in range(max_retries):
                                try:
                                    if attempt > 0:
                                        if status: await status.edit(f"🔄 Reintentando Nativo ({attempt+1}/{max_retries})...")
                                        await asyncio.sleep(2)
                                        
                                    async with session.get(url_descarga) as resp:
                                        if resp.status == 200:
                                            total_size = int(resp.headers.get('Content-Length', 0))
                                            downloaded = 0
                                            start_t = time.time()
                                            last_edit_t = 0
                                            
                                            with open(final_temp, 'wb') as f:
                                                while True:
                                                    chunk = await resp.content.read(1024*1024) # 1MB chunks
                                                    if not chunk: break
                                                    f.write(chunk)
                                                    downloaded += len(chunk)
                                                    
                                                    # Status update
                                                    now_t = time.time()
                                                    if now_t - last_edit_t > 4:
                                                        last_edit_t = now_t
                                                        from utils import render_bar
                                                        p_f = downloaded/total_size*100 if total_size else 0
                                                        pct = f"{int(p_f)}%" if total_size else "..."
                                                        bar = render_bar(downloaded, total_size) if total_size else "░░" * 10
                                                        mb_curr = downloaded / (1024*1024)
                                                        mb_total = total_size / (1024*1024) if total_size else 0
                                                        speed = mb_curr / (now_t - start_t) if (now_t - start_t) > 0 else 0
                                                        print(f"⬇️ Nativo Progreso: {mb_curr:.1f}/{mb_total:.1f} MB ({pct}) @ {speed:.1f} MB/s")
                                                        if status: await status.edit(f"⬇️ Descargando 📁 `{mb_curr:.1f}/{mb_total:.1f} MB` (`{pct}`)")
                                                        update_progress(chat_id, status.id if status else 0, percent=p_f, speed=f"{speed:.1f}MB/s", status="Descargando 📁", name=datos.get('titulo','Video'), url=url_descarga)
                                                        
                                            final = final_temp
                                            fallback_success = True
                                            break
                                        else:
                                            if status: await status.edit(f"⚠️ Error descarga: {resp.status}. Intentando YT-DLP...")
                                            break
                                except Exception as e_inner:
                                    last_exception = e_inner
                                    print(f"Native DL attempt {attempt+1} failed: {e_inner}")
                            
                            if not fallback_success:
                                use_ytdlp_fallback = True
                    except Exception as e:
                        print(f"Native DL Error: {e}")
                        use_ytdlp_fallback = True

                else:
                    # ARIA2 BLOCK (Solo si existe)
                    cmd = [
                        FAST_PATH if os.path.exists(FAST_PATH) else "aria"+"2c", 
                        url_descarga,
                        "-o", temp_out, 
                        "-d", DOWNLOAD_DIR,
                        "-c", # REANUDAR (Resume) activado
                        "-x", "16", "-s", "16", "-j", "1", "-k", "1M",
                        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36" if any(x in url_descarga for x in ["xhand.net", "xhamster.com", "xhcdn.com"]) else get_random_user_agent(),
                        "--check-certificate=false",
                        "--allow-overwrite=false", # Cambiado a false para permitir resume del mismo archivo
                        "--auto-file-renaming=false",
                        "--timeout=120", "--connect-timeout=60",
                        "--max-tries=10", "--retry-wait=5",
                        "--summary-interval=1",
                        "--file-allocation=none"
                    ]
                    
                    if yourupload_link:
                        cmd.extend(["--header", f"Referer: {url}"])
                    elif "erome.com" in url_descarga:
                        cmd.extend(["--header", f"Referer: https://www.erome.com/"])
                    elif "fireload.com" in url_descarga:
                        cmd.extend(["--header", f"Referer: {url}"])
                    elif "mp4upload.com" in url_descarga:
                        cmd.extend(["--header", f"Referer: https://www.mp4upload.com/"])
                    elif "xhand.net" in url_descarga or "xhamster.com" in url_descarga or "xhcdn.com" in url_descarga:
                        cmd.extend(["--header", f"Referer: {url}"])
                        
                    if fireload_cookie:
                        cmd.extend(["--header", f"Cookie: {fireload_cookie}"])
                    
                    cookie_file = sel_cookie(url_descarga)
                    if cookie_file:
                        cmd.extend(["--load-cookies", cookie_file])

                    aria_max_attempts = 3
                    aria_success = False
                    
                    for aria_attempt in range(aria_max_attempts):
                        if aria_attempt > 0:
                            if status: await status.edit(f"🔄 Reintentando Aria2 (Intento {aria_attempt+1}/{aria_max_attempts})...")
                            await asyncio.sleep(4)
                        
                        process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        # --- ARIA2 PROGRESS PARSER ---
                        # Format: [#GID 25MiB/100MiB(25%) CN:1 DL:1.2MiB]
                        track = [time.time(), 0]
                        aria_error_log = []
                        
                        async def read_stream(stream, callback):
                            while True:
                                try:
                                    buffer = b""
                                    while True:
                                        char = await stream.read(1)
                                        if not char:
                                            if buffer: await callback(buffer)
                                            return
                                        buffer += char
                                        if char == b'\r' or char == b'\n':
                                            await callback(buffer)
                                            buffer = b""
                                except: break

                        async def handle_stdout(line):
                            try:
                                line_str = line.decode('utf-8', errors='ignore').strip()
                                if not line_str: return
                                
                                # Parse Progress lines
                                if "CN:" in line_str and "DL:" in line_str and "(" in line_str:
                                    parts = line_str.split()
                                    downloaded = "0"
                                    total = "0"
                                    percent = "0%"
                                    
                                    for p in parts:
                                        if "/" in p and "(" in p: 
                                            try:
                                                d_t, per = p.split("(") 
                                                downloaded, total = d_t.split("/")
                                                percent = per.replace(")", "")
                                            except: pass
                                            
                                    # Update UI (Throttle 2s)
                                    now = time.time()
                                    if (now - track[0]) > 2: 
                                        track[0] = now
                                        d_c = downloaded
                                        t_c = total
                                        msg_txt = f"⬇️ Descargando 📁 `{d_c}/{t_c}` (`{percent}`)"
                                        print(f"⬇️ Aria2 Progreso: {d_c}/{t_c} ({percent})")
                                        try: await status.edit(msg_txt)
                                        except: pass
                            except: pass

                        async def handle_stderr(line):
                            line_str = line.decode('utf-8', errors='ignore').strip()
                            if line_str:
                                aria_error_log.append(line_str)
                                print(f"Aria2 Error: {line_str}")

                        # Run readers concurrently
                        await asyncio.gather(
                            read_stream(process.stdout, handle_stdout),
                            read_stream(process.stderr, handle_stderr)
                        )
                        
                        await process.wait()
                        
                        if process.returncode == 0:
                            aria_success = True
                            break
                        else:
                            err_msg = "\n".join(aria_error_log[-3:])
                            print(f"⚠️ Aria2 Intento {aria_attempt+1} fallido (Code {process.returncode}): {err_msg}")
                            
                    if not aria_success:
                        # FALLBACK to Native
                        if status: await status.edit(f"⚠️ Aria2 falló. Iniciando descarga Nativa...")
                        await asyncio.sleep(1) # Give it a second
                        
                        print("🔄 Initiating Native Fallback...")
                        try:
                            from utils import load_cookies_dict
                            cookies = load_cookies_dict(sel_cookie(url_descarga))
                            headers_fallback = {'User-Agent': get_random_user_agent()}
                            if "erome.com" in url_descarga:
                                headers_fallback['Referer'] = 'https://www.erome.com/'
                            elif "xhand.net" in url_descarga or "xhamster.com" in url_descarga or "xhcdn.com" in url_descarga:
                                headers_fallback['Referer'] = url
                            elif "pornhub.com" in url_descarga or "phncdn.com" in url_descarga or "pornhub.com" in url or "phncdn.com" in url:
                                headers_fallback['Referer'] = 'https://es.pornhub.com/'
                            timeout_config = aiohttp.ClientTimeout(total=None, connect=60, sock_read=60)
                            async with aiohttp.ClientSession(cookies=cookies, headers=headers_fallback, timeout=timeout_config) as session:
                                max_retries = 3
                                fallback_success = False
                                last_exception = None
                                
                                for attempt in range(max_retries):
                                    try:
                                        if attempt > 0:
                                            if status: await status.edit(f"🔄 Reintentando Nativo ({attempt+1}/{max_retries})...")
                                            await asyncio.sleep(2)
                                            
                                        async with session.get(url_descarga) as resp:
                                            if resp.status == 200:
                                                total_size = int(resp.headers.get('Content-Length', 0))
                                                downloaded = 0
                                                start_t = time.time()
                                                last_edit_t = 0
                                                
                                                with open(final_temp, 'wb') as f:
                                                    while True:
                                                        chunk = await resp.content.read(1024*1024)
                                                        if not chunk: break
                                                        f.write(chunk)
                                                        downloaded += len(chunk)
                                                        
                                                        now_t = time.time()
                                                        if now_t - last_edit_t > 4:
                                                            last_edit_t = now_t
                                                            from utils import render_bar
                                                            p_f = downloaded/total_size*100 if total_size else 0
                                                            pct = f"{int(p_f)}%" if total_size else "..."
                                                            mb_curr = downloaded / (1024*1024)
                                                            mb_total = total_size / (1024*1024) if total_size else 0
                                                            speed = mb_curr / (now_t - start_t) if (now_t - start_t) > 0 else 0
                                                            print(f"⬇️ Nativo(Fallback) Progreso: {mb_curr:.1f}/{mb_total:.1f} MB ({pct}) @ {speed:.1f} MB/s")
                                                            if status: await status.edit(f"⬇️ Descargando (Nativo) 📁 `{mb_curr:.1f}/{mb_total:.1f} MB` (`{pct}`) @ `{speed:.1f} MB/s`")
                                                            
                                                final = final_temp
                                                fallback_success = True
                                                break
                                            else:
                                                if status: await status.edit(f"⚠️ Fallback Error: {resp.status}. Intentando YT-DLP...")
                                                break
                                    except Exception as e_inner:
                                        last_exception = e_inner
                                        print(f"Fallback attempt {attempt+1} failed: {e_inner}")
                                
                                if not fallback_success:
                                    use_ytdlp_fallback = True
                        except Exception as e_fall:
                             print(f"Fallback Exception: {e_fall}")
                             use_ytdlp_fallback = True
                    else:
                        final = final_temp 
                    # End of Aria2 process

                final_temp = os.path.join(DOWNLOAD_DIR, temp_out)
                if os.path.exists(final_temp):
                    # Deducir extension para que get_meta funcione
                    ext = ".mp4" # Default safe
                    if "." in url_descarga:
                         try:
                             parts = url_descarga.split("/")[-1].split("?")[0].split(".")
                             if len(parts) > 1:
                                 can_ext = "." + parts[-1]
                                 if len(can_ext) < 6: ext = can_ext
                         except: pass

                    final_path_with_ext = final_temp + ext
                    try:
                        os.rename(final_temp, final_path_with_ext)
                        final = final_path_with_ext
                    except Exception as e:
                        print(f"Rename Error: {e}")
                        # Fallback robusto: Si el renombrado falla por bloqueo, intentar copiar
                        import shutil
                        try:
                            shutil.copy(final_temp, final_path_with_ext)
                            final = final_path_with_ext
                        except Exception as ecopy:
                            print(f"Copy Fallback Error: {ecopy}")
                            final = final_temp
                else:
                    # Fallback wget basico?
                    pass

            if use_ytdlp_fallback or (not final and not (usar_turbo or is_direct_download or str(vid_id).startswith("direct_"))):
                # --- MODO CLÁSICO (YT-DLP) ---
                if use_ytdlp_fallback and status:
                    # Pequeña notificación visual del cambio de motor a YT-DLP
                    await status.edit("🔄 Motor primario falló. Reintentando con YT-DLP...")
                    
                # Para YouTube, Facebook, Twitter, etc.
                opts = {
                    'outtmpl': f"{base_name}.%(ext)s",
                    'quiet': True, 
                    'no_warnings': True, 
                    'max_filesize': LIMIT_2GB,
                    'progress_hooks': [progress_hook], # HOOK AÑADIDO
                    'force_ipv4': True,
                    'socket_timeout': 30,
                    'continuedl': True,
                    'retries': 15,
                    'fragment_retries': 15,
                    'extractor_retries': 10, # Reintentar solicitudes del extractor de página
                    'http_headers': {
                        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36" if any(x in url_descarga for x in ["xhand.net", "xhamster.com", "xhcdn.com", "pornhub.com", "phncdn.com"]) else get_random_user_agent()
                    }
                }
                try:
                    from yt_dlp.networking.impersonate import ImpersonateTarget
                    opts['impersonate'] = ImpersonateTarget.from_str('chrome-110')
                except Exception as e_imp:
                    print(f"Error setting yt-dlp impersonate in downloader: {e_imp}")
                    opts['extractor_args'] = {'generic': {'impersonate': ['chrome']}}

                if "surrit.com" in url_descarga or "missav" in url_descarga:
                    opts['http_headers']['Referer'] = 'https://missav.ws/'
                elif "xhand.net" in url_descarga or "xhamster.com" in url_descarga or "xhcdn.com" in url_descarga:
                    opts['http_headers']['Referer'] = url
                elif "pornhub.com" in url_descarga or "phncdn.com" in url_descarga or "pornhub.com" in url or "phncdn.com" in url:
                    opts['http_headers']['Referer'] = 'https://es.pornhub.com/'

                if calidad == "mp3":
                    opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}]})
                elif calidad.isdigit():
                    opts['format'] = f"bv*[height<={calidad}]+ba/b[height<={calidad}] / best"
                else:
                    opts['format'] = 'best'
                opts['merge_output_format'] = 'mp4'

                cookie_file = sel_cookie(url_descarga)
                if cookie_file: opts['cookiefile'] = cookie_file

                if "eporner" in url_descarga:
                    opts['nocheckcertificate'] = True

                # --- FAST: PREPARAR OPCIONES ---
                force_std = False
                use_fast = False
                
                # OPTIMIZACIÓN: Descargas paralelas nativas para todos (a menos que se use Fast)
                opts['concurrent_fragment_downloads'] = 8
                
                if HAS_FAST and not calidad.startswith("html_") and conf.get('fast_enabled', True) and "eporner" not in url_descarga:
                    if not any(x in url_descarga for x in ["youtube.com", "youtu.be", "twitter.com", "x.com", "surrit.com", "hvidserv.com", "pornhub.com"]):
                        use_fast = True
                
                # Helper para ejecutar descarga Y extraer info con reintentos para evadir bloqueos / timeouts temporales
                async def run_ytdlp(options):
                    max_ytdlp_attempts = 5
                    for ytdlp_attempt in range(max_ytdlp_attempts):
                        try:
                            with yt_dlp.YoutubeDL(options) as ydl:
                                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url_descarga, download=True))
                                return info
                        except Exception as e_ytdlp:
                            err_msg = str(e_ytdlp)
                            # Si es un error temporal de red (timeout, rate limit, Cloudflare temporal, etc.)
                            is_temporary = any(x in err_msg.lower() for x in ["timeout", "timed out", "connection", "403", "503", "too many requests", "429", "curl: (28)"])
                            if is_temporary and ytdlp_attempt < max_ytdlp_attempts - 1:
                                print(f"⚠️ run_ytdlp falló (Intento {ytdlp_attempt+1}/{max_ytdlp_attempts}): {e_ytdlp}. Reintentando en 4s...")
                                if status:
                                    try: await status.edit(f"🔄 Error de conexión. Reintentando consulta ({ytdlp_attempt+2}/{max_ytdlp_attempts})...")
                                    except: pass
                                await asyncio.sleep(4)
                            else:
                                raise e_ytdlp

                # Intento 1: FAST (si aplica)
                info_dict = None
                
                if use_fast:
                    print(f"🚀 Intentando Fast para: {url_descarga}")
                    opts_fast = opts.copy()
                    opts_fast.update({
                        'external_downloader': FAST_PATH if os.path.exists(FAST_PATH) else 'aria'+'2c',
                        'external_downloader_args': ['-x','16','-k','1M','-s','16'],
                        'merge_output_format': 'mp4' 
                    })
                    try:
                        info_dict = await run_ytdlp(opts_fast)
                    except Exception as e:
                        print(f"⚠️ Fast falló: {e}")
                        if "WinError 32" in str(e) or "used by another process" in str(e):
                            raise e
                        
                        # Silent Retry
                        force_std = True

                # Intento 2: STANDARD (Si no se usó Fast o si Fast falló)
                if not use_fast or force_std:
                    try:
                        info_dict = await run_ytdlp(opts)
                    except Exception as e:
                        # RETRY WITHOUT COOKIES LOGIC
                        err_str = str(e)
                        print(f"⚠️ Error descarga: {err_str}")
                        
                        # --- 404 Not Found Handling ---
                        if "404" in err_str:
                            fail_url = (datos or {}).get('xvideos_original_url') or (datos or {}).get('pornhub_original_url') or (datos or {}).get('url') or url
                            if status: await status.edit(f"❌ **El video ha sido eliminado o el enlace no es válido**\n\n🔗 {fail_url}")
                            return

                        # --- Network Unreachable Handling ---
                        if "Errno 101" in err_str or "Network is unreachable" in err_str or "Connection reset by peer" in err_str or "ReadTimeout" in err_str:
                             if ".mp4" in url_descarga or "eporner.com" in url_descarga:
                                 print(f"⚠️ Error de red en YT-DLP. Intentando fallback nativo para: {url_descarga}")
                                 if status: await status.edit("🔄 Error de Red en el Servidor. Intentando descarga nativa ligera...")
                                 
                                 temp_out = f"dl_{chat_id}_{ts}_native.mp4"
                                 final_temp = os.path.join(DOWNLOAD_DIR, temp_out)
                                 fallback_success = False
                                 try:
                                     from utils import load_cookies_dict
                                     cookies = load_cookies_dict(sel_cookie(url_descarga))
                                     ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36" if any(x in url_descarga for x in ["xhand.net", "xhamster.com", "xhcdn.com"]) else get_random_user_agent()
                                     headers_fallback = {'User-Agent': ua}
                                     timeout_config = aiohttp.ClientTimeout(total=None, connect=60, sock_read=60)
                                     
                                     async with aiohttp.ClientSession(cookies=cookies, headers=headers_fallback, timeout=timeout_config) as session:
                                         for attempt in range(3):
                                             try:
                                                 if attempt > 0:
                                                     if status: await status.edit(f"🔄 Reintentando Nativo ({attempt+1}/3)...")
                                                     await asyncio.sleep(3)
                                                 
                                                 async with session.get(url_descarga) as resp:
                                                     if resp.status == 200:
                                                         total_size = int(resp.headers.get('Content-Length', 0))
                                                         downloaded = 0
                                                         start_t = time.time()
                                                         last_edit_t = 0
                                                         with open(final_temp, 'wb') as f:
                                                             while True:
                                                                 chunk = await resp.content.read(1024*1024) # 1MB chunks
                                                                 if not chunk: break
                                                                 f.write(chunk)
                                                                 downloaded += len(chunk)
                                                                 now_t = time.time()
                                                                 if now_t - last_edit_t > 4:
                                                                     last_edit_t = now_t
                                                                     p_f = downloaded/total_size*100 if total_size else 0
                                                                     pct = f"{int(p_f)}%" if total_size else "..."
                                                                     mb_curr = downloaded / (1024*1024)
                                                                     mb_total = total_size / (1024*1024) if total_size else 0
                                                                     speed = mb_curr / (now_t - start_t) if (now_t - start_t) > 0 else 0
                                                                     if status: await status.edit(f"⬇️ Descarga Nativa 📁 `{mb_curr:.1f}/{mb_total:.1f} MB` (`{pct}`) @ `{speed:.1f} MB/s`")
                                                                     try: update_progress(chat_id, status.id if status else 0, percent=p_f, speed=f"{speed:.1f}MB/s", status="Descarga Nativa", name=datos.get('titulo','Video'), url=url_descarga)
                                                                     except: pass
                                                         
                                                         final = final_temp
                                                         info_dict = {'title': datos.get('titulo', 'Video Directo'), 'ext': 'mp4'}
                                                         fallback_success = True
                                                         break
                                                     else:
                                                         print(f"⚠️ Fallback nativo HTTP Error: {resp.status}")
                                             except Exception as en:
                                                 print(f"Fallback nativo (network unreachable) failed attempt {attempt+1}: {en}")
                                 except Exception as ge:
                                     print(f"Global fallback nativo exception: {ge}")
                                 
                                 if not fallback_success:
                                     if status: await status.edit("❌ **Error de Red en el Servidor.**\nNo se pudo establecer conexión con el host del video. Intenta de nuevo más tarde.")
                                     return
                                 else:
                                     print("✅ Descarga nativa ligera completada.")
                             else:
                                 if status: await status.edit("❌ **Error de Red en el Servidor.**\nNo se pudo establecer conexión con el host del video. Intenta de nuevo más tarde.")
                                 return
                        
                        # No remover cookies para sitios que las requieren obligatoriamente (como missav, surrit o eporner)
                        # ni por errores genéricos de fragmentos/descarga que ocurren a mitad de una descarga sana
                        is_mandatory_cookies_site = any(domain in url_descarga.lower() for domain in ["missav", "surrit", "eporner"])
                        should_retry_no_cookies = (
                            'cookiefile' in opts 
                            and not is_mandatory_cookies_site
                            and any(x in err_str.lower() for x in ["sign in", "unable to extract", "403", "captcha", "empty", "forbidden", "cannot parse", "facebook"])
                        )
                        
                        if should_retry_no_cookies:
                            print("⚠️ Falló con cookies. Reintentando SIN cookies...")
                            del opts['cookiefile']
                            try:
                                info_dict = await run_ytdlp(opts)
                            except Exception as e2:
                                # FALLBACK FINAL: COBALT / TIKWM
                                print(f"⚠️ Falló Reintento Nativo: {e2}")
                                
                                err2_str = str(e2)
                                if "404" in err2_str:
                                     fail_url = (datos or {}).get('xvideos_original_url') or (datos or {}).get('pornhub_original_url') or (datos or {}).get('url') or url
                                     if status: await status.edit(f"❌ **El video ha sido eliminado o el enlace no es válido**\n\n🔗 {fail_url}")
                                     return
                                if "Errno 101" in err2_str or "Network is unreachable" in err2_str:
                                     if status: await status.edit("❌ **Error de Red en el Servidor (Unreachable).**")
                                     return
                                     
                                # --- TIKTOK FALLBACK (TIKWM) [RETRY PATH] ---
                                if "tiktok.com" in url_descarga:
                                      print("🎵 Falló yt-dlp (Retry). Intentando Fallback TIKWM...")
                                      tik_data = await get_tikwm_data(url_descarga)
                                      
                                      if tik_data:
                                          if 'images' in tik_data and tik_data['images']:
                                              print(f"📸 TikTok Slideshow detected: {len(tik_data['images'])} images")
                                              async with aiohttp.ClientSession() as session:
                                                  for idx, img_url in enumerate(tik_data['images']):
                                                      try:
                                                          async with session.get(img_url) as resp:
                                                              if resp.status == 200:
                                                                  img_path = os.path.join(job_dir, f"{base_name}_slide_{idx}.jpg")
                                                                  with open(img_path, 'wb') as f:
                                                                      f.write(await resp.read())
                                                                  multi_files.append(img_path)
                                                      except Exception as e_img:
                                                          print(f"Error downloading slide {idx}: {e_img}")
                                              if multi_files:
                                                  final = multi_files[0]
                                                  info_dict = {
                                                      'title': tik_data.get('title', 'TikTok Slideshow'),
                                                      'uploader': tik_data.get('author', {}).get('nickname', 'TikTok User'),
                                                      'description': tik_data.get('title', ''),
                                                      'ext': 'jpg'
                                                  }
                                              else: raise e2
                                          elif 'play' in tik_data:
                                              print(f"🎥 TikTok Video detected.")
                                              v_url = tik_data['play']
                                              temp_out = f"dl_{chat_id}_{ts}_tikwm.mp4"
                                              final_temp = os.path.join(DOWNLOAD_DIR, temp_out)
                                              async with aiohttp.ClientSession() as session:
                                                  async with session.get(v_url) as resp:
                                                      if resp.status == 200:
                                                          with open(final_temp, 'wb') as f:
                                                              while True:
                                                                  chunk = await resp.content.read(1024*1024)
                                                                  if not chunk: break
                                                                  f.write(chunk)
                                                          final = final_temp
                                                          info_dict = {
                                                              'title': tik_data.get('title', 'TikTok Video'),
                                                              'uploader': tik_data.get('author', {}).get('nickname', 'TikTok User'),
                                                              'description': tik_data.get('title', ''),
                                                              'ext': 'mp4',
                                                              'duration': tik_data.get('duration', 0)
                                                          }
                                                      else: raise e2
                                          else: raise e2
                                      else:
                                          pass # Try Cobalt

                                print("🧬 Intentando Fallback COBALT...")
                                cobalt_url = await get_cobalt_link(url_descarga, calidad)
                                if cobalt_url:
                                    # Silent Cobalt
                                    try:
                                        temp_out = f"dl_{chat_id}_{ts}_cobalt"
                                        final_temp = os.path.join(DOWNLOAD_DIR, temp_out)
                                        
                                        async with aiohttp.ClientSession() as session:
                                            async with session.get(cobalt_url) as resp:
                                                if resp.status == 200:
                                                    with open(final_temp, 'wb') as f:
                                                        while True:
                                                            chunk = await resp.content.read(1024*1024)
                                                            if not chunk: break
                                                            f.write(chunk)
                                                    final = final_temp
                                                    # Mock info dict for metadata
                                                    info_dict = {'title': 'Facebook/Social Video (Cobalt)', 'ext': 'mp4'}
                                                else:
                                                    if status: await status.edit(f"❌ Cobalt Server Error: {resp.status}")
                                                    raise e2
                                    except Exception as ec:
                                         print(f"❌ Cobalt Fallback Error: {ec}")
                                         raise e2 
                                else:
                                    print("❌ Cobalt no devolvió URL.")
                                    raise e2 
                        else:
                            # FIX: WinError 32/5 logic
                             if any(x in err_str for x in ["WinError 32", "WinError 5", "used by another process", "Access is denied"]):
                                print(f"⚠️ Conflicto de archivos ({err_str}). Reintentando loop de renomb... ")
                                posible_temp = f"{base_name}.temp.mp4"
                                posible_final = f"{base_name}.mp4"
                                renamed = False
                                for _ in range(5):
                                    await asyncio.sleep(2)
                                    if not os.path.exists(posible_final) and os.path.exists(posible_temp):
                                        try:
                                            os.rename(posible_temp, posible_final)
                                            renamed = True
                                            break
                                        except: pass
                                if not renamed and not os.path.exists(posible_final): raise e
                             else:
                                 # SI NO ES COOKIE ERROR NI LOCK ERROR, INTENTAR COBALT / TIKWM
                                 
                                 # --- TIKTOK FALLBACK (TIKWM) ---
                                 if "tiktok.com" in url_descarga:
                                      print("🎵 Falló yt-dlp. Intentando Fallback TIKWM...")
                                      tik_data = await get_tikwm_data(url_descarga)
                                      
                                      if tik_data:
                                          # A. SLIDESHOW (Images)
                                          if 'images' in tik_data and tik_data['images']:
                                              print(f"📸 TikTok Slideshow detected: {len(tik_data['images'])} images")
                                              
                                              async with aiohttp.ClientSession() as session:
                                                  for idx, img_url in enumerate(tik_data['images']):
                                                      try:
                                                          async with session.get(img_url) as resp:
                                                              if resp.status == 200:
                                                                  # Save as .jpg
                                                                  img_path = os.path.join(job_dir, f"{base_name}_slide_{idx}.jpg")
                                                                  with open(img_path, 'wb') as f:
                                                                      f.write(await resp.read())
                                                                  multi_files.append(img_path)
                                                      except Exception as e_img:
                                                          print(f"Error downloading slide {idx}: {e_img}")
                                                          
                                              if multi_files:
                                                  final = multi_files[0] # Fake final to pass checks
                                                  info_dict = {
                                                      'title': tik_data.get('title', 'TikTok Slideshow'),
                                                      'uploader': tik_data.get('author', {}).get('nickname', 'TikTok User'),
                                                      'description': tik_data.get('title', ''),
                                                      'ext': 'jpg'
                                                  }
                                              else:
                                                  raise e

                                          # B. VIDEO
                                          elif 'play' in tik_data:
                                              print(f"🎥 TikTok Video detected.")
                                              v_url = tik_data['play']
                                              temp_out = f"dl_{chat_id}_{ts}_tikwm.mp4"
                                              final_temp = os.path.join(DOWNLOAD_DIR, temp_out)
                                              
                                              async with aiohttp.ClientSession() as session:
                                                  async with session.get(v_url) as resp:
                                                      if resp.status == 200:
                                                          with open(final_temp, 'wb') as f:
                                                              # Download in chunks
                                                              while True:
                                                                  chunk = await resp.content.read(1024*1024)
                                                                  if not chunk: break
                                                                  f.write(chunk)
                                                          final = final_temp
                                                          info_dict = {
                                                              'title': tik_data.get('title', 'TikTok Video'),
                                                              'uploader': tik_data.get('author', {}).get('nickname', 'TikTok User'),
                                                              'description': tik_data.get('title', ''),
                                                              'ext': 'mp4',
                                                              'duration': tik_data.get('duration', 0)
                                                          }
                                                      else: raise e
                                          else:
                                              raise e
                                      else:
                                          # If TikWM failed, try Cobalt? (Or just fail)
                                          pass

                                 # --- FACEBOOK / OTHER COBALT FALLBACK ---
                                 elif "facebook.com" in url_descarga or "fb.watch" in url_descarga:
                                     print("🧬 Social Media Falló. Intentando Fallback COBALT directo...")
                                     cobalt_url = await get_cobalt_link(url_descarga, calidad)
                                     if cobalt_url:
                                        # Silent Cobalt
                                        try:
                                            temp_out = f"dl_{chat_id}_{ts}_cobalt"
                                            final_temp = os.path.join(DOWNLOAD_DIR, temp_out)
                                            async with aiohttp.ClientSession() as session:
                                                async with session.get(cobalt_url) as resp:
                                                    if resp.status == 200:
                                                        with open(final_temp, 'wb') as f:
                                                            while True:
                                                                chunk = await resp.content.read(1024*1024)
                                                                if not chunk: break
                                                                f.write(chunk)
                                                        final = final_temp
                                                        info_dict = {'title': 'Social Video (Cobalt)', 'ext': 'mp4'}
                                                    else: raise e
                                        except: raise e
                                     else: raise e
                                 else:
                                     raise e

                # --- METADATA TRANSLATION (POST-EXCUTION) ---
                if info_dict:
                    try:
                        # 1. Extract Real Info
                        real_title = info_dict.get('title')
                        real_desc = info_dict.get('description', '')
                        real_tags = info_dict.get('tags', [])
                        
                        # 2. Translate if needed (Requested: STICTLY LINKED TO LANGUAGE BUTTON)
                        # 2. Translate if needed (Requested: STICTLY LINKED TO LANGUAGE BUTTON)
                        # Only translate if language is explicitly 'es'
                        if conf.get('lang') == 'es':
                            # Silent Translation
                            # from ai_service import translate_text_pure, generate_hashtags_ai # REMOVED AI
                            from utils import traducir_texto 
                            
                            # A. Título
                            if real_title and real_title.lower() not in ['playlist', 'video']:
                                t_trans = await traducir_texto(real_title)
                                if t_trans: datos['titulo'] = t_trans
                                else: datos['titulo'] = real_title
                                
                            # B. Descripción
                            # Lower limit to > 0 to capture everything
                            if real_desc:
                                d_trans = await traducir_texto(real_desc[:1200]) # Limit input
                                if d_trans: datos['descripcion'] = d_trans
                                else: datos['descripcion'] = real_desc
                            
                            # C. Hashtags (STRICT: Original Tags + Text Hashtags NO AI INVENTION)
                            # Convert list to string
                            tags_from_yt = real_tags if real_tags else []
                            
                            # Also look for hashtags in description using Regex (Strict)
                            tags_from_desc = re.findall(r"#[^\s]+", real_desc) if real_desc else []
                            
                            # Combine unique tags
                            all_tags = list(set(tags_from_yt + tags_from_desc))
                            
                            if all_tags:
                                tags_raw = " ".join(all_tags)
                                # Translate Hashtags (Keeping them as tags)
                                # We pass them to translation. Expected: "#Red #Blue" -> "#Rojo #Azul"
                                tags_trans = await traducir_texto(tags_raw)
                                
                                if tags_trans:
                                    # Post-process to ensure they start with #
                                    clean_t = []
                                    for t in tags_trans.split():
                                        if not t.startswith('#'): t = f"#{t}"
                                        clean_t.append(t)
                                    datos['hashtags'] = " ".join(clean_t)
                                else:
                                    datos['hashtags'] = tags_raw
                            else:
                                datos['hashtags'] = ""
                                
                        # 3. Extract Dimensions explicitly for 'datos'
                        datos['width'] = info_dict.get('width')
                        datos['height'] = info_dict.get('height')
                        
                        # Extra check if width/height missing but resolution present
                        if not datos.get('width') and info_dict.get('resolution'):
                             # Try parsing "1920x1080"
                             try:
                                 res_parts = info_dict['resolution'].split('x')
                                 if len(res_parts) == 2:
                                     datos['width'] = int(res_parts[0])
                                     datos['height'] = int(res_parts[1])
                             except: pass

                    except Exception as e_meta:
                        print(f"⚠️ Metadata Translation Error: {e_meta}")

                if calidad == "mp3": final = f"{base_name}.mp3"
                else:
                    # Check Video AND Image extensions
                    for e in ['.mp4', '.mkv', '.webm', '.jpg', '.jpeg', '.png', '.webp', '.gif']:
                        if os.path.exists(base_name+e): 
                            final = base_name+e
                            break
        
        # --- END DOWNLOAD BLOCK (SEMAPHORE RELEASED) ---

        # --- POST-PROCESADO: DETECCION DE TIPO Y RENOMBRAMIENTO ---
        if not final or not os.path.exists(final):
            if status: await status.edit("❌ **Error: Archivo no encontrado.**\nLa descarga falló silenciosamente.")
            return

        # --- SMART IMAGE ANALYSIS REMOVED (STRICT NO AI) ---
        # User requested 0 AI invention. If yt-dlp gives no tags, we send empty tags.
        # Logic matches main.py: Only original metadata is preserved.
        # --- SILENT VIDEO FIX (Force MP4) ---
        # If video has no audio, Telegram sends it as GIF (Animation).
        # We force add silent audio to ensure it sends as Video (MP4) with controls.
        if calidad != "mp3" and not conf.get('doc_mode') and final.lower().endswith(('.mp4', '.mkv', '.webm')):
            from tools_media import has_audio_track, add_silent_audio
            has_audio = await asyncio.get_running_loop().run_in_executor(None, lambda: asyncio.run(has_audio_track(final)))
            
            if not has_audio:
                print(f"🔇 Silent Video Detected. Adding dummy audio to force MP4...")
                # if status: await status.edit("🔇 Video mudo detectado. Agregando audio silencioso...")
                
                new_final = await asyncio.get_running_loop().run_in_executor(None, lambda: asyncio.run(add_silent_audio(final)))
                
                if new_final and os.path.exists(new_final):
                    # Cleanup old
                    try: os.remove(final)
                    except: pass
                    final = new_final
                    file_size = os.path.getsize(final) # Update size
        pass

        if multi_files:
            # If we have multiple files (Slideshow), use them.
            files_to_send = multi_files
            file_size = sum(os.path.getsize(f) for f in multi_files)
        else:
            file_size = os.path.getsize(final)
            files_to_send = [final]
        is_split = False
        
        # --- SPLIT LOGIC (>1.9GB) ---
        if file_size > TG_LIMIT:
            # Silent Splitting
            
            # 1. Intentar corte inteligente (video)
            if calidad != "mp3" and not conf.get('doc_mode'):
                try:
                    parts = await asyncio.get_running_loop().run_in_executor(None, lambda: split_video_by_size(final, TG_LIMIT))
                    if parts:
                        files_to_send = parts
                        is_split = True
                except Exception as e:
                    print(f"Error Smart Split: {e}")
                    parts = []
            
            # 2. Fallback: Corte Binario (zip/7z/part) o video fallido
            if not is_split:
                 try:
                     parts = await asyncio.get_running_loop().run_in_executor(None, lambda: split_file_into_volumes(final, TG_LIMIT))
                     if parts:
                         files_to_send = parts
                         is_split = True
                 except Exception as e:
                     print(f"Error Binary Split: {e}")
                     pass

        # --- REDUNDANCY REMOVED ---


        # --- SUBIDA ---
        if return_paths:
            if status:
                try: await status.delete()
                except: pass
            job_dir_to_clean = None
            final = None
            thumb = None
            return {
                "files": files_to_send,
                "datos": datos,
                "vid_id": vid_id,
                "ckey": ckey,
                "is_doc_mode": is_doc_mode,
                "job_dir": job_dir
            }
        total_parts = len(files_to_send)
        sent_file_ids_list = [] # Collect IDs for caching
        uploaded_messages_objs = [] # Para el ordenamiento final

        if is_split and status:
            await status.edit(f"✅ Descarga lista. Iniciando subida de {total_parts} partes...")

        async def upload_part(i, f_path):
            if not os.path.exists(f_path): return None
            
            part_msg = f"[{i+1}/{total_parts}]" if total_parts > 1 else ""
            
            part_status = None
            if is_split:
                try: part_status = await client.send_message(chat_id, f"📤 Iniciando subida {part_msg}...", reply_to_message_id=msg_orig.id)
                except: part_status = status
            else:
                part_status = status
                if part_status: await part_status.edit(f"📤 Subiendo {part_msg}..." if part_msg else "📤 Subiendo Video...")
                
            final_caption = generate_caption(datos, conf, extra_tag=f"{part_msg}")
            
            # --- META & THUMB ---
            thumb_path = None
            duration, width, height = 0, 0, 0
            
            # Generar thumb para videos (incluso en modo documento, ya que Telegram lo soporta)
            if calidad != "mp3" and f_path.endswith(('.mp4', '.mkv', '.webm', '.ts')):
                # Reparar contenedor a MP4 Nativo FastStart si es necesario
                try:
                    fixed = await fast_remux_mp4(f_path)
                    if fixed and os.path.exists(fixed):
                        if fixed != f_path and os.path.exists(f_path):
                            try: os.remove(f_path)
                            except: pass
                        f_path = fixed
                except Exception as e_remux:
                    print(f"Error fast_remux_mp4: {e_remux}")

                try:
                     w, h, d = await get_meta(f_path)
                     width, height, duration = w, h, d
                except: pass

                seek_forced = None
                if conf.get('parallel_thumb_mode'):
                     p_sec = conf.get('parallel_thumb_seek', 2)
                     m, s = divmod(p_sec, 60)
                     hh, m = divmod(m, 60)
                     seek_forced = f"{int(hh):02d}:{int(m):02d}:{s:02d}"
                thumb_path = await get_thumb(f_path, chat_id, ts, duration, seek_override=seek_forced)
            
            sent_msg = None
            progress_tracking = [time.time(), 0]
            
            cb_progreso = progreso if part_status else None
            args_progreso = (part_status, progress_tracking, f"Subiendo {part_msg}") if part_status else ()

            try:
                if calidad == "mp3":
                     async with chat_action_loop(client, chat_id, enums.ChatAction.UPLOAD_AUDIO):
                         dur_a = await get_audio_dur(f_path)
                         kwargs = {"caption": final_caption, "title": datos.get('titulo', 'Audio'), "duration": dur_a, "reply_to_message_id": msg_orig.id}
                         if cb_progreso:
                             kwargs["progress"] = cb_progreso
                             kwargs["progress_args"] = args_progreso
                         sent_msg = await client.send_audio(chat_id, f_path, **kwargs)
                elif conf.get('doc_mode'):
                     async with chat_action_loop(client, chat_id, enums.ChatAction.UPLOAD_DOCUMENT):
                         kwargs = {"caption": final_caption, "thumb": thumb_path, "reply_to_message_id": msg_orig.id}
                         if cb_progreso:
                             kwargs["progress"] = cb_progreso
                             kwargs["progress_args"] = args_progreso
                         sent_msg = await client.send_document(chat_id, f_path, **kwargs)
                elif f_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                     async with chat_action_loop(client, chat_id, enums.ChatAction.UPLOAD_PHOTO):
                         kwargs = {"caption": final_caption, "reply_to_message_id": msg_orig.id}
                         if cb_progreso:
                             kwargs["progress"] = cb_progreso
                             kwargs["progress_args"] = args_progreso
                         sent_msg = await client.send_photo(chat_id, f_path, **kwargs)
                else:
                     try:
                         async with chat_action_loop(client, chat_id, enums.ChatAction.UPLOAD_VIDEO):
                             kwargs = {"caption": final_caption, "duration": duration, "width": width, "height": height, "thumb": thumb_path, "supports_streaming": True, "reply_to_message_id": msg_orig.id}
                             if cb_progreso:
                                 kwargs["progress"] = cb_progreso
                                 kwargs["progress_args"] = args_progreso
                             sent_msg = await client.send_video(chat_id, f_path, **kwargs)
                     except Exception as e_vid:
                         print(f"⚠️ Video Send Error: {e_vid}. Fallback to Doc.")
                         async with chat_action_loop(client, chat_id, enums.ChatAction.UPLOAD_DOCUMENT):
                             kwargs = {"caption": final_caption + "\n(Video Fallback)", "thumb": thumb_path, "reply_to_message_id": msg_orig.id}
                             if cb_progreso:
                                 kwargs["progress"] = cb_progreso
                                 kwargs["progress_args"] = args_progreso
                             sent_msg = await client.send_document(chat_id, f_path, **kwargs)

            except Exception as e_send:
                print(f"❌ Upload Error part {i}: {e_send}")
            
            # Limpiar el mensaje de estado temporal si es una parte dividida
            if is_split and part_status and part_status != status:
                try: await part_status.delete()
                except: pass
            
            # Cleanup Part
            if thumb_path and os.path.exists(thumb_path):
                try: os.remove(thumb_path)
                except: pass
            
            if is_split:
                try: os.remove(f_path)
                except: pass
                
            return sent_msg

        # Ejecutar todas las subidas de forma concurrente
        tasks = [upload_part(i, f_path) for i, f_path in enumerate(files_to_send)]
        results = await asyncio.gather(*tasks)

        for sent_msg in results:
            if sent_msg:
                uploaded_messages_objs.append(sent_msg)
                fid = None
                if sent_msg.video: fid = sent_msg.video.file_id
                elif sent_msg.document: fid = sent_msg.document.file_id
                elif sent_msg.audio: fid = sent_msg.audio.file_id
                
                if fid: sent_file_ids_list.append(fid)

        # --- ORDENAMIENTO FINAL VISUAL ---
        # Hacer ordenamiento si hay múltiples partes, o si hay una sola parte pero con portada (para que queden contiguas al final)
        if (total_parts > 1 and len(uploaded_messages_objs) > 1) or (total_parts == 1 and len(uploaded_messages_objs) == 1 and cover_msg):
            if status: await status.edit("✅ Subida lista. Ordenando partes en el chat...")
            
            # Borrar los mensajes desordenados (y la portada anterior si existe)
            msg_ids_to_delete = [m.id for m in uploaded_messages_objs]
            if cover_msg:
                msg_ids_to_delete.append(cover_msg.id)
            try: await client.delete_messages(chat_id, msg_ids_to_delete)
            except: pass
            
            # Reenviar la portada primero
            if cover_msg:
                try:
                    new_cover = await cover_msg.copy(chat_id, reply_to_message_id=msg_orig.id)
                    cover_msg = new_cover
                    await asyncio.sleep(1.2) # Pausa para mantener el orden
                except Exception as e_cov:
                    print(f"Error reenviando portada JAV: {e_cov}")
            
            # Reenviar ordenadamente
            new_uploaded_msgs = []
            for i, orig_msg in enumerate(uploaded_messages_objs):
                part_msg = f"[{i+1}/{total_parts}]" if total_parts > 1 else ""
                final_caption = generate_caption(datos, conf, extra_tag=part_msg if part_msg else None)
                try:
                    sent = None
                    if orig_msg.video:
                        sent = await client.send_video(chat_id, orig_msg.video.file_id, caption=final_caption, supports_streaming=True, reply_to_message_id=msg_orig.id)
                    elif orig_msg.document:
                        sent = await client.send_document(chat_id, orig_msg.document.file_id, caption=final_caption, reply_to_message_id=msg_orig.id)
                    elif orig_msg.audio:
                        sent = await client.send_audio(chat_id, orig_msg.audio.file_id, caption=final_caption, reply_to_message_id=msg_orig.id)
                    elif orig_msg.photo:
                        sent = await client.send_photo(chat_id, orig_msg.photo.file_id, caption=final_caption, reply_to_message_id=msg_orig.id)
                    
                    if sent:
                        new_uploaded_msgs.append(sent)
                    await asyncio.sleep(1.5) # Pausa para mantener el orden
                except Exception as e:
                    print(f"Error reenviando parte {i}: {e}")
            uploaded_messages_objs = new_uploaded_msgs

        if status:
            try: await status.delete()
            except: pass
        
        # --- FINAL CACHE SAVE (AFTER LOOP) ---
        if sent_file_ids_list and vid_id:
            # Determine if we save a list or a single string
            final_cache_payload = sent_file_ids_list[0] if len(sent_file_ids_list) == 1 else sent_file_ids_list
             
            # Strict Save: ID, URL, Quality, DocMode, FileID/List
            print(f"✨ Saving to Cache: {vid_id} (Parts: {len(sent_file_ids_list)})")
            # We use create_task to be non-blocking
            asyncio.create_task(save_cached_file_strict(vid_id, url_descarga, ckey, is_doc_mode, final_cache_payload))
        
        # Cleanup Original if Split or just generic cleanup
        if final and os.path.exists(final):
            try: os.remove(final)
            except: pass
            
        final_messages = []
        if cover_msg:
            final_messages.append(cover_msg)
        final_messages.extend(uploaded_messages_objs)
        return final_messages
            
    except Exception as e:
        print(f"❌ Error en procesar_descarga: {e}")
        if status: 
            try:
                err_lower = str(e).lower()
                fail_url = (datos or {}).get('xvideos_original_url') or (datos or {}).get('pornhub_original_url') or (datos or {}).get('url') or url
                if "404" in err_lower or "not found" in err_lower or "video no encontrado" in err_lower:
                    await status.edit(f"❌ **El video ha sido eliminado o el enlace no es válido**\n\n🔗 {fail_url}")
                else:
                    await status.edit(f"❌ Error: {str(e)[:100]}")
            except: pass
    finally:
        remove_active(chat_id, task_key)
        # Cleanup Job Dir (Full Folder isolation cleanup)
        import shutil
        try:
             # Ensure job_dir_to_clean is defined and exists (scope check)
             if 'job_dir_to_clean' in locals() and job_dir_to_clean and os.path.exists(job_dir_to_clean):
                 shutil.rmtree(job_dir_to_clean, ignore_errors=True)
        except: pass

        # Fallback specific cleanup if job_dir verification failed (legacy)
        if final and os.path.exists(final):
            try: os.remove(final)
            except: pass
        if thumb and os.path.exists(thumb):
            try: os.remove(thumb)
            except: pass
        # Clean up url_storage entry for this download
        if vid_id:
            st = url_storage.get(chat_id)
            if st:
                # Si es un dict simple
                if isinstance(st, dict) and st.get('id') == vid_id:
                     url_storage.pop(chat_id, None)
                # Si es una lista (links_data)
                elif isinstance(st, dict) and 'links_data' in st:
                     st['links_data'] = [item for item in st['links_data'] if item.get('id') != vid_id]
                     url_storage[chat_id] = st

# Cleanup from end
