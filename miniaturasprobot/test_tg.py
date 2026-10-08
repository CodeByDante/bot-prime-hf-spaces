import asyncio
from pyrogram import Client, idle
import logging

logging.basicConfig(level=logging.INFO)

API_ID = 33226415
API_HASH = "01999dae3e5348c7ab0dbcc6f7f4edc5"
BOT_TOKEN = "8798114281:AAE9M0Ux-T4VDWR8Fq6h9j0U-fLLuz3MVfM"

app = Client("test_bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message()
async def logger(client, message):
    print("MESSAGGEEEE: ", message.text)
    await message.reply(f"Hola, recibi tu mensaje: {message.text}")

async def main():
    print("Arrancando test...")
    await app.start()
    print("Esperando mensajes... manda /start o hola")
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
