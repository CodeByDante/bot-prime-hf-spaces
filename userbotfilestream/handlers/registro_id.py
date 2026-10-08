import asyncio
from telethon import events
from telethon.tl.types import PeerChannel
from core.client import client
from utils.channel_resolver import load_channels, save_channels, DEFAULT_NAMES
from utils.helpers import safe_edit_status


async def procesar_registro_id(event):
    chat_id = event.chat_id
    status_msg = await event.reply("🔍 **[Bot Prime]** Iniciando `/registro_id`. Actualizando base de datos de canales específicos...")
    
    try:
        data = load_channels()
        updated_channels = []
        
        # 1. Obtener todos los diálogos actuales (canales) para buscar por nombre
        await safe_edit_status(status_msg, "🔍 **[Bot Prime]** Escaneando tus canales y chats para hacer coincidir nombres...")
        dialogs = []
        async for dialog in client.iter_dialogs():
            if dialog.is_channel and dialog.name:
                dialogs.append(dialog)
                
        # 2. Buscar coincidencias para cada uno de los canales específicos
        for key, default_name in DEFAULT_NAMES.items():
            found_dialog = None
            
            # Buscar coincidencia exacta
            for d in dialogs:
                if d.name.lower() == default_name.lower():
                    found_dialog = d
                    break
                    
            # Buscar coincidencia parcial si no hay exacta
            if not found_dialog:
                for d in dialogs:
                    if default_name.lower() in d.name.lower():
                        found_dialog = d
                        break
                        
            if found_dialog:
                clean_id = int(str(found_dialog.entity.id).replace("-100", ""))
                data[key] = {
                    "id": clean_id,
                    "name": found_dialog.name
                }
                updated_channels.append(f"• **{key}** -> '{found_dialog.name}' (ID: `{clean_id}`)")
            else:
                # Si no se encuentra por nombre actual, intentar verificar por ID previo
                if key in data and data[key].get("id"):
                    prev_id = data[key]["id"]
                    try:
                        entity = await client.get_entity(PeerChannel(channel_id=int(str(prev_id).replace("-100", ""))))
                        data[key]["name"] = entity.title
                        updated_channels.append(f"• **{key}** -> '{entity.title}' (ID previo verificado: `{prev_id}`)")
                    except Exception:
                        updated_channels.append(f"• **{key}** -> (ID previo `{prev_id}` no verificado)")
                else:
                    updated_channels.append(f"• **{key}** -> ❌ No encontrado en diálogos ni ID previo.")
                    
        # Guardar archivo JSON con los datos actualizados
        save_channels(data)
        
        report = "✅ **[Bot Prime]** Registro e identificación de canales completado:\n\n"
        report += "\n".join(updated_channels)
        
        await safe_edit_status(status_msg, report)
        await asyncio.sleep(15)
        await client.delete_messages(chat_id, [event.id, status_msg.id])
        
    except Exception as e:
        try:
            await safe_edit_status(status_msg, f"❌ **[Bot Prime]** Error durante el registro de IDs: {e}")
            await asyncio.sleep(8)
            await client.delete_messages(chat_id, [event.id, status_msg.id])
        except Exception:
            pass
