import re
import asyncio
import urllib.request
import urllib.parse
from telethon.errors import FloodWaitError

from core.client import client
from utils.helpers import extract_title_from_caption, limpiar_entidades_html, safe_edit_status


def buscar_sinopsis_en_veohentai(title):
    queries_to_try = []
    clean_title = re.sub(r'[!?,.:-]', ' ', title).strip()
    clean_title = re.sub(r'\s+', ' ', clean_title)
    queries_to_try.append(clean_title)
    
    if "gal" in clean_title.lower():
        queries_to_try.append(re.sub(r'\bgal\b', 'gyaru', clean_title, flags=re.IGNORECASE))
    elif "gyaru" in clean_title.lower():
        queries_to_try.append(re.sub(r'\bgyaru\b', 'gal', clean_title, flags=re.IGNORECASE))
        
    words = clean_title.split()
    if len(words) > 2:
        queries_to_try.append(" ".join(words[:2]))
    elif len(words) > 1:
        queries_to_try.append(" ".join(words[:1]))
        
    seen = set()
    queries = []
    for q in queries_to_try:
        if q and q.lower() not in seen:
            seen.add(q.lower())
            queries.append(q)
            
    for q in queries:
        try:
            search_url = "https://veohentai.com/?s=" + urllib.parse.quote_plus(q)
            req = urllib.request.Request(
                search_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')
                
            pattern_links = r'href="(https://veohentai.com/ver/[^"]+)"'
            links = re.findall(pattern_links, html)
            if not links:
                pattern_series = r'href="(https://veohentai.com/serie/[^"]+)"'
                links = re.findall(pattern_series, html)
                
            if not links:
                continue
                
            target_link = None
            for link in links:
                if "episodio-1" in link.lower() or "episodio-01" in link.lower() or "capitulo-1" in link.lower():
                    target_link = link
                    break
            if not target_link:
                target_link = links[0]
                
            req_page = urllib.request.Request(
                target_link,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
            )
            
            with urllib.request.urlopen(req_page, timeout=10) as response_page:
                html_page = response_page.read().decode('utf-8', errors='ignore')
                
            pattern_genres = r'href="https://veohentai.com/genero/[^/]+/"[^>]*>(.*?)</a>'
            genres_found = re.findall(pattern_genres, html_page)
            generos_list = []
            for g in genres_found:
                g_clean = g.strip()
                if g_clean:
                    hashtag = "#" + re.sub(r'[^a-zA-Z0-9ñÑáéíóúÁÉÍÓÚ]', '', g_clean).lower()
                    generos_list.append(hashtag)
            generos_str = " ".join(generos_list) if generos_list else "#hentai"
    
            pattern_content = r'<div class="entry-content[^"]*">(.*?)</div>'
            content_match = re.search(pattern_content, html_page, re.DOTALL)
            if content_match:
                snippet = content_match.group(1)
                snippet = re.sub(r'<script[^>]*>.*?</script>', '', snippet, flags=re.DOTALL)
                clean_text = re.sub(r'<[^>]+>', '', snippet).strip()
                clean_text = limpiar_entidades_html(clean_text)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                if len(clean_text) > 50:
                    return {
                        'sinopsis': clean_text,
                        'generos': generos_str
                    }
        except Exception:
            pass
    return None

def buscar_sinopsis_en_internet(title):
    query = f"{title} sinopsis anime"
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
    
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        pattern = r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>'
        snippets = re.findall(pattern, html, re.DOTALL)
        
        for snippet in snippets:
            clean_text = re.sub(r'<[^>]+>', '', snippet).strip()
            clean_text = limpiar_entidades_html(clean_text)
            if len(clean_text) > 50 and "JavaScript" not in clean_text and "cookies" not in clean_text:
                return clean_text
    except Exception:
        pass
    return None


async def procesar_comando_sinopsis(event):
    chat_id = event.chat_id
    
    # Parse scan limit (default None to scan everything)
    limit = None
    args = event.message.message.split()
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            pass

    limit_desc = f"los últimos {limit} mensajes" if limit else "todo el historial"
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Escaneando álbumes en {limit_desc} para agregar sinopsis...")
    
    try:
        messages = []
        async for m in client.iter_messages(chat_id, limit=limit):
            messages.append(m)
            
        albums_a_procesar = []
        for msg in messages:
            if msg.photo and msg.message:
                caption = msg.message.strip()
                if "sinopsis" in caption.lower() or "synopsis" in caption.lower():
                    continue
                if re.search(r'\b(?:Episodio|Capitulo|Capítulo|Ep|Cap)\s+\d+', caption, re.IGNORECASE):
                    continue
                    
                titulo = extract_title_from_caption(caption)
                
                albums_a_procesar.append({
                    'msg': msg,
                    'title': titulo
                })
                
        if not albums_a_procesar:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** Todos los álbumes ya cuentan con su sinopsis.")
            await asyncio.sleep(5)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        await safe_edit_status(status_msg, f"📝 **[Bot Prime]** Detectados {len(albums_a_procesar)} álbumes sin sinopsis. Buscando...")
        
        for item in albums_a_procesar:
            msg = item['msg']
            titulo = item['title']
            
            await safe_edit_status(status_msg, f"🌐 **[Bot Prime]** Buscando información de: '{titulo}'...")
            
            resultado = buscar_sinopsis_en_veohentai(titulo)
            if resultado:
                sinopsis = resultado.get('sinopsis')
                generos = resultado.get('generos')
            else:
                sinopsis = buscar_sinopsis_en_internet(titulo)
                generos = "#hentai #anime"
                
            if sinopsis:
                texto_base = f"🉐Titulo: {titulo}\n\n🀄️Sinopsis: \n\n✔️genero: {generos}"
                limite_sinopsis = 1000 - len(texto_base)
                
                if len(sinopsis) > limite_sinopsis:
                    sinopsis_recortada = sinopsis[:limite_sinopsis - 4]
                    ultimo_espacio = sinopsis_recortada.rfind(' ')
                    if ultimo_espacio > 0:
                        sinopsis = sinopsis_recortada[:ultimo_espacio] + "..."
                    else:
                        sinopsis = sinopsis_recortada + "..."
                        
                nuevo_texto = (
                    f"🉐Titulo: {titulo}\n\n"
                    f"🀄️Sinopsis: {sinopsis}\n\n"
                    f"✔️genero: {generos}"
                )
                
                while True:
                    try:
                        await client.edit_message(chat_id, msg.id, nuevo_texto)
                        break
                    except FloodWaitError as e:
                        print(f"⚠️ [FloodWait] Esperando {e.seconds} segundos para editar sinopsis...")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"Error al editar mensaje ID {msg.id}: {e}")
                        break
                    
            await asyncio.sleep(3)
            
        await safe_edit_status(status_msg, "✅ **[Bot Prime]** Proceso de sinopsis completado.")
        await asyncio.sleep(5)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
        await asyncio.sleep(10)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
