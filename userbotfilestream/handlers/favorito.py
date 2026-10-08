import asyncio
from telethon import events

async def procesar_comando_f(event):
    if not event.is_reply:
        await event.edit("Debes responder a un mensaje con el comando /f para añadir #favorito.")
        await asyncio.sleep(3)
        await event.delete()
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg:
        await event.edit("No se pudo obtener el mensaje al que respondiste.")
        await asyncio.sleep(3)
        await event.delete()
        return

    try:
        # Delete the command immediately
        await event.delete()
    except Exception:
        pass

    text = reply_msg.text or ""
    if "#favorito" not in text:
        if text:
            new_text = text + "\n\n#favorito"
        else:
            new_text = "#favorito"
        
        try:
            await reply_msg.edit(new_text)
        except Exception as e:
            print(f"Error al editar mensaje para añadir #favorito: {e}")
