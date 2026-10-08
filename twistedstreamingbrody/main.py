import os
import asyncio
from telethon import events
from core import client, user_modes, active_tasks

import bot_subidor
import bot_editor
import bot_buscador

@client.on(events.NewMessage(pattern='^/start$'))
async def handle_start(event):
    mode = user_modes.get(event.chat_id)
    if not mode:
        await event.respond("👋 **Bienvenido a Twisted Streaming Brody**\n\nPor favor elige el bot que deseas usar:\n- /bot_subidor : Para subir películas y series.\n- /bot_editor : Para editar la base de datos.\n- /bot_buscador : Para buscar y entregar videos.")
    elif mode == 'buscador':
        await send_buscador_welcome(event)
    elif mode == 'editor':
        await set_editor(event)

async def send_buscador_welcome(event):
    from telethon.tl.types import KeyboardButtonWebView
    from telethon import Button
    chat_id = getattr(event, 'chat_id', getattr(getattr(event, 'message', None), 'chat_id', None))
    
    # Eliminar cualquier teclado de respuesta previo que haya quedado atascado
    try:
        tmp = await client.send_message(chat_id, "🔄 Actualizando teclado...", buttons=Button.clear())
        await tmp.delete()
    except: pass
    
    photos = await client.get_profile_photos('me', limit=1)
    msg = "🔍 **Modo Buscador Activado**\n\nBienvenido al Bot Buscador. Escribe el nombre de la película o serie que buscas, o abre la Mini App debajo."
    
    btn_webapp = KeyboardButtonWebView(text="🍿 Twisted Streaming Brody", url="https://codebybrody-twistedstreamingbrody.hf.space")
    
    if photos:
        await client.send_file(chat_id, photos[0], caption=msg, buttons=[[btn_webapp]])
    else:
        await client.send_message(chat_id, msg, buttons=[[btn_webapp]])

@client.on(events.NewMessage(pattern='^/bot_subidor$'))
async def set_subidor(event):
    chat_id = event.chat_id
    user_modes[chat_id] = 'subidor'
    if chat_id in active_tasks:
        for t in active_tasks[chat_id]:
            t.cancel()
        del active_tasks[chat_id]
        
    photos = await client.get_profile_photos('me', limit=1)
    msg = "📁 **Modo Subidor Activado**\n\nBienvenido al Bot Subidor. Aquí podrás registrar tus películas y series. Usa /start para ver las opciones."
    if photos:
        await client.send_file(chat_id, photos[0], caption=msg)
    else:
        await event.respond(msg)

@client.on(events.NewMessage(pattern='^/bot_editor$'))
async def set_editor(event):
    chat_id = event.chat_id
    user_modes[chat_id] = 'editor'
    if chat_id in active_tasks:
        for t in active_tasks[chat_id]:
            t.cancel()
        del active_tasks[chat_id]
        
    from telethon.tl.types import KeyboardButtonWebView
    from telethon import Button
    photos = await client.get_profile_photos('me', limit=1)
    msg = "🛠️ **Modo Editor Activado**\n\nBienvenido al Bot Editor. Envíame el ID del contenido que deseas editar o usa las opciones que aparecen debajo."
    
    # Limpiar cualquier teclado previo por si acaso
    try:
        tmp = await client.send_message(chat_id, "🔄 Actualizando teclado...", buttons=Button.clear())
        await tmp.delete()
    except: pass
    
    btn_webapp = KeyboardButtonWebView(text="🍿 Twisted Streaming Brody", url="https://codebybrody-twistedstreamingbrody.hf.space")
    
    if photos:
        await client.send_file(chat_id, photos[0], caption=msg, buttons=[[btn_webapp]])
    else:
        await client.send_message(chat_id, msg, buttons=[[btn_webapp]])
    
    # Iniciar ciclo del editor
    import asyncio
    current_task = asyncio.current_task()
    if chat_id not in active_tasks:
        active_tasks[chat_id] = []
    active_tasks[chat_id].append(current_task)
    try:
        await bot_editor.handle_editor_mode(event)
    finally:
        if current_task in active_tasks.get(chat_id, []):
            active_tasks[chat_id].remove(current_task)

@client.on(events.NewMessage(pattern='^/bot_buscador$'))
async def set_buscador(event):
    chat_id = event.chat_id
    user_modes[chat_id] = 'buscador'
    if chat_id in active_tasks:
        for t in active_tasks[chat_id]:
            t.cancel()
        del active_tasks[chat_id]
        
    await send_buscador_welcome(event)

print("Iniciando el Bot con Modos Separados...")
client.start(bot_token=os.getenv('TELEGRAM_BOT_TOKEN'))

async def set_commands():
    from telethon.tl.functions.bots import SetBotCommandsRequest
    from telethon.tl.types import BotCommand, BotCommandScopeDefault
    try:
        await client(SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code='',
            commands=[
                BotCommand(command="start", description="Elegir Bot / Volver al inicio"),
                BotCommand(command="bot_subidor", description="Activar Bot Subidor"),
                BotCommand(command="bot_editor", description="Activar Bot Editor"),
                BotCommand(command="bot_buscador", description="Activar Bot Buscador"),
                BotCommand(command="app", description="Abrir la Mini App de Catálogo"),
                BotCommand(command="setting", description="Configuración (Modo Buscador)"),
                BotCommand(command="cancelar", description="Cancelar proceso actual")
            ]
        ))
        print("📁 Menú nativo de comandos (/) actualizado exitosamente.")
    except Exception as e:
        print(f"Error al configurar comandos: {e}")

client.loop.run_until_complete(set_commands())
client.run_until_disconnected()
