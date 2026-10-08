import os
import math
import random
import time
import asyncio
import logging
from typing import List
from pyrogram import Client
from pyrogram.types import Message
from PIL import Image

logger = logging.getLogger(__name__)

# Temporary storage for downloaded collage images
COLLAGE_DIR = "downloads/collage_tmp"
os.makedirs(COLLAGE_DIR, exist_ok=True)

async def create_and_send_collage(client: Client, chat_id: int, status_msg: Message, file_ids: List[str]):
    """
    Downloads a list of telegram file_ids, combines them into a grid collage,
    and sends the final image back to the user.
    """
    
    if not file_ids:
        await status_msg.edit_text("❌ No se recibieron imágenes válidas.")
        return
        
    await status_msg.edit_text(f"📥 Descargando {len(file_ids)} imágenes...")
    
    downloaded_paths = []
    
    try:
        # 1. Download all images
        for i, f_id in enumerate(file_ids):
            try:
                # Use a unique name for each
                tmp_path = os.path.join(COLLAGE_DIR, f"img_{chat_id}_{int(time.time())}_{i}.jpg")
                file_path = await client.download_media(f_id, file_name=tmp_path)
                if file_path and os.path.exists(file_path):
                    downloaded_paths.append(file_path)
            except Exception as e:
                logger.error(f"Error downloading image for collage {f_id}: {e}")
                
        if not downloaded_paths:
            await status_msg.edit_text("❌ Hubo un error al descargar las imágenes de Telegram.")
            return
            
        await status_msg.edit_text("⚙️ Generando Collage...")
        
        # 2. Open all images with PIL
        images = []
        for path in downloaded_paths:
            try:
                img = Image.open(path)
                # Convert to RGB to avoid issues with transparency
                if img.mode in ('RGBA', 'P'): 
                    img = img.convert('RGB')
                images.append(img)
            except Exception as e:
                logger.error(f"Error opening image {path}: {e}")
                
        if not images:
            await status_msg.edit_text("❌ Las imágenes descargadas están corruptas.")
            return
            
        # 3. Calculate Layout (Smart Justified Grid - No Cropping)
        num_images = len(images)
        
        # Determinar columnas basadas en la cantidad
        if num_images <= 2:
            cols = num_images
        elif num_images <= 4:
            cols = 2
        elif num_images <= 6:
            cols = 3
        else:
            cols = math.ceil(math.sqrt(num_images))
            
        # Target total width of the collage
        W = 1600
        
        rows_list = []
        row_heights = []
        
        # Dividir imágenes en filas
        for i in range(0, num_images, cols):
            row_imgs = images[i:i+cols]
            
            # Aspect ratio = ancho / alto
            aspect_ratios = [img.width / img.height for img in row_imgs]
            sum_ratios = sum(aspect_ratios)
            
            # Calcular la altura perfecta para esta fila para que llene el ancho total (W)
            row_h = int(W / sum_ratios)
            
            # Prevenir estiramiento extremo en imagenes verticales sueltas en la última fila
            max_allowed_h = int(1.5 * (W / len(row_imgs)))
            if row_h > max_allowed_h:
                row_h = max_allowed_h
                
            row_heights.append(row_h)
            
            # Redimensionar imagenes
            resized_row = []
            current_w = 0
            for j, img in enumerate(row_imgs):
                # La ultima imagen llena el espacio residual EXACTO del ancho (salvo si se capeo en altura)
                if j == len(row_imgs) - 1 and row_h < max_allowed_h:
                    new_w = W - current_w
                else:
                    new_w = int(row_h * (img.width / img.height))
                    current_w += new_w
                    
                resized = img.resize((new_w, row_h), Image.Resampling.LANCZOS)
                resized_row.append(resized)
                
            rows_list.append(resized_row)
            
        # Crear lienzo en blanco
        total_h = sum(row_heights)
        collage_img = Image.new('RGB', (W, total_h), color=(0, 0, 0))
        
        # Pegar imagenes (centrando la ultima fila si quedó pequeña)
        current_y = 0
        for i, row in enumerate(rows_list):
            current_x = 0
            row_h = row_heights[i]
            
            row_w = sum([img.width for img in row])
            if row_w < W:
                current_x = (W - row_w) // 2
                
            for img in row:
                collage_img.paste(img, (current_x, current_y))
                current_x += img.width
            current_y += row_h
            
        # 4. Save Collage
        output_path = os.path.join(COLLAGE_DIR, f"collage_{chat_id}_{int(time.time())}.jpg")
        
        # Guardar en executor para no bloquear el loop
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: collage_img.save(output_path, quality=90))
        
        # 5. Send Collage
        await status_msg.edit_text("📤 Enviando collage terminado...")
        try:
            await client.send_photo(
                chat_id,
                photo=output_path,
                caption="🖼 **¡Aquí tienes tu Tira Vertical!**"
            )
        except Exception as e_send:
            err_str = str(e_send).lower()
            if "dimension" in err_str or "size" in err_str:
                await status_msg.edit_text("⚠️ El archivo es demasiado largo para Telegram, enviando como Documento...")
                await client.send_document(
                    chat_id,
                    document=output_path,
                    caption="🖼 **¡Aquí tienes tu Tira Vertical en alta calidad!**\n(Enviado como archivo porque es muy largo)"
                )
            else:
                raise e_send
        
        # Cleanup final msg
        await status_msg.delete()
        
    except Exception as e:
        logger.error(f"Error fatal generando collage: {e}")
        await status_msg.edit_text(f"❌ Ocurrió un error al crear el collage: {e}")
    finally:
        # 6. Cleanup local files
        for path in downloaded_paths:
             if os.path.exists(path):
                 try: os.remove(path)
                 except: pass
                 
        if 'output_path' in locals() and os.path.exists(output_path):
             try: os.remove(output_path)
             except: pass
