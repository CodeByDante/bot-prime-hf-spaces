import re
from aiohttp import web
from telethon.tl.types import InputDocumentFileLocation
from telethon.tl.functions.upload import GetFileRequest
from telethon.errors import FloodWaitError
import asyncio

# Variables globales para el streaming local
active_documents = {}
active_client = None

# --- SERVIDOR PROXY HTTP PARA STREAMING ---
async def download_chunk_aligned(client, document, start, length):
    total_size = document.size
    chunk_size = 524288  # 512KB (máximo permitido por Telegram)
    
    end = min(start + length - 1, total_size - 1)
    if start > end:
        return b""
        
    block_start = start // chunk_size
    block_end = end // chunk_size
    
    location = InputDocumentFileLocation(
        id=document.id,
        access_hash=document.access_hash,
        file_reference=document.file_reference,
        thumb_size=""
    )
    
    combined_data = b""
    for block in range(block_start, block_end + 1):
        offset = block * chunk_size
        limit = chunk_size
        if offset + limit > total_size:
            remaining = total_size - offset
            limit = 4096
            while limit < remaining and limit < chunk_size:
                limit *= 2
            
        while True:
            try:
                result = await client(GetFileRequest(
                    location=location,
                    offset=offset,
                    limit=limit
                ))
                combined_data += result.bytes
                break
            except FloodWaitError as e:
                print(f"[MTProto Warning] FloodWaitError detectado. Esperando {e.seconds} segundos...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                print(f"[MTProto Error] GetFileRequest falló: {e}")
                return b""
            
    slice_start = start - (block_start * chunk_size)
    slice_end = slice_start + length
    
    return combined_data[slice_start:slice_end]

async def handle_stream(request):
    global active_client
    if not active_client:
        return web.Response(status=404, text="No hay cliente activo.")
        
    doc_id_str = request.query.get("id")
    if not doc_id_str:
        return web.Response(status=404, text="Falta el ID del video.")
        
    try:
        doc_id = int(doc_id_str)
    except ValueError:
        return web.Response(status=400, text="ID de video inválido.")
        
    document = active_documents.get(doc_id)
    if not document:
        return web.Response(status=404, text="Video no encontrado o inactivo.")

    total_size = document.size
    range_header = request.headers.get("Range")
    
    start = 0
    end = total_size - 1

    if range_header:
        match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if match:
            start = int(match.group(1))
            if match.group(2):
                end = int(match.group(2))

    response = web.StreamResponse(
        status=206,
        reason="Partial Content",
        headers={
            "Content-Range": f"bytes {start}-{end}/{total_size}",
            "Content-Length": str(end - start + 1),
            "Content-Type": "video/mp4",
            "Accept-Ranges": "bytes"
        }
    )

    await response.prepare(request)

    try:
        chunk_size = 128 * 1024
        current = start
        while current <= end:
            length = min(chunk_size, end - current + 1)
            chunk = await download_chunk_aligned(active_client, document, current, length)
            if not chunk:
                break
            await response.write(chunk)
            current += len(chunk)
    except Exception:
        pass
    finally:
        try:
            await response.write_eof()
        except Exception:
            pass

    return response

_proxy_runner = None

async def start_proxy_server(port=8080):
    global _proxy_runner
    if _proxy_runner is not None:
        return _proxy_runner
        
    app = web.Application()
    app.router.add_get("/stream", handle_stream)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    
    try:
        await site.start()
        _proxy_runner = runner
        return runner
    except OSError as e:
        # Ignore if address is already in use
        if e.errno == 10048 or e.errno == 98:
            pass
        else:
            raise e
            
    return None
