from telethon import TelegramClient, events

api_id = 33226415
api_hash = '01999dae3e5348c7ab0dbcc6f7f4edc5'
bot_token = '8798114281:AAE9M0Ux-T4VDWR8Fq6h9j0U-fLLuz3MVfM'

client = TelegramClient('telethon_session', api_id, api_hash)

@client.on(events.NewMessage())
async def handler(event):
    print("MESSAGGEEEE: ", event.message.message)
    await event.reply(f"Hola telethon, recibi tu mensaje: {event.message.message}")

print("Iniciando telethon...")
client.start(bot_token=bot_token)
client.run_until_disconnected()
