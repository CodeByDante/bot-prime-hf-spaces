import re

def clean_comparison_string(text):
    if not text:
        return ""
    # Quitar prefijo de "titulo:" o "título:" y lo que esté antes
    text_clean = re.sub(r'^.*?\b(?:titulos?|títulos?):\s*', '', text, flags=re.IGNORECASE)
    # Quitar caracteres no alfanuméricos (incluyendo emojis)
    text_clean = re.sub(r'[^a-zA-Z0-9ñÑáéíóúÁÉÍÓÚ]', ' ', text_clean)
    # Reducir espacios múltiples
    text_clean = re.sub(r'\s+', ' ', text_clean)
    return text_clean.strip().lower()


def extract_title_from_caption(caption):
    if not caption:
        return ""
    # Buscar una línea que contenga "titulo:" o "título:"
    for line in caption.split('\n'):
        if re.search(r'\b(?:titulo|título):\s*', line, re.IGNORECASE):
            return re.sub(r'^.*?\b(?:titulo|título):\s*', '', line, flags=re.IGNORECASE).strip()
    # Si no se encuentra, usar la primera línea
    return caption.split('\n')[0].strip()


def get_message_title(message):
    if message.message:
        return message.message.split('\n')[0].strip()
    
    doc = getattr(message, 'video', None) or getattr(message, 'document', None)
    if doc:
        for attr in doc.attributes:
            if hasattr(attr, "file_name") and attr.file_name:
                name = attr.file_name
                name = re.sub(r'\.[a-zA-Z0-9]+$', '', name)
                name = name.replace('_', ' ').replace('.', ' ')
                return name.strip()
    return ""


def extract_series_name(title):
    if not title:
        return ""
    # Quitar indicadores de episodio
    clean = re.sub(r'\s+(?:Episodio|Capitulo|Capítulo|Ep|Cap|Part|Parte)\s+\d+.*$', '', title, flags=re.IGNORECASE)
    clean = re.sub(r'\s+\d+\s*$', '', clean)
    clean = clean.strip(" -:|[]()")
    return clean.strip()


def parse_episode_number(title):
    match = re.search(r'(?:Episodio|Capitulo|Capítulo|Ep|Cap|Part|Parte)\s+(\d+)', title, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    match = re.search(r'\b(\d+)\b\s*$', title)
    if match:
        return int(match.group(1))
        
    return 999


def calculate_distribution(num_chapters, total_screenshots=10):
    if num_chapters <= 0:
        return []
    cociente = total_screenshots // num_chapters
    residuo = total_screenshots % num_chapters
    
    dist = []
    for i in range(num_chapters):
        count = cociente + (1 if i < residuo else 0)
        dist.append(count)
    return dist


def limpiar_entidades_html(clean_text):
    return (clean_text
            .replace('&nbsp;', ' ')
            .replace('&quot;', '"')
            .replace('&amp;', '&')
            .replace('&#x27;', "'")
            .replace('&#39;', "'")
            .replace('&lt;', '<')
            .replace('&gt;', '>')
            .replace('&iacute;', 'í')
            .replace('&aacute;', 'á')
            .replace('&eacute;', 'é')
            .replace('&oacute;', 'ó')
            .replace('&uacute;', 'ú')
            .replace('&ntilde;', 'ñ')
            .replace('&Iacute;', 'Í')
            .replace('&Aacute;', 'Á')
            .replace('&Eacute;', 'É')
            .replace('&Oacute;', 'Ó')
            .replace('&Uacute;', 'Ú')
            .replace('&Ntilde;', 'Ñ'))


async def safe_edit_status(status_msg, text, parse_mode='markdown'):
    import asyncio
    from telethon.errors import FloodWaitError
    retries = 3
    while retries > 0:
        try:
            await status_msg.edit(text, parse_mode=parse_mode)
            break
        except FloodWaitError as e:
            print(f"⚠️ [FloodWait en status_msg.edit] Esperando {e.seconds} segundos...")
            await asyncio.sleep(e.seconds)
            retries -= 1
        except Exception as e:
            print(f"❌ Error al editar status_msg: {e}")
            break

