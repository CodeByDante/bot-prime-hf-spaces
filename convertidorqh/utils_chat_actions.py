
from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def chat_action_loop(client, chat_id, action, delay=4):
    """
    Desactivado por petición del usuario para evitar bloqueos de FloodWait
    por mensajes de "SetTyping" (escribiendo, subiendo video, etc).
    """
    try:
        yield
    finally:
        pass
