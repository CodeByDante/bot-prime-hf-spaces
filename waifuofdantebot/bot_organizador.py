import asyncio
import re
import os
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.types import Message

# Configuración
BOT_TOKEN = "8645264987:AAGkJM_Wntso4KJzN44IIV488GisPCH0MQs"
API_ID = 29330032      # Usando tu API_ID común
API_HASH = "b0825fdbecb48db90de25f4633bba79f"

# Diccionarios temporales
# Estructura: { "NombreBaseDelVideo": { "chat_id": ID, "timer": task, "parts": { part_num: Message }, "sent_msgs": [Message], "total_parts": int or None } }
pending_groups = defaultdict(lambda: {"chat_id": None, "timer": None, "parts": {}, "sent_msgs": [], "total_parts": None})

# Tiempo a esperar después del último archivo recibido si no se sabe el total
WAIT_TIME = 15

app = Client("OrganizadorBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

async def delete_messages(msgs):
    """Elimina mensajes de Telegram de manera asíncrona."""
    for m in msgs:
        try:
            await m.delete()
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"⚠️ Error al borrar mensaje anterior: {e}")

async def forward_and_update_group(base_name):
    group = pending_groups[base_name]
    if not group or not group["parts"]:
        return

    chat_id = group["chat_id"]
    parts = group["parts"]
    sent_msgs = group.get("sent_msgs", [])

    # 1. Eliminar los mensajes reenviados anteriormente si existen
    if sent_msgs:
        print(f"🗑️ Eliminando {len(sent_msgs)} mensajes anteriores de: {base_name}")
        asyncio.create_task(delete_messages(sent_msgs))
        group["sent_msgs"] = []

    # 2. Ordenar las partes disponibles (0 es portada, 1, 2, 3...)
    sorted_parts = sorted(parts.items(), key=lambda x: x[0])
    
    # 3. Reenviar la versión actualizada de las partes
    new_sent_msgs = []
    print(f"📦 Reenviando {len(sorted_parts)} partes en orden de: {base_name}")
    for part_num, msg in sorted_parts:
        try:
            # Enviar como copia
            sent = await msg.copy(chat_id)
            new_sent_msgs.append(sent)
            await asyncio.sleep(1.2)  # Pausa para asegurar el orden
        except Exception as e:
            print(f"❌ Error reenviando parte {part_num}: {e}")

    # Guardar las referencias de los nuevos mensajes enviados
    group["sent_msgs"] = new_sent_msgs

    # 4. Verificar si está completo
    total = group["total_parts"]
    video_parts = [k for k in parts.keys() if k > 0]
    
    if total is not None and len(video_parts) >= total:
        print(f"✅ Grupo {base_name} completado exitosamente ({len(video_parts)}/{total} partes).")
        if group["timer"]:
            group["timer"].cancel()
        
        if total > 1:
            try:
                await app.send_message(chat_id, f"✅ **{base_name}** subido en orden ({total}/{total} partes).")
            except:
                pass
        pending_groups.pop(base_name, None)

async def delayed_forward(base_name):
    group = pending_groups.get(base_name)
    if not group:
        return
        
    wait_time = WAIT_TIME
    if group["total_parts"] is not None:
        # Si se sabe el total, el timer es una seguridad por si una parte falla en subirse
        wait_time = 60

    await asyncio.sleep(wait_time)
    
    # Cuando el timer se cumple finaliza el grupo
    print(f"⏰ Timer cumplido para {base_name}. Cerrando grupo.")
    
    group = pending_groups.pop(base_name, None)
    if group:
        chat_id = group["chat_id"]
        parts = group["parts"]
        video_parts_count = len([k for k in parts.keys() if k > 0])
        total = group["total_parts"] or video_parts_count
        if total > 1:
            try:
                await app.send_message(chat_id, f"✅ **{base_name}** subido en orden ({video_parts_count}/{total} partes).")
            except:
                pass

pending_photos = {}
last_photo_for_chat = {}

def extract_code_from_text(text):
    if not text: return None
    text_upper = text.upper()
    
    # 1. Match FC2-PPV-xxxxxxx or FC2-xxxxx or similar
    match_fc2 = re.search(r'\b(FC2(?:-PPV)?-\d+)\b', text_upper)
    if match_fc2:
        return match_fc2.group(1)
        
    # 2. Match standard JAV code: letters-numbers (e.g. ABC-123, ABCD-123, ABC-0123)
    match_std = re.search(r'\b([A-Z0-9]{2,8}-\d+)\b', text_upper)
    if match_std:
        return match_std.group(1)
        
    # 3. Match without dash: letters followed by numbers (e.g. ABC123)
    match_nodash = re.search(r'\b([A-Z]{2,8})(\d{3,6})\b', text_upper)
    if match_nodash:
        return f"{match_nodash.group(1)}-{match_nodash.group(2)}"
        
    return None

@app.on_message(filters.photo)
async def handle_photo(client, message: Message):
    chat_id = message.chat.id
    code = extract_code_from_text(message.caption)
    if code:
        pending_photos[(chat_id, code)] = message
        print(f"📸 Portada registrada con código: {code} en chat {chat_id}")
    else:
        last_photo_for_chat[chat_id] = message
        print(f"📸 Portada guardada como fallback en chat {chat_id}")

@app.on_message(filters.document | filters.video)
async def handle_media(client, message: Message):
    file_name = None
    if message.document:
        file_name = message.document.file_name
    elif message.video:
        file_name = message.video.file_name

    if not file_name:
        return

    name_without_ext, _ = os.path.splitext(file_name)

    part_num = 1
    total_parts = 1
    base_name = name_without_ext

    # 1. Intentar extraer del caption (e.g. "[1/3]")
    cap_match = re.search(r'\[\s*(\d+)\s*/\s*(\d+)\s*\]', message.caption or "")
    if cap_match:
        part_num = int(cap_match.group(1))
        total_parts = int(cap_match.group(2))
        
        # Extraer base_name quitando la parte de part si existe en el archivo
        part_file_match = re.search(r'(.*?)(?:\.part[_\- ]?(\d+)|_part[_\- ]?(\d+))(.*?)$', name_without_ext, re.IGNORECASE)
        if part_file_match:
            base_name = part_file_match.group(1).strip()
    else:
        # 2. Intentar extraer del nombre del archivo (e.g. "_part1")
        part_file_match = re.search(r'(.*?)(?:\.part[_\- ]?(\d+)|_part[_\- ]?(\d+))(.*?)$', name_without_ext, re.IGNORECASE)
        if part_file_match:
            base_name = part_file_match.group(1).strip()
            part_num = int(part_file_match.group(2) or part_file_match.group(3))
            total_parts = None # No se sabe el total

    chat_id = message.chat.id
    
    print(f"📥 Recibido {file_name} -> Base: {base_name} | Parte: {part_num} | Total: {total_parts}")

    # Cancelar el timer anterior si existe
    if pending_groups[base_name]["timer"]:
        pending_groups[base_name]["timer"].cancel()

    is_first_part_seen = len(pending_groups[base_name]["parts"]) == 0

    # Guardar datos en el grupo
    pending_groups[base_name]["chat_id"] = chat_id
    pending_groups[base_name]["parts"][part_num] = message
    if total_parts is not None:
        pending_groups[base_name]["total_parts"] = total_parts

    # Si es la primera parte, asociar la foto de portada buscando por código o usando fallback
    if is_first_part_seen:
        photo_msg = None
        video_code = extract_code_from_text(base_name)
        if not video_code and message.caption:
            video_code = extract_code_from_text(message.caption)
            
        if video_code and (chat_id, video_code) in pending_photos:
            photo_msg = pending_photos.pop((chat_id, video_code))
            print(f"🎯 Portada emparejada por código ({video_code}) para: {base_name}")
        elif chat_id in last_photo_for_chat:
            photo_msg = last_photo_for_chat.pop(chat_id)
            print(f"🎯 Portada emparejada por fallback para: {base_name}")
            
        if photo_msg:
            pending_groups[base_name]["parts"][0] = photo_msg

    # Reenviar inmediatamente el grupo actualizado eliminando el anterior
    await forward_and_update_group(base_name)

    # Iniciar nuevo timer de fallback si el grupo no se completó inmediatamente
    if base_name in pending_groups:
        pending_groups[base_name]["timer"] = asyncio.create_task(
            delayed_forward(base_name)
        )

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply("🤖 **Bot Organizador Activo**\n\nSolo reenvíame archivos con nombres que contengan `part1`, `part2`, etc., o que tengan captions con formatos `[1/3]`, `[2/3]`.\n\nYo me encargaré de ordenar, borrar versiones incompletas y reenviar todo limpio con su portada.")

if __name__ == "__main__":
    print("🚀 Iniciando Bot Organizador...")
    app.run()
