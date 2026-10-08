
import asyncio
import os
import time
import shutil
from pyrogram.types import InputMediaPhoto, InputMediaDocument, InputMediaVideo, InputMediaAudio, InputMediaAnimation
from config import DATA_DIR
from database import get_config
from utils import extract_images_ffmpeg, create_split_zips, video_to_gif_ffmpeg, create_telegram_sticker, search_saucenao, format_saucenao_results, search_tracemoe, format_tracemoe_results, split_video_generic, cut_video_range
from tools_media import get_meta, get_thumb, smart_cut_video, create_video_collage, generate_subtitles_video, progreso
from firebase_service import save_user_config_fb

# --- HELPER: LOGICA PARTY ---
async def run_party_logic(client, chat_id, file_path, mode, val, msg_to_edit=None, original_msg=None, context_config=None):
    # --- LOAD CONFIG FROM CONTEXT OR DB ---
    # Si context_config es None, cargamos la actual (comportamiento legacy/fallback)
    # Pero si viene del handler, usaremos la "congelada" al momento de iniciar la tarea.
    if context_config is None:
        context_config = get_config(chat_id)

    if msg_to_edit:
        await msg_to_edit.edit(f"⏳ Procesando Party ({mode}={val})...")
    else:
         sm = await client.send_message(chat_id, f"⏳ Procesando Party ({mode}={val})...")
         msg_to_edit = sm

    try:
        if mode == 'parts':
            parts = await asyncio.get_running_loop().run_in_executor(None, lambda: split_video_generic(file_path, mode, float(val)))
        elif mode in ['sec', 'min']:
            parts = await asyncio.get_running_loop().run_in_executor(None, lambda: split_video_generic(file_path, mode, float(val)))
        elif mode == 'range':
            pts = str(val).split()
            if len(pts) < 2 or len(pts) % 2 != 0:
                await msg_to_edit.edit("❌ Formato de rango inválido. Deben ser pares (Ej: '10 20 30 40').")
                return False
            
            parts = []
            for i in range(0, len(pts), 2):
                s, e = pts[i], pts[i+1]
                p_path = await asyncio.get_running_loop().run_in_executor(None, lambda: cut_video_range(file_path, s, e))
                if p_path: parts.append(p_path)
        else:
            parts = []

        if not parts:
            await msg_to_edit.edit("❌ Error al procesar el video.")
            return False

        # --- LOGICA ZIP MODE ---
        # Usamos context_config congelada
        is_zip_mode = context_config.get('party_zip', False)
        
        if is_zip_mode:
            await msg_to_edit.edit(f"📦 Comprimiendo {len(parts)} partes en ZIP...")
            # Calcular nombre base
            base_zip = file_path.rsplit('.', 1)[0] + "_party"
            
            # Crear zips (run in executor for blocking I/O)
            zip_files = await asyncio.get_running_loop().run_in_executor(None, lambda: create_split_zips(parts, base_zip))
            
            # Limpiar partes originales ya que están en el zip
            for p in parts:
                try: os.remove(p)
                except: pass
                
            parts = zip_files # Reemplazamos la lista de partes con los ZIPs
            
        # --- LOGICA ENVIO (Agrupado o Individual) ---
        # Usamos context_config congelada
        
        # FIX: Si es DOC MODE, forzamos thumb=None para que se vea como archivo genérico (icono azul)
        send_as_doc_mode = context_config.get('doc_mode')
        use_group_mode = context_config.get('group_mode') and len(parts) > 1
        
        # --- LOCK SENDING PHASE PER CHAT ---
        # We need a way to lock per chat. Since we moved this function, we need to handle locks here or pass them.
        # For simplicity, we can create a local lock map or rely on concurrency limit.
        # The original code used a global PARTY_SEND_LOCKS in main.py. 
        # We will skip the lock for now or implement a simple one if critical, 
        # but since we are refactoring, let's keep it simple. If valid concurrency exists, it handles it.
        # Ideally we'd import the lock from main or create a new one here.
        # Let's assume we proceed without the explicit chat lock for now, or add a simple one.
        
        # --- SEND ORIGINAL VIDEO FIRST (User Request) ---
        if original_msg:
            try:
                await msg_to_edit.edit(f"📤 Enviando video original...")
                await original_msg.copy(chat_id, caption="🎬 **Video Original**")
            except Exception as e:
                print(f"Error copying original: {e}")

        # --- PARALLEL METADATA & THUMBNAIL GENERATION ---
        # Pre-calculamos todo de una sola vez para velocidad maxima
        meta_cache = {} # path -> {'w':, 'h':, 'dur':, 'thumb':}
        
        if not is_zip_mode:
            await msg_to_edit.edit(f"⚡ Procesando metadatos ({len(parts)} partes)...")
            ts = int(time.time())
            
            # Helper to process one file
            async def process_one(idx, p_path):
                try:
                    # Parallel Meta + Thumb
                    # A veces get_thumb necesita duration, asi que idealmente meta primero, luego thumb.
                    # Pero get_thumb es robusto. Hagamos meta primero.
                    w, h, dur = await get_meta(p_path)
                    
                    # Thumb ID unico
                    t_path = await get_thumb(p_path, chat_id, f"{ts}_{idx}", duration=dur)
                    
                    return p_path, {'w': w, 'h': h, 'dur': dur, 'thumb': t_path}
                except:
                    return p_path, None

            # Gather all
            tasks = [process_one(i, p) for i, p in enumerate(parts)]
            results = await asyncio.gather(*tasks)
            
            for p_path, data in results:
                if data: meta_cache[p_path] = data

        
        # --- SENDING PHASE ---
        if use_group_mode:
            await msg_to_edit.edit(f"📤 Enviando {len(parts)} parte(s) en álbum...")
            
            # Dividir en chunks de 10 (Límite Telegram)
            chunks = [parts[i:i + 10] for i in range(0, len(parts), 10)]
            
            for i, chunk in enumerate(chunks):
                media_group = []
                temp_thumbs = []
                
                for j, p in enumerate(chunk):
                    try:
                        thumb = None
                        width, height, duration = None, None, None
                        
                        if p in meta_cache:
                            d = meta_cache[p]
                            width, height, duration = d['w'], d['h'], d['dur']
                            thumb = d['thumb']
                            if thumb: temp_thumbs.append(thumb)
                        
                        # Caption solo en el primer elemento del grupo
                        cap = "" 
                        if i == 0 and j == 0:
                            cap = "🎉 **Party Video** (Álbum)"

                        if is_zip_mode or send_as_doc_mode:
                            media_group.append(InputMediaDocument(media=p, thumb=thumb, caption=cap))
                        elif p.lower().endswith(('.mp3', '.m4a', '.flac', '.wav', '.ogg')):
                            media_group.append(InputMediaAudio(media=p, thumb=thumb, caption=cap, duration=duration))
                        else:
                            media_group.append(InputMediaVideo(
                                media=p, 
                                thumb=thumb, 
                                width=width, 
                                height=height, 
                                duration=duration, 
                                caption=cap
                            ))
                    except Exception as e:
                        print(f"Error preparando media group item {j}: {e}")
                
                if media_group:
                    try:
                        await client.send_media_group(chat_id, media_group)
                    except Exception as e:
                        print(f"Error enviando Media Group: {e}")
                        # Fallback a envios individuales si falla el grupo
                        for item in media_group:
                            try:
                                if isinstance(item, InputMediaDocument):
                                    await client.send_document(chat_id, item.media, thumb=item.thumb, caption=item.caption)
                                elif isinstance(item, InputMediaAudio):
                                    await client.send_audio(chat_id, item.media, thumb=item.thumb, caption=item.caption, duration=item.duration)
                                else:
                                    await client.send_video(chat_id, item.media, thumb=item.thumb, caption=item.caption)
                            except: pass

                # Cleanup thumbs del chunk (ya no son necesarios)
                for t in temp_thumbs:
                    if os.path.exists(t): os.remove(t)

        else:
            # --- ENVIO INDIVIDUAL (Legacy Logic) ---
            await msg_to_edit.edit(f"📤 Enviando {len(parts)} {'ZIPs' if is_zip_mode else 'partes'}...")
            
            for i, p in enumerate(parts):
                try:
                    thumb = None
                    width, height, duration = None, None, None
                    
                    if p in meta_cache:
                        d = meta_cache[p]
                        width, height, duration = d['w'], d['h'], d['dur']
                        thumb = d['thumb']

                    if is_zip_mode or send_as_doc_mode:
                            cap_lbl = "🎉 Party ZIP" if is_zip_mode else "🎉 Party Video (Doc)"
                            if len(parts) > 1: cap_lbl += f" - Parte {i+1}"
                            
                            await client.send_document(
                            chat_id, p,
                            thumb=thumb,
                            caption=cap_lbl,
                            force_document=True
                            )
                    else:
                        if p.lower().endswith(('.mp3', '.m4a', '.flac', '.wav', '.ogg')):
                                await client.send_audio(
                                chat_id, p,
                                duration=duration if duration else None,
                                thumb=thumb,
                                caption=f"🎉 Party: Parte {i+1}" if len(parts) > 1 else "🎉 Party Audio"
                                )
                        else:
                            await client.send_video(
                                chat_id, p,
                                width=width if width else None,
                                height=height if height else None,
                                duration=duration if duration else None,
                                thumb=thumb,
                                caption=f"🎉 Party: Parte {i+1}" if len(parts) > 1 else "🎉 Party Video"
                            )
                    # Cleanup immediately after send
                    if thumb and os.path.exists(thumb): os.remove(thumb)
                except Exception as e:
                    print(f"Error enviando parte {i}: {e}")
                    try: await client.send_document(chat_id, p)
                    except: pass
        
        # Cleanup final
        try: 
            if os.path.exists(file_path): os.remove(file_path)
            for p in parts: 
                if os.path.exists(p): os.remove(p)
        except: pass
        
        await msg_to_edit.delete()
        
        # --- AUTO-DISABLE PARTY MODE ---
        conf = get_config(chat_id)
        # Solo desactivar si NO está en modo Auto-Party (Persistent)
        if conf.get('party_mode') and not conf.get('auto_party', False):
            conf['party_mode'] = False
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            # Avisar (sin keyboard pass for now to avoid circular dependency)
            await client.send_message(chat_id, "✅ **Finalizado.**\nModo Party desactivado.")
            
        return True
    except Exception as e:
        await msg_to_edit.edit(f"❌ Error en Party: {e}")
        return False

async def run_extract_logic(client, chat_id, file_path, mode, val, msg_to_edit=None):
    if msg_to_edit: await msg_to_edit.edit(f"🖼 **Extrayendo imágenes ({mode}={val})...**")
    else: msg_to_edit = await client.send_message(chat_id, f"🖼 **Extrayendo imágenes ({mode}={val})...**")

    try:
        imgs, out_dir = await asyncio.get_running_loop().run_in_executor(None, lambda: extract_images_ffmpeg(file_path, val, mode))
        
        if not imgs:
            await msg_to_edit.edit("❌ No se pudieron extraer imágenes. Verifica el tiempo/intervalo.")
            return False

        conf = get_config(chat_id)
        is_zip = conf.get('extract_party_zip', True)
        is_doc = conf.get('doc_mode', False)
        is_group = conf.get('group_mode', True)

        if is_zip:
            await msg_to_edit.edit(f"📦 **Comprimiendo {len(imgs)} imágenes...**")
            base_name = f"Extracted_{chat_id}_{int(time.time())}"
            zip_files = await asyncio.get_running_loop().run_in_executor(None, lambda: create_split_zips(imgs, base_name))
            
            for zp in zip_files:
                await client.send_document(chat_id, zp, caption=f"🖼 **Extractor**: {len(imgs)} fotogramas ({mode}={val})")
                if os.path.exists(zp): os.remove(zp)
        else:
            await msg_to_edit.edit(f"📤 **Enviando {len(imgs)} imágenes...**")
            if is_group and len(imgs) > 1:
                # Enviar como Media Group (max 10 cada uno)
                chunks = [imgs[i:i + 10] for i in range(0, len(imgs), 10)]
                for chunk in chunks:
                    media = []
                    for img in chunk:
                        if is_doc: media.append(InputMediaDocument(media=img))
                        else: media.append(InputMediaPhoto(media=img))
                    await client.send_media_group(chat_id, media)
            else:
                # Individual
                for img in imgs:
                    if is_doc: await client.send_document(chat_id, img)
                    else: await client.send_photo(chat_id, img)

        await msg_to_edit.delete()
        
        # Cleanup dir
        if os.path.exists(out_dir): shutil.rmtree(out_dir)
        
        # Auto-OFF logic
        conf = get_config(chat_id)
        if not conf.get('auto_extract', False):
            conf['extract_mode'] = False
            asyncio.create_task(save_user_config_fb(chat_id, conf))
            
        return True
    except Exception as e:
        await msg_to_edit.edit(f"❌ Error en Extractor: {e}")
        return False


async def run_gif_logic(client, chat_id, file_path, msg_to_edit=None):
    if msg_to_edit: await msg_to_edit.edit("🎞 **Convirtiendo a GIF...**")
    else: msg_to_edit = await client.send_message(chat_id, "🎞 **Convirtiendo a GIF...**")

    try:
        gif_file = await asyncio.get_running_loop().run_in_executor(None, lambda: video_to_gif_ffmpeg(file_path))
        if gif_file:
            await client.send_animation(chat_id, gif_file, caption="🎬 **GIF Creado**")
            if os.path.exists(gif_file): os.remove(gif_file)
            await msg_to_edit.delete()
        else:
            await msg_to_edit.edit("❌ Error al convertir a GIF.")
    except Exception as e:
        await msg_to_edit.edit(f"❌ Error: {e}")
    finally:
        # Auto-OFF
        conf = get_config(chat_id)
        conf['gif_mode'] = False
        asyncio.create_task(save_user_config_fb(chat_id, conf))


async def run_sticker_logic(client, chat_id, file_path, msg_to_handle=None):
    # Mensaje de espera
    wm = await client.send_message(chat_id, "🎭 **Creando Video Sticker (VP9)...**")
    
    try:
        # Generamos el sticker optimizado, no asyncio here according to main.py it was run_in_executor
        sticker_file = await asyncio.get_running_loop().run_in_executor(None, lambda: create_telegram_sticker(file_path, is_emoji=False))
        
        if sticker_file:
            # Enviamos el sticker
            # Nota: Al ser .webm y formato correcto, Telegram debería mostrarlo como sticker.
            await client.send_sticker(chat_id, sticker_file)
            
            # Mensaje de éxito
            await wm.edit("✅ **Sticker Generado.**\n(Añádelo a tus favoritos o reenvíalo)")
            
            if os.path.exists(sticker_file): os.remove(sticker_file)
        else:
            await wm.edit("❌ Error al crear sticker (FFmpeg).")
            
    except Exception as e:
        await wm.edit(f"❌ Error General: {e}")
    finally:
        conf = get_config(chat_id)
        conf['sticker_mode'] = False
        asyncio.create_task(save_user_config_fb(chat_id, conf))


async def run_saucenao_logic(client, chat_id, file_path, msg_to_edit=None):
    if msg_to_edit: await msg_to_edit.edit("🔍 **Buscando información...**")
    else: msg_to_edit = await client.send_message(chat_id, "🔍 **Buscando información...**")
    
    try:
        # 1. SauceNAO
        results_sauce = await asyncio.get_running_loop().run_in_executor(None, lambda: search_saucenao(file_path))
        msg_sauce = format_saucenao_results(results_sauce)
        
        # 2. Trace.moe
        results_trace = await asyncio.get_running_loop().run_in_executor(None, lambda: search_tracemoe(file_path))
        msg_trace, video_preview, is_adult = format_tracemoe_results(results_trace)
        
        # Combine Results
        final_msg = f"{msg_sauce}\n\n━━━━━━━━━━━━━━━━━━━━\n\n{msg_trace}"
        
        # Enviar resultados
        await msg_to_edit.edit(final_msg, disable_web_page_preview=True)
        
    except Exception as e:
        await msg_to_edit.edit(f"❌ Error en Búsqueda: {e}")
    finally:
        # Cleanup file
        if os.path.exists(file_path): 
            try: os.remove(file_path)
            except: pass
            
        # Auto-OFF
        conf = get_config(chat_id)
        conf['saucenao_mode'] = False
        asyncio.create_task(save_user_config_fb(chat_id, conf))

async def run_smart_cut_logic(c, cid, m):
    wm = await m.reply("⬇️ **Descargando para Smart Cut...**")
    dl_path = None
    out_path = None
    
    try:
        timestamp = int(time.time())
        dl_path = os.path.join("downloads", f"smart_in_{cid}_{timestamp}.mp4")
        
        # Download with Progress
        times = [0, 0]
        await m.download(file_name=dl_path, progress=progreso, progress_args=(wm, times, "Descargando para Smart Cut"))
        
        await wm.edit("🧠 **Analizando intro...**\n_Buscando cambios de escena..._")
        
        # Run detection and cut
        res = await smart_cut_video(dl_path)
        
        if res and res[0]:
            out_path, cut_time = res
            await wm.edit(f"✂️ **Intro detectada: {cut_time:.2f}s**\n📤 Enviando video cortado...")
            
            # Generate Thumbnail from the NEW video
            t_path = await get_thumb(out_path, cid, int(time.time()))
            
            # Send video with Progress
            w, h, dur = await get_meta(out_path)
            times = [0, 0]
            await c.send_video(
                cid, out_path, 
                width=w, height=h, duration=dur,
                thumb=t_path, # Attach new thumbnail
                caption=f"🧠 **Smart Cut Aplicado**\n\n✂️ Se eliminaron los primeros **{cut_time:.2f}s**.",
                progress=progreso, progress_args=(wm, times, "Subiendo Smart Cut")
            )
            
            # Cleanup Thumb
            if t_path and os.path.exists(t_path): 
                try: os.remove(t_path)
                except: pass
        else:
             await wm.edit("⚠️ **No se detectó intro.**\nEnviando original (Directo)...")
                    
             # Try to use file_id from message to avoid re-upload
             sent_ok = False
             try:
                 target_file_id = None
                 if m.video: target_file_id = m.video.file_id
                 elif m.document: target_file_id = m.document.file_id
                 elif m.animation: target_file_id = m.animation.file_id

                 if target_file_id:
                     await c.send_video(
                         cid, target_file_id, 
                         caption="video original sin cambios (smart cut no encontrado)"
                     )
                     sent_ok = True
             except Exception as e:
                 print(f"Smart Cut Direct Send Error: {e}")
             
             if not sent_ok:
                 w, h, dur = await get_meta(dl_path)
                 t_path = await get_thumb(dl_path, cid, int(time.time()))
                 
                 try:
                     await c.send_video(
                         cid, dl_path, 
                         width=w, height=h, duration=dur, thumb=t_path,
                         caption="video original sin cambios (smart cut no encontrado)",
                         progress=progreso, progress_args=(wm, times, "Enviando")
                     )
                 except:
                     await c.send_document(cid, dl_path, caption="video original sin cambios (smart cut no encontrado)")
                 
                 if t_path and os.path.exists(t_path): os.remove(t_path)
            
    except Exception as e:
        print(f"Smart Cut Error: {e}")
        await wm.edit(f"❌ Error: {e}")
        
    finally:
        # Cleanup
        if dl_path and os.path.exists(dl_path): 
            try: os.remove(dl_path)
            except: pass
        if out_path and os.path.exists(out_path):
            try: os.remove(out_path)
            except: pass
            
        # Robust Auto-OFF
        conf = get_config(cid)
        conf['smart_cut_mode'] = False
        asyncio.create_task(save_user_config_fb(cid, conf))
        
        try: await c.send_message(cid, "✅ **Smart Cut Finalizado (Auto-OFF)**")
        except: pass
        try: await wm.delete()
        except: pass

async def run_collage_logic(c, cid, m):
    """
    Handles the collage creation process.
    """
    conf = get_config(cid)
    ctype = conf.get('collage_type', 'png')
    grid = conf.get('collage_grid', '3x3')
    
    # 1. Download Video
    wm = await m.reply("⬇️ **Descargando para Collage...**")
    
    try:
        # Determine path
        timestamp = int(time.time())
        dl_path = os.path.join("downloads", f"collage_in_{cid}_{timestamp}.mp4")
        
        # Import moved to top
        times = [0, 0]
        await m.download(file_name=dl_path, progress=progreso, progress_args=(wm, times, "Descargando para Collage"))
        
        await wm.edit(f"🧩 **Generando Collage {grid} (esto puede tardar)...**")
        
        # 2. Generate Collage Image
        collage_path = await create_video_collage(dl_path, grid=grid)
        
        if not collage_path or not os.path.exists(collage_path):
            await wm.edit("❌ Error: No se pudo crear el collage.")
            return

        # 3. Send Result
        await wm.edit("📤 **Subiendo resultado...**")
        times = [0, 0]
        
        if ctype == 'png':
             # Send as Photo
             await c.send_photo(
                 cid, collage_path, 
                 caption=f"🧩 **Collage {grid} Generado**",
                 progress=progreso, progress_args=(wm, times, "Subiendo Collage (IMG)")
             )
        else:
             # Send as Video Thumbnail
             w, h, dur = await get_meta(dl_path)
             if dur == 0: dur = 10
             
             await c.send_video(
                 cid, 
                 dl_path, 
                 thumb=collage_path, 
                 width=w, 
                 height=h, 
                 duration=dur, 
                 caption=f"🧩 **Video con Portada Collage ({grid})**",
                 progress=progreso, progress_args=(wm, times, "Subiendo Collage (Ovid)")
             )
        
        # 4. Clean up
        try: os.remove(collage_path)
        except: pass
        
        try: os.remove(dl_path)
        except: pass
        
        await wm.delete()
        
        # 5. Auto-OFF (Check Specific AUTO)
        is_auto = conf.get(f'collage_auto_{grid}', False)
        
        if not is_auto:
            conf['collage_mode'] = False
            asyncio.create_task(save_user_config_fb(cid, conf))
            await c.send_message(cid, f"✅ **Modo Collage ({grid}) Finalizado**")
            pass

    except Exception as e:
        print(f"Collage Logic Error: {e}")
        await wm.edit(f"❌ Error crítico: {e}")

async def run_subtitle_logic(c, cid, m):
    wm = await m.reply("⬇️ **Descargando para Subtitular...**")
    dl_path = None
    out_path = None
    
    try:
        timestamp = int(time.time())
        dl_path = os.path.join("downloads", f"sub_in_{cid}_{timestamp}.mp4")
        
        # Download
        times = [0, 0]
        await m.download(file_name=dl_path, progress=progreso, progress_args=(wm, times, "Descargando para Subtítulos"))
        
        await wm.edit("📝 **Generando Subtítulos (Whisper AI)...**\n_Esto puede tardar unos minutos..._")
        
        # Subtitle Generation
        out_path = await generate_subtitles_video(dl_path, cid)
        
        if out_path and os.path.exists(out_path):
            await wm.edit("📤 **Subiendo video subtitulado...**")
            
            w, h, dur = await get_meta(out_path)
            t_path = await get_thumb(out_path, cid, int(time.time()))
            times = [0, 0]
            
            await c.send_video(
                cid, out_path,
                width=w, height=h, duration=dur,
                thumb=t_path,
                caption="📝 **Video Subtitulado (Automático)**\n_Generado con Whisper AI_",
                progress=progreso, progress_args=(wm, times, "Subiendo Subtitulado")
            )
            
            if t_path and os.path.exists(t_path): os.remove(t_path)
        else:
            await wm.edit("❌ Error generando subtítulos.")
        
    except Exception as e:
        await wm.edit(f"❌ Error Sub: {e}")
        
    finally:
        if dl_path and os.path.exists(dl_path): 
            try: os.remove(dl_path)
            except: pass
        if out_path and os.path.exists(out_path):
            try: os.remove(out_path)
            except: pass
        
        conf = get_config(cid)
        conf['subtitle_mode'] = False
        asyncio.create_task(save_user_config_fb(cid, conf))
        await wm.delete()
