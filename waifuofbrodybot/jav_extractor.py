import re
import base64
import os
import urllib.parse
import time
from curl_cffi import requests

# Headers simulando Chrome en Windows (Menos sospechoso para Cloudflare con Cookies)
JAV_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.google.com/',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1'
}

from config import COOKIES_DIR

def load_cookies(filename):
    """Carga cookies desde archivo Netscape en la carpeta de cookies."""
    path = os.path.join(COOKIES_DIR, filename)
    cookies = {}
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                for line in f:
                    if line.strip().startswith('#') or not line.strip(): continue
                    parts = line.strip().split('\t')
                    if len(parts) >= 7:
                        cookies[parts[5]] = parts[6]
        except: pass
    return cookies

def decode_base64(s):
    try:
        return base64.b64decode(s + '=' * (-len(s) % 4)).decode('utf-8')
    except: return None

def find_m3u8_deep(text):
    """Busca cualquier cosa que parezca un m3u8 en el texto sucio."""
    candidates = set()
    
    # 1. Patrón clásico http...m3u8
    matches = re.findall(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', text)
    for m in matches:
        clean = m.replace('\\/', '/')
        candidates.add(clean)
        
    # 2. Patrón Base64 común en JAV
    b64_matches = re.findall(r'file\s*:\s*["\']([a-zA-Z0-9+/=]{20,})["\']', text)
    for b in b64_matches:
        decoded = decode_base64(b)
        if decoded and 'http' in decoded and '.m3u8' in decoded:
            candidates.add(decoded)
            
    return candidates

def unpack_missav_surrit(html_text):
    """Desencripta el packer eval(function(p,a,c,k,e,d)) de MissAV para extraer el link de surrit."""
    match = re.search(r"'([^']+)'\.split\('\|'\)", html_text)
    if not match: return None
    words = match.group(1).split('|')
    
    match_p = re.search(r"\}\('(.*?)', *\d+, *\d+,", html_text)
    if match_p:
        p = match_p.group(1)
        def base36(i):
            digits = "0123456789abcdefghijklmnopqrstuvwxyz"
            res = ""
            while i > 0:
                res = digits[i % 36] + res
                i //= 36
            return res or "0"
            
        for i, word in enumerate(words):
            if not word: continue
            idx = base36(i)
            p = re.sub(r'\b' + idx + r'\b', word, p)
            
        m3u8_links = re.findall(r'(https?://surrit\.com[^\s\'"]+\.m3u8)', p)
        if m3u8_links:
            return m3u8_links[0]
    return None

def extraer_jav_directo(url):
    print(f"⚡ [JAV Turbo] Atacando: {url}")
    
    final_links = []
    seen = set()
    page_title = "JAV Video"
    
    html = None
    r_status = None
    
    # 30 intentos idénticos con cookies activas y simulación de Chrome
    for attempt in range(1, 31):
        try:
            print(f"🔄 [JAV Turbo] Intento {attempt}/30 con cookies...")
            session = requests.Session()
            
            c = load_cookies('cookies_jav.txt')
            if not c: c = load_cookies('cookies_pornhub.txt')
            if c: session.cookies.update(c)
            
            parsed_url = urllib.parse.urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/"
            
            impersonate_targets = ["chrome120", "chrome124", "safari18_0", "chrome119"]
            imp = impersonate_targets[attempt % len(impersonate_targets)]
            
            r = session.get(url, headers={'Referer': base_url}, impersonate=imp, timeout=15)
            r_status = r.status_code
            
            if r.status_code not in [403, 503]:
                html = r.text
                print(f"✅ [JAV Turbo] Intento {attempt} exitoso! (HTTP {r.status_code})")
                break
            else:
                print(f"⚠️ [JAV Turbo] Intento {attempt} bloqueado por Cloudflare (HTTP {r.status_code})")
        except Exception as e:
            print(f"⚠️ [JAV Turbo] Intento {attempt} falló con error: {e}")
        
        if not html and attempt < 30:
            time.sleep(2)
            
    if not html:
        print(f"❌ [JAV Turbo] Todos los intentos de bypass fallaron (Último status: {r_status})")
        return ([], page_title, None)
        
    try:
        # Extraer el Título Real de la página
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        if title_match:
            page_title = title_match.group(1).replace(' - MissAV.ws', '').replace(' - MissAV', '').strip()
        
        # Extraer la portada (og:image o poster)
        cover_url = None
        cover_match = re.search(r'<meta\s+(?:property|name)="og:image"\s+content="([^"]+)"', html, re.IGNORECASE)
        if not cover_match:
            cover_match = re.search(r'poster="([^"]+)"', html, re.IGNORECASE)
        if cover_match:
            cover_url = cover_match.group(1)
        
        # 1. BÚSQUEDA DEL PACKER DE MISSAV (Desencriptar JS)
        surrit_url = unpack_missav_surrit(html)
        if surrit_url:
            if surrit_url not in seen:
                seen.add(surrit_url)
                final_links.append({'url': surrit_url, 'size': 0, 'res': 'MissAV HD (Surrit)'})
                
        # 2. BÚSQUEDA DIRECTA EN EL HTML PRINCIPAL
        found_urls = find_m3u8_deep(html)
        for u in found_urls:
            if u not in seen:
                seen.add(u)
                final_links.append({'url': u, 'size': 0, 'res': 'JAV Direct (Main)'})
 
        # 3. BÚSQUEDA DE IFRAMES (El video suele estar aquí)
        iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)
        
        for iframe_src in iframes:
            if not iframe_src.startswith('http'): 
                if iframe_src.startswith('//'): iframe_src = 'https:' + iframe_src
                else: continue
            
            # Ignorar publicidad obvia
            if 'ads' in iframe_src or 'banner' in iframe_src: continue
            
            print(f"⚡ Escaneando Iframe: {iframe_src}")
            
            if iframe_src not in seen:
                seen.add(iframe_src)
                final_links.append({'url': iframe_src, 'size': 0, 'res': 'Iframe Player (YT-DLP)'})
 
            try:
                # Entrar al iframe intentando evadir Cloudflare también (3 intentos idénticos con cookies)
                iframe_html = None
                for iframe_attempt in range(1, 4):
                    try:
                        session_frame = requests.Session()
                        c = load_cookies('cookies_jav.txt')
                        if not c: c = load_cookies('cookies_pornhub.txt')
                        if c: session_frame.cookies.update(c)
                        
                        impersonate_targets = ["chrome120", "chrome124", "safari18_0", "chrome119"]
                        imp = impersonate_targets[iframe_attempt % len(impersonate_targets)]
                        
                        r_frame = session_frame.get(iframe_src, headers={'Referer': url}, impersonate=imp, timeout=10)
                        if r_frame.status_code not in [403, 503]:
                            iframe_html = r_frame.text
                            break
                        else:
                            print(f"⚠️ [JAV Turbo iframe] Intento {iframe_attempt} bloqueado por Cloudflare (HTTP {r_frame.status_code})")
                    except Exception as e:
                        print(f"⚠️ [JAV Turbo iframe] Intento {iframe_attempt} falló con error: {e}")
                    
                    if not iframe_html and iframe_attempt < 3:
                        time.sleep(1)
                
                if iframe_html:
                    frame_m3u8s = find_m3u8_deep(iframe_html)
                    for u in frame_m3u8s:
                        if u not in seen:
                            seen.add(u)
                            final_links.insert(0, {'url': u, 'size': 0, 'res': 'JAV Stream (Extracted)'})
            except: 
                pass
 
    except Exception as e:
        print(f"⚠️ Error JAV Extractor: {e}")
 
    return (sorted(final_links, key=lambda x: 0 if '.m3u8' in x['url'] or '.mp4' in x['url'] else 1), page_title, cover_url)