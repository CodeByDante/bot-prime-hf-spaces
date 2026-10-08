import asyncio
import os
import subprocess
from utils import descargar_galeria, GALLERY_DL_EXEC

URL = "https://www.tiktok.com/@entitydante/photo/7557919556937731383"

async def test_gallery():
    print(f"Testing URL with gallery-dl: {URL}")
    print(f"Exec: {GALLERY_DL_EXEC}")
    
    try:
        files, tmp, meta = descargar_galeria(URL)
        print(f"Files: {files}")
        print(f"Meta: {meta}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_gallery())
