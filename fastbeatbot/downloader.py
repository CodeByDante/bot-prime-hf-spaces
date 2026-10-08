# Dummy downloader module to prevent ModuleNotFoundError in old unused code
def get_all_hentaila_episodes(*args, **kwargs): return []
async def procesar_descarga(*args, **kwargs): return False
import asyncio
SEM_DOWNLOAD = asyncio.Semaphore(1)
