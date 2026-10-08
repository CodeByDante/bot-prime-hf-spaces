import re
import time
import asyncio
from telethon import events
from telethon.errors import FloodWaitError
from core.client import client
from utils.channel_resolver import matches_channel
from utils.helpers import safe_edit_status



# Expresión regular para códigos JAV (ej: PRED-769, DVDMS-149, GVG-707, etc.)
JAV_REGEX = re.compile(r'\b([a-zA-Z0-9]{2,10}-\d{2,7})\b')

# Prefijos excluidos comunes para evitar falsos positivos
EXCLUDED_PREFIXES = {
    'ep', 'pt', 'part', 'cap', 'vol', 'v', 'ed', 'id', 'p',
    'dvd', 'cd', 'mp4', 'mkv', 'avi', 'gif', 'png', 'jpg'
}

def determine_censorship(text):
    text_lower = text.lower()
    if "sin censura" in text_lower or "uncensored" in text_lower or re.search(r'\b(?:s/c|sin_censura)\b', text_lower):
        return "sin censura"
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

def parse_master_caption(caption):
    # Intentar extraer info del capitulo master
    part_str, (part_num, total_parts) = extract_part(caption)
    if total_parts <= 1:
        return None
        
    code = None
    matches = JAV_REGEX.findall(caption)
    for raw_code in matches:
        prefix = raw_code.split('-')[0]
        if prefix.lower() not in EXCLUDED_PREFIXES:
            code = raw_code
            break
            
    if not code:
        return None
        
    censorship = determine_censorship(caption)
    
    # Limpiar descripción
    desc = caption
    
    # Remover prefijos de parte como "Enlace Directo [1/2]", "video [1/3]", "video [1 de 3]", etc.
    part_pattern = re.compile(
        r'(?:Enlace\s+Directo|video|video\s+directo)?\s*\[?\d+\s*(?:/|de)\s*\d+\]?', 
        re.IGNORECASE
    )
    desc = part_pattern.sub("", desc)
    
    # Remover el código JAV
    desc = desc.replace(code, "")
    
    # Remover etiquetas de censura
    if censorship:
        cens_patterns = [
            r'\(?sin\s+censura\)?', r'\(?con\s+censura\)?',
            r'\(?uncensored\)?', r'\(?censored\)?',
            r'\b(?:s/c|c/c)\b', r'\b(?:sin|con)_censura\b'
        ]
        for pat in cens_patterns:
            desc = re.sub(pat, "", desc, flags=re.IGNORECASE)
            
    # Limpiar espacios y caracteres basura iniciales/finales
    desc = desc.strip()
    desc = re.sub(r'^[:\-\s\u200b]+', '', desc)
    desc = desc.strip()
    
    return {
        'code': code,
        'censorship': censorship,
        'total_parts': total_parts,
        'description': desc
    }

def format_caption(code, censorship, part_num, total_parts, description):
    cens_str = f" ({censorship})" if censorship else ""
    header = f"{code}{cens_str} [{part_num}/{total_parts}]"
    if description:
        return f"{header}\n{description}"
    return header

async def procesar_comando_renombrador_simple(event):
    chat_id = event.chat_id
    
    # Obtener información del chat
    chat = await event.get_chat()
    chat_title = getattr(chat, 'title', '') or ''
    is_private = event.is_private
    
    # Restringir a "JAV REGULAR" excepto para chats privados
    if not is_private and not matches_channel(chat_id, chat_title, "jav_regular"):
        error_msg = await event.reply("❌ **[Bot Prime]** Este comando es exclusivo para el canal **JAV REGULAR**.")
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
    status_msg = await event.reply(f"🔍 **[Bot Prime]** Analizando videos en {limit_desc} para corregir nombres...")
    
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
                
        # Sort messages by ID ascending (chronological order)
        messages_sorted = sorted(messages, key=lambda x: x.id)
        
        # 2. Identificar videos que forman parte de series
        parsed_items = []
        for msg in messages_sorted:
            if not msg.video:
                continue
            caption = msg.message or ""
            part_str, (part_num, total_parts) = extract_part(caption)
            if total_parts > 1:
                parsed_items.append({
                    'msg': msg,
                    'part_num': part_num,
                    'total_parts': total_parts,
                    'caption': caption
                })
                
        # 3. Agrupar partes que correspondan a la misma serie (ID cercano y mismo total_parts)
        groups = []
        for item in parsed_items:
            added = False
            for grp in groups:
                if grp['total_parts'] == item['total_parts']:
                    # Proximidad de ID <= 8 mensajes
                    if any(abs(item['msg'].id - existing['msg'].id) <= 8 for existing in grp['items']):
                        grp['items'].append(item)
                        added = True
                        break
            if not added:
                groups.append({
                    'total_parts': item['total_parts'],
                    'items': [item]
                })
                
        # 4. Determinar los cambios a realizar en cada grupo
        edit_actions = []
        for grp in groups:
            grp['items'].sort(key=lambda x: x['part_num'])
            master_info = None
            
            # Buscar el elemento que contiene el código JAV y descripción
            for item in grp['items']:
                info = parse_master_caption(item['caption'])
                if info and info['code']:
                    master_info = info
                    break
                    
            if not master_info:
                continue # No hay código JAV para este grupo
                
            code = master_info['code']
            censorship = master_info['censorship']
            description = master_info['description']
            total_parts = master_info['total_parts']
            
            for item in grp['items']:
                part_num = item['part_num']
                new_caption = format_caption(code, censorship, part_num, total_parts, description)
                
                # Si el caption actual difiere del nuevo formato, agendar edición
                if item['caption'].strip() != new_caption.strip():
                    edit_actions.append({
                        'msg': item['msg'],
                        'new_caption': new_caption
                    })
                    
        if not edit_actions:
            await safe_edit_status(status_msg, "✅ **[Bot Prime]** Todos los videos analizados ya tienen el formato correcto.")
            await asyncio.sleep(6)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
            return
            
        # 5. Ejecutar las ediciones de los mensajes
        total_edits = len(edit_actions)
        await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Se encontraron {total_edits} mensajes por corregir. Iniciando renombrado...")
        await asyncio.sleep(2)
        
        success_count = 0
        for idx, action in enumerate(edit_actions, 1):
            msg = action['msg']
            new_caption = action['new_caption']
            
            await safe_edit_status(status_msg, f"⚙️ **[Bot Prime]** Editando mensaje {idx} de {total_edits}...")
            
            retries = 3
            edited = False
            while retries > 0:
                try:
                    await client.edit_message(chat_id, msg.id, new_caption)
                    edited = True
                    break
                except FloodWaitError as e:
                    print(f"[Renombrador Simple] FloodWait: esperando {e.seconds} seg...")
                    await safe_edit_status(status_msg, f"⏳ **[Bot Prime]** Límite excedido. Esperando {e.seconds} seg...")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    print(f"[Renombrador Simple] Error editando mensaje {msg.id}: {e}")
                    retries -= 1
                    if retries > 0:
                        await asyncio.sleep(2)
            
            if edited:
                success_count += 1
            
            # Espera entre ediciones
            await asyncio.sleep(1.5)
            
        await safe_edit_status(status_msg, f"✅ **[Bot Prime]** Renombrado completado. Se corrigieron {success_count} de {total_edits} mensajes.")
        await asyncio.sleep(8)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
