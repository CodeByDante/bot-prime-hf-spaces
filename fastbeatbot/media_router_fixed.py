@app.on_message(filters.video | filters.document | filters.audio | filters.animation)
async def main_media_router(c, m):
    cid = m.chat.id
    conf = get_config(cid)

    # --- NANO BANANA EXCLUSION CHECK (Images as Documents) ---
    # If Nano Banana is active, it handles its own images (even files).
    # Party Mode shouldn't steal them.
    if conf.get('ai_model_mode') == 'nano_banana':
        is_pos_image = False
        if m.photo: is_pos_image = True
        elif m.document and m.document.mime_type and m.document.mime_type.startswith('image/'): is_pos_image = True
        elif m.document and m.document.file_name:
             _, ext = os.path.splitext(m.document.file_name)
             if ext.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.heic']:
                 is_pos_image = True
        
        if is_pos_image:
            # Let ai_chat_handler handle it
            return await m.continue_propagation()
    
    # --- LOGICA: UNIR PARTY (COLECCI├ôN) ---
    # --- LOGICA: UNIR PARTY (COLECCI├ôN) ---
    # --- SMART CUT LOGIC (Top Priority within Tools) ---
    if conf.get('smart_cut_mode'):
        if SEM_SMART_CUT.locked():
             wait = await m.reply("ÔÅ│ **En Cola de Procesamiento (Smart Cut)...**\n_Esperando turno_")
        else:
             wait = await m.reply("­ƒºá **Analizando Intro...**\nÔ¼ç´©Å Bajando video...")

        async with SEM_SMART_CUT:
             if wait.text.startswith("ÔÅ│"): await wait.edit("­ƒºá **Analizando Intro...**\nÔ¼ç´©Å Bajando video...")
             
             from utils import download_parallel
             from tools_media import smart_cut_video, get_meta, get_thumb
             from tools_media import progreso as prog_callback
             
             f_p = await download_parallel(c, m, os.path.join(DATA_DIR, f"smart_{cid}_{m.id}.mp4"), progress=prog_callback, progress_args=(wait, [0,0], "Descargando"))
             if not f_p: f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"smart_{cid}_{m.id}.mp4"))
             
             if f_p and os.path.exists(f_p):
                 res_tuple = await smart_cut_video(f_p)
                 
                 if res_tuple:
                     out_path, cut_time = res_tuple
                     await wait.edit(f"Ô£é´©Å **Intro Detectada ({cut_time}s)**\nEnviando video cortado...")
                     
                     w, h, dur = await get_meta(out_path)
                     t_path = await get_thumb(out_path, cid, int(time.time()))
                     
                     try:
                         await c.send_video(
                             cid, out_path, 
                             width=w, height=h, duration=dur, thumb=t_path,
                             caption=f"­ƒºá **Smart Cut** (Intro: {cut_time}s)",
                             progress=prog_callback, progress_args=(wait, [0,0], "Enviando")
                         )
                     except:
                         await c.send_document(cid, out_path, caption=f"­ƒºá **Smart Cut** (Intro: {cut_time}s)")
                     
                     if t_path and os.path.exists(t_path): os.remove(t_path)
                     if os.path.exists(out_path): os.remove(out_path)
                 else:
                    await wait.edit("ÔÜá´©Å **No se detect├│ intro.**\nEnviando original (Directo)...")
                    
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
                        w, h, dur = await get_meta(f_p)
                        t_path = await get_thumb(f_p, cid, int(time.time()))
                        
                        try:
                            await c.send_video(
                                cid, f_p, 
                                width=w, height=h, duration=dur, thumb=t_path,
                                caption="video original sin cambios (smart cut no encontrado)",
                                progress=prog_callback, progress_args=(wait, [0,0], "Enviando")
                            )
                        except:
                            await c.send_document(cid, f_p, caption="video original sin cambios (smart cut no encontrado)")
                        
                        if t_path and os.path.exists(t_path): os.remove(t_path)
                 
                 if os.path.exists(f_p): os.remove(f_p)
             else:
                 await wait.edit("ÔØî Error descragando video.")
             
             # Auto Logic
             if not conf.get('smart_cut_auto_mode', False):
                 conf['smart_cut_mode'] = False
                 from firebase_service import save_user_config_fb
                 asyncio.create_task(save_user_config_fb(cid, conf))
                 try: await wait.delete()
                 except: pass
                 await c.send_message(cid, "Ô£à **Proceso Finalizado.**\n­ƒøæ Se desactiv├│ el modo/herramienta: Smart Cut")
             else:
                 try: await wait.delete()
                 except: pass

        return

    if not conf.get('party_mode') and not conf.get('auto_party') and not conf.get('join_party_mode') and not conf.get('extract_mode') and not conf.get('gif_mode') and not conf.get('mp3_mode') and not conf.get('cut_init_mode') and not conf.get('cut_auto_mode') and not conf.get('convert_qh_mode') and not conf.get('convert_h264_mode') and not conf.get('resize_mode') and not conf.get('resize_auto_mode') and not conf.get('custom_thumb_mode') and not conf.get('fusion_mode') and not conf.get('fusion_auto_mode') and not conf.get('fusion_auto_audio_capture'):
        return m.continue_propagation()
    
    st = url_storage.get(cid, {})

    # --- FUSION AUTO MODE (Wait Audio Step) ---
    if conf.get('fusion_auto_audio_capture', False):
        wait = await m.reply("Ô¼ç´©Å **Guardando referencia del Audio Predeterminado...**")
        
        file_id = None
        if m.audio: file_id = m.audio.file_id
        elif m.voice: file_id = m.voice.file_id
        elif m.document: file_id = m.document.file_id
        elif m.video: file_id = m.video.file_id
        
        if not file_id:
            await wait.edit("ÔØî Por favor env├¡a un archivo v├ílido (Audio, Nota de voz, Video o Documento).")
            return
            
        conf['fusion_default_audio'] = file_id
        conf['fusion_auto_audio_capture'] = False # Auto OFF after capturing
        
        from firebase_service import save_user_config_fb
        import asyncio
        asyncio.create_task(save_user_config_fb(cid, conf))
        
        from tools_fusion import show_fusion_auto_menu
        await wait.edit("Ô£à **Audio Predeterminado Guardado correctamente (ID de Telegram vinculado).**")
        await show_fusion_auto_menu(c, cid, conf)
        return

    # --- FUSION AUTO MODE FLOW ---
    
    # Global semaphore to prevent FFmpeg CPU/RAM death on mass uploads
    if 'fusion_auto_sem' not in globals():
        global fusion_auto_sem
        import asyncio
        fusion_auto_sem = asyncio.Semaphore(5)

    if conf.get('fusion_auto_mode', False):
        from tools_fusion import get_fusion_session, show_fusion_panel
        
        if conf.get('fusion_default_audio'):
            if m.video or m.document or m.animation:
                wait = await m.reply("­ƒñû **Fusi├│n Autom├ítica:** En cola... ÔÅ│")
                
                async with fusion_auto_sem:
                    await wait.edit("­ƒñû **Fusi├│n Autom├ítica:** Inicializando...")
                    
                    file_id = conf['fusion_default_audio']
                    
                    # Create a reliable unique hash for this specific file_id so it downloads the new one if changed
                    import hashlib
                    clean_id = hashlib.md5(file_id.encode()).hexdigest()[:15]
                    a_path = os.path.join(DATA_DIR, f"fus_auto_a_{cid}_{clean_id}.mp3")
                    
                    if not os.path.exists(a_path):
                        await wait.edit("­ƒñû **Fusi├│n Autom├ítica:** Recuperando audio predeterminado de la nube...")
                        try:
                            a_path = await c.download_media(file_id, file_name=a_path)
                        except Exception as e:
                            await wait.edit("ÔØî El audio predeterminado ya no es accesible. Por favor gu├írdalo de nuevo.")
                            return
                            
                    if not a_path or not os.path.exists(a_path):
                        await wait.edit("ÔØî Fallo obteniendo el audio predeterminado.")
                        return
                    
                    await wait.edit("­ƒñû **Fusi├│n Autom├ítica:** Descargando video objetivo...")
                    from utils import download_parallel
                    from tools_media import progreso
                    
                    filename = getattr(m.video, 'file_name', None) or getattr(m.document, 'file_name', None) or getattr(m.animation, 'file_name', None) or ".mp4"
                    _, ext = os.path.splitext(filename)
                    ts = int(time.time())
                    # Ensure unique filename by appending m.id (Message ID) for concurrent batches
                    v_path = os.path.join(DATA_DIR, f"fus_auto_v_{ts}_{m.id}_{cid}{ext}")
                    
                    f_p = await download_parallel(c, m, v_path, concurrency=16, progress=progreso, progress_args=(wait, [0,0], "Bajando Video"))
                    if not f_p: f_p = await c.download_media(m, file_name=v_path)
                    
                    if not f_p:
                        await wait.edit("ÔØî Error bajando video.")
                        return
                    
                    await wait.edit("ÔÜÖ´©Å **Fusi├│n Autom├ítica:** Mezclando y renderizando...")
                    
                    sess = await get_fusion_session(cid)
                    out_path = os.path.join(DATA_DIR, f"fusion_auto_final_{ts}_{m.id}_{cid}.mp4")
                    
                    from tools_fusion import process_fusion
                    ok, err = await process_fusion(
                        f_p, a_path, out_path, 
                        keep_video_audio=conf.get('fusion_auto_cfg_v', True), 
                        keep_added_audio=conf.get('fusion_auto_cfg_a', True), 
                        safe_mode=sess.get('safe_mode', False),
                        vol_v=conf.get('fusion_auto_vol_v', 100),
                        vol_a=conf.get('fusion_auto_vol_a', 100),
                        loop_audio=conf.get('fusion_auto_loop', True),
                        force_shortest=conf.get('fusion_auto_shortest', False)
                    )
                    
                    if ok:
                        await wait.edit("­ƒôñ **Fusi├│n Autom├ítica:** Subiendo...")
                        from tools_media import get_meta, get_thumb
                        w, h, dur = await get_meta(out_path)
                        thumb = await get_thumb(out_path, cid, ts)
                    
                    
                        try:
                            await c.send_video(
                                cid, out_path,
                                caption="­ƒñû **Fusi├│n Autom├ítica Terminada**",
                                width=w, height=h, duration=dur, thumb=thumb,
                                progress=progreso, progress_args=(wait, [0,0], "Enviando")
                            )
                        except Exception as e:
                            try: await c.send_document(cid, out_path, caption="­ƒñû **Fusi├│n Autom├ítica** (Fallback Doc)", thumb=thumb)
                            except: pass
                            
                        if thumb and os.path.exists(thumb): os.remove(thumb)
                        if os.path.exists(out_path): os.remove(out_path)
                        await wait.delete()
                    else:
                        await wait.edit(f"ÔØî Error Fusi├│n Autom├ítica:\n`{err}`")
                    
                    if os.path.exists(f_p): os.remove(f_p)
                    return
            else:
                return # Ignore messages that aren't videos in auto mode
                
        else:
            await m.reply("ÔÜá´©Å El Modo Autom├ítico est├í activado, pero falta el Audio Predeterminado. Ve al submen├║ para establecerlo.")
            return

    # --- FUSION MANUAL MODE FLOW ---
    if conf.get('fusion_mode', False):
        from tools_fusion import get_fusion_session, show_fusion_panel
        sess = await get_fusion_session(cid)
        
        if not sess['video']:
            # STEP 1: Register Video Base
            sess['video'] = m
            sess['step'] = 1
            await m.reply("­ƒÄÑ **Video Registrado (1).**\n\nAhora env├¡ame el **AUDIO** (o video).")
            return
            
        else:
            # STEP 2: Register Audio
            sess['audio'] = m
            sess['step'] = 2
            
            # Show Panel
            await show_fusion_panel(c, cid)
            return



    # --- CUSTOM THUMB MODE (Video Step + Catalog Gen) ---
    if conf.get('custom_thumb_mode', False) and st.get('custom_thumb_step') == 'wait_video':
        wait = await m.reply("Ô¼ç´©Å **Bajando Video Base...**")
        
        # Download with Progress
        from utils import download_parallel
        from tools_media import progreso
        
        f_p = await download_parallel(c, m, os.path.join(DATA_DIR, f"custom_base_{cid}_{m.id}.mp4"), concurrency=16, progress=progreso, progress_args=(wait, [0,0], "Bajando Video (x16)"))
        if not f_p: f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"custom_base_{cid}_{m.id}.mp4"), progress=progreso, progress_args=(wait, [0,0], "Bajando Video"))
        
        if f_p:
            await wait.edit("­ƒÄ× **Generando Cat├ílogo de Miniaturas...**\n(Cada 5s)")
            from tools_media import generate_catalog_thumbs
            
            thumbs = await generate_catalog_thumbs(f_p, interval=5)
            
            url_storage[cid] = {
                'custom_thumb_step': 'wait_thumb', 
                'video_path': f_p,
                'custom_thumbs_list': thumbs
            }
            
            if thumbs:
                # Ask for custom image FIRST, with option for Catalog
                kb = InlineKeyboardMarkup([
                     [InlineKeyboardButton("­ƒÄ× Ver Cat├ílogo Autom├ítico", callback_data="custom|show_catalog")],
                     [InlineKeyboardButton("ÔØî Cancelar", callback_data="menu|tools")]
                 ])
                
                await wait.delete()
                await c.send_message(cid, "Ô£à **Video Recibido.**\n\n1´©ÅÔâú Env├¡ame una **IMAGEN** para usar de portada.\n2´©ÅÔâú O abre el c├ítalogo de frames del video.", reply_markup=kb)
            else:
                await wait.edit("ÔÜá´©Å No pude generar miniaturas del video.\n**Env├¡a una imagen manual** para usarla.")
                
        else:
            await wait.edit("ÔØî Error descarga video.")
        return

    # --- CONVERTIDOR QH FLOW (QUEUE + TURBO x32) ---
    if conf.get('convert_qh_mode', False):
        # 1. Detectar si es Imagen (para no convertirla a video)
        is_image = False
        original_ext = ""
        
        if m.photo:
            is_image = True
            original_ext = ".jpg"
        elif m.document:
            if m.document.mime_type and m.document.mime_type.startswith("image/"):
                is_image = True
            if m.document.file_name:
                _, original_ext = os.path.splitext(m.document.file_name)
                if original_ext.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.bmp']:
                    is_image = True
        
        # Si es imagen, procesamos como imagen (pass-through o conversi├│n simple si hiciera falta)
        if is_image:
            wait = await m.reply("Ô¼ç´©Å **Bajando Imagen...**")
            # Descargar con nombre original/extensi├│n correcta
            # Usamos download_media de pyrogram directo para im├ígenes, es r├ípido.
            dl_path = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"qh_img_{cid}_{m.id}{original_ext}"))
            
            if dl_path and os.path.exists(dl_path):
                await wait.edit("­ƒôñ **Enviando Imagen...**")
                try:
                    # Enviar como FOTO (Normal) como pidi├│ el usuario
                    await c.send_photo(cid, dl_path, caption="­ƒôª **Imagen (QH)**")
                except Exception as e:
                    # Fallback a documento solo si falla
                    await c.send_document(cid, dl_path, caption="­ƒôª **Imagen (QH)**")
                
                os.remove(dl_path)
                await wait.delete()
            else:
                 await wait.edit("ÔØî Error descargando imagen.")
            return

        # 2. Si NO es imagen (Video/Audio), flujo normal de Video
        if SEM_CONVERT_QH.locked():
             wait = await m.reply("ÔÅ│ **En Cola de Procesamiento...**\n_Esperando turno (M├íx 5 simult├íneos)_")
        else:
             wait = await m.reply("Ô¼ç´©Å **Bajando TURBO (x32)...**\n­ƒÜÇ Convertidor QH Activo")

        async with SEM_CONVERT_QH:
             if wait.text.startswith("ÔÅ│"): await wait.edit("Ô¼ç´©Å **Bajando TURBO (x32)...**\n­ƒÜÇ Convertidor QH Activo")
             
             from utils import download_parallel
             from tools_media import progreso
             
             # Force MP4 for Videos
             f_p = await download_parallel(c, m, os.path.join(DATA_DIR, f"conv_qh_{cid}_{m.id}.mp4"), concurrency=32, progress=progreso, progress_args=(wait, [0,0], "Descargando"))
             
             if not f_p:
                 # Fallback
                 f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"conv_qh_{cid}_{m.id}.mp4"))

             if f_p:
                 await wait.edit("­ƒôñ **Enviando Video Convertido...**")
                 from tools_media import get_meta, get_thumb
                 w, h, dur = await get_meta(f_p)
                 t_path = await get_thumb(f_p, cid, int(time.time()))
                 
                 try:
                     await c.send_video(cid, f_p, width=w, height=h, duration=dur, thumb=t_path, caption=f"­ƒôª **Convertido QH**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                 except Exception as e:
                     await c.send_document(cid, f_p, caption=f"­ƒôª **Convertido QH** (Doc Fallback)", progress=progreso, progress_args=(wait, [0,0], "Enviando"))

                 if t_path and os.path.exists(t_path): os.remove(t_path)
                 if os.path.exists(f_p): os.remove(f_p)
                 await wait.delete()
             else:
                 await wait.edit("ÔØî Error en descarga.")
        return

    # --- DIMENSIONADOR FLOW ---
    if conf.get('resize_mode'):
        target = conf.get('resize_target', '9:16')
        wait = await m.reply(f"­ƒôÉ **Dimensionador Activo**\nTarget: `{target}`\nÔ¼ç´©Å Bajando video...")
        
        from utils import download_parallel
        from tools_media import resize_video, progreso, get_meta, get_thumb
        
        # Download
        f_p = await download_parallel(c, m, os.path.join(DATA_DIR, f"resize_{cid}_{m.id}.mp4"), concurrency=32, progress=progreso, progress_args=(wait, [0,0], "Descargando"))
        if not f_p:
            f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"resize_{cid}_{m.id}.mp4"))
            
        if f_p and os.path.exists(f_p):
            await wait.edit(f"ÔÜÖ´©Å **Redimensionando a {target}...**\n(Zoom + Crop al centro)")
            
            # Process
            out_path = await resize_video(f_p, target)
            
            if out_path and os.path.exists(out_path):
                await wait.edit("­ƒôñ **Enviando Video Redimensionado...**")
                w, h, dur = await get_meta(out_path)
                t_path = await get_thumb(out_path, cid, int(time.time()))
                
                try:
                    await c.send_video(cid, out_path, width=w, height=h, duration=dur, thumb=t_path, caption=f"­ƒôÉ **Redimensionado a {target}**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                except:
                    await c.send_document(cid, out_path, caption=f"­ƒôÉ **Redimensionado a {target}**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                
                # Cleanup
                if t_path and os.path.exists(t_path): os.remove(t_path)
                os.remove(out_path)
                # Auto-OFF
                conf['resize_mode'] = False
                from firebase_service import save_user_config_fb
                asyncio.create_task(save_user_config_fb(cid, conf))
                await c.send_message(cid, "Ô£à **Proceso Finalizado.**\n­ƒøæ Se desactiv├│ el modo/herramienta: Dimensionador")
            else:
                 await wait.edit("ÔØî Error al procesar el video.")
            
            if os.path.exists(f_p): os.remove(f_p)
            try: await wait.delete()
            except: pass
        else:
             await wait.edit("ÔØî Error descragando video.")
        return

    # --- CONVERTIDOR MP4 H264 FLOW (QUEUE + TURBO x32 + FFMPEG) ---
    if conf.get('convert_h264_mode', False):
        if SEM_CONVERT_H264.locked():
             wait = await m.reply("ÔÅ│ **En Cola de Procesamiento...**\n_Esperando turno (M├íx 5 simult├íneos)_")
        else:
             wait = await m.reply("Ô¼ç´©Å **Bajando TURBO (x32)...**\n­ƒÜÇ Convertidor H.264 Activo")

        async with SEM_CONVERT_H264:
             if wait.text.startswith("ÔÅ│"): await wait.edit("Ô¼ç´©Å **Bajando TURBO (x32)...**\n­ƒÜÇ Convertidor H.264 Activo")
             
             from utils import download_parallel
             from tools_media import progreso, convert_to_h264, get_meta, get_thumb
             
             # Descarga en modo documento (para aceptar MKV, TS, AVI crudos)
             original_path = os.path.join(DATA_DIR, f"tmp_h264_{cid}_{m.id}") # Sin extension para que download_parallel o fallback decidan o usar extension original
             
             # Intentamos adivinar extension del nombre de archivo si es documento
             ext = ""
             if m.document and m.document.file_name:
                 _, ext = os.path.splitext(m.document.file_name)
             elif m.video and m.video.file_name:
                  _, ext = os.path.splitext(m.video.file_name)
             elif m.animation:
                  # Treat Animation/GIF as MP4 source for ffmpeg
                  ext = ".mp4" 
             
             if not ext: ext = ".mp4" # Default
             original_path += ext

             f_p = await download_parallel(c, m, original_path, concurrency=32, progress=progreso, progress_args=(wait, [0,0], "Descargando"))
             
             if not f_p:
                 f_p = await c.download_media(m, file_name=original_path)

             if f_p and os.path.exists(f_p):
                 await wait.edit("ÔÜÖ´©Å **Convirtiendo a MP4 H.264...**\nEsto puede tardar seg├║n el peso.")
                 
                 # Conversion FFMPEG
                 h264_path = await convert_to_h264(f_p)
                 
                 if h264_path and os.path.exists(h264_path):
                     await wait.edit("­ƒôñ **Enviando Video H.264...**")
                     w, h, dur = await get_meta(h264_path)
                     t_path = await get_thumb(h264_path, cid, int(time.time()))
                     
                     try:
                         # Send as Video
                         await c.send_video(cid, h264_path, width=w, height=h, duration=dur, thumb=t_path, caption=f"­ƒÄ× **Convertido H.264**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                     except Exception as e:
                         await c.send_document(cid, h264_path, caption=f"­ƒÄ× **Convertido H.264** (Doc Fallback)", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                     
                     if t_path and os.path.exists(t_path): os.remove(t_path)
                     os.remove(h264_path)
                 else:
                     await wait.edit("ÔØî **Error en la conversi├│n.**\nQuiz├ís el archivo est├í da├▒ado.")
                 
                 if os.path.exists(f_p): os.remove(f_p)
                 try: await wait.delete()
                 except: pass
             else:
                 await wait.edit("ÔØî Error en descarga.")
        return

    # --- AUTO RESIZE SPECIFIC FLOW ---
    if conf.get('resize_auto_mode', False) and 'party_pending' not in st:
        # Check Semaphore Status (Reusing SEM_AUTO_CORTE for shared resource limit)
        if SEM_AUTO_CORTE.locked():
             wait = await m.reply("ÔÅ│ **En Cola de Procesamiento (Resize)...**\n_Esperando turno_")
        else:
             wait = await m.reply("Ô¼ç´©Å **Bajando para Redimensionar...**\n­ƒÜÇ Velocidad M├íxima Activada")

        async with SEM_AUTO_CORTE:
            if wait.text.startswith("ÔÅ│"): await wait.edit("Ô¼ç´©Å **Bajando...**")
            
            # 1. Download
            ext = ".mp4"
            if m.document and m.document.file_name: _, ext = os.path.splitext(m.document.file_name)
            elif m.video and m.video.file_name: _, ext = os.path.splitext(m.video.file_name)
            
            from utils import download_parallel
            from tools_media import progreso, resize_video, get_meta, get_thumb
            
            f_p = await download_parallel(c, m, os.path.join(DATA_DIR, f"resize_{cid}_{m.id}{ext}"), progress=progreso, progress_args=(wait, [0,0], "Descargando"))
            
            if not f_p: f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"resize_{cid}_{m.id}{ext}"))

            if f_p and os.path.exists(f_p):
                val = conf.get('resize_auto_val', '9:16')
                await wait.edit(f"­ƒôÉ **Redimensionando a {val}...**")
                
                # 2. PROCESAR
                out_path = await resize_video(f_p, val)
                
                if out_path:
                    w, h, dur = await get_meta(out_path)
                    t_path = await get_thumb(out_path, cid, int(time.time()))
                    
                    await wait.edit("­ƒôñ **Enviando video redimensionado...**")
                    try:
                        await c.send_video(
                            cid, out_path, 
                            width=w, height=h, duration=dur, thumb=t_path,
                            caption=f"Ô£à **Auto Dimensionador** (`{val}`)",
                            progress=progreso, progress_args=(wait, [0,0], "Enviando")
                        )
                    except Exception as e:
                         await c.send_document(cid, out_path, caption=f"Ô£à **Auto Dimensionador** (`{val}`)", thumb=t_path)
                    
                    if t_path and os.path.exists(t_path): os.remove(t_path)
                    os.remove(out_path)
                else:
                    await wait.edit("ÔØî Error al redimensionar.")
                
                if os.path.exists(f_p): os.remove(f_p)
                try: await wait.delete()
                except: pass
            else:
                await wait.edit("ÔØî Error en descarga.")
        return

    # --- AUTO CORTE SPECIFIC FLOW (QUEUE) ---
    if conf.get('cut_auto_mode', False) and 'party_pending' not in st:
        # Check Semaphore Status
        if SEM_AUTO_CORTE.locked():
             wait = await m.reply("ÔÅ│ **En Cola de Procesamiento...**\n_Esperando turno (M├íx 5 simult├íneos)_")
        else:
             wait = await m.reply("Ô¼ç´©Å **Bajando TURBO (x16)...**\n­ƒÜÇ Velocidad M├íxima Activada")

        async with SEM_AUTO_CORTE:
            if wait.text.startswith("ÔÅ│"): await wait.edit("Ô¼ç´©Å **Bajando TURBO (x16)...**\n­ƒÜÇ Velocidad M├íxima Activada")
            
            # Determine Extension
            ext = ".mp4"
            if m.audio: ext = ".mp3"
            if m.document and m.document.file_name: _, ext = os.path.splitext(m.document.file_name)
            elif m.video and m.video.file_name: _, ext = os.path.splitext(m.video.file_name)
            elif m.audio and m.audio.file_name: _, ext = os.path.splitext(m.audio.file_name)
            
            from utils import download_parallel
            from tools_media import progreso
            f_p = await download_parallel(c, m, os.path.join(DATA_DIR, f"party_{cid}_{m.id}{ext}"), progress=progreso, progress_args=(wait, [0,0], "Descargando"))
            
            if not f_p:
                  f_p = await c.download_media(m, file_name=os.path.join(DATA_DIR, f"party_{cid}_{m.id}{ext}"))

            # Logic Auto Cut
            val = conf.get('cut_auto_val', '15')
            await wait.edit(f"Ô£é´©Å **Auto Corte Activo ({val}s)**\nProcesando...")
            
            from tools_media import cut_video_start, get_meta, get_thumb
            out = await cut_video_start(f_p, val)

            if out:
                await wait.edit("­ƒôñ **Enviando video cortado...**")
                w, h, dur = await get_meta(out)
                t_path = await get_thumb(out, cid, int(time.time()))
                
                try:
                    if out.lower().endswith(('.mp3', '.m4a', '.flac', '.wav', '.ogg')):
                         # Send as Audio
                         await c.send_audio(cid, out, caption=f"Ô£é´©Å **Corte Inicial Auto ({val}s)**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                    else:
                         # Send as Video
                         await c.send_video(cid, out, width=w, height=h, duration=dur, thumb=t_path, caption=f"Ô£é´©Å **Corte Inicial Auto ({val}s)**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))
                except Exception as e:
                    await c.send_document(cid, out, caption=f"Ô£é´©Å **Corte Inicial Auto ({val}s)**", progress=progreso, progress_args=(wait, [0,0], "Enviando"))

                if t_path and os.path.exists(t_path): os.remove(t_path)
                if os.path.exists(out): os.remove(out)
                await wait.delete()
                if os.path.exists(f_p): os.remove(f_p)
            else:
                await wait.edit("ÔØî Error en Auto Corte.")
        return
        
    # --- STANDARD FLOW (No Queue / One-by-One Manual) ---

    # --- DEFERRED DOWNLOAD CHECK ---
    # Si NO hay configuraci├│n pendiente, NO descargar. Preguntar primero.
    if 'party_pending' not in st and not (conf.get('gif_mode') or conf.get('mp3_mode') or conf.get('cut_init_mode') or conf.get('extract_mode')):
         # --- CUSTOM AUTO PARTY CHECK (Priority) ---
         return

         return

    # --- DEFERRED EXTRACT MODE CHECK ---
    if conf.get('extract_mode') and 'extract_pending' not in st:
         # Ignore if auto_extract is ON (let it download)
         if conf.get('auto_extract', False):
             pass 
         else:
             url_storage[cid] = {'extract_step': 'wait_mode', 'extract_msg': m}
             kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("ÔÅ▒ Segundos", callback_data="extract_sel|sec"), InlineKeyboardButton("­ƒòÆ Minutos", callback_data="extract_sel|min")],
                [InlineKeyboardButton("­ƒÄ» Frame Exacto", callback_data="extract_sel|exact")],
                [InlineKeyboardButton("­ƒöÖ Volver", callback_data="menu|tools")]
             ])
             # Check if we should delete user message to keep chat clean or just reply? 
             # Party mode replies. We reply.
             await m.reply("­ƒû╝ **Modo Extractor Activo**\n\n1´©ÅÔâú **Configura** abajo ­ƒæç\n2´©ÅÔâú El video se descargar├í **despu├®s** de configurar.", reply_markup=kb)
             return

    wait = await m.reply("Ô¼ç´©Å **Bajando TURBO (x16)...**\n­ƒÜÇ Velocidad M├íxima Activada")
    
    from utils import download_parallel
    from tools_media import progreso
    
    # Determine Extension
    ext = ".mp4"
    if m.audio: ext = ".mp3"
    if m.document and m.document.file_name: _, ext = os.path.splitext(m.document.file_name)
    elif m.video and m.video.file_name: _, ext = os.path.splitext(m.video.file_name)
    elif m.audio and m.audio.file_name: _, ext = os.path.splitext(m.audio.file_name)

    # Create Job Directory (Nested)
    tool_folder = os.path.join(DATA_DIR, "general_temp")
    if not os.path.exists(tool_folder): os.makedirs(tool_folder)
    
    job_dir = os.path.join(tool_folder, f"job_{cid}_{time.time_ns()}_{random.randint(1000, 9999)}")
    if not os.path.exists(job_dir): os.makedirs(job_dir)
    
    f_p = await download_parallel(c, m, os.path.join(job_dir, f"party_{cid}{ext}"), progress=progreso, progress_args=(wait, [0,0], "Descargando"))
    
    if not f_p:
         # Fallback manual por si acaso
         f_p = await c.download_media(m, file_name=os.path.join(job_dir, f"party_{cid}{ext}"))
    
    # ┬┐Hay una acci├│n pendiente?
    if conf.get('gif_mode'):
        # Solo GIF, sin men├║ de opciones
        await run_gif_logic(c, cid, f_p, wait)
    elif conf.get('mp3_mode'):
        # Solo MP3, sin men├║
        await run_mp3_logic(c, cid, f_p, wait)
    elif conf.get('cut_init_mode'):
        # Ir al men├║ de corte (Manual)
        url_storage[cid] = {'cut_step': 'wait_time', 'file': f_p}
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("5s", callback_data="cut_exec|00:05"), InlineKeyboardButton("10s", callback_data="cut_exec|00:10"), InlineKeyboardButton("30s", callback_data="cut_exec|00:30")],
            [InlineKeyboardButton("1m", callback_data="cut_exec|01:00"), InlineKeyboardButton("Ô£Å´©Å Manual", callback_data="cut_input|manual")],
            [InlineKeyboardButton("­ƒöÖ Volver", callback_data="menu|tools")]
        ])
        await wait.edit("Ô£é´©Å **Corte Inicial**\n┬┐Cu├ínto tiempo quieres cortar del inicio?\n(El video empezar├í DESPU├ëS de este tiempo)", reply_markup=kb)
    elif conf.get('extract_mode'):
        # Ir al men├║ de extracci├│n
        url_storage[cid] = {'extract_step': 'wait_mode', 'file': f_p}
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("ÔÅ▒ Segundos", callback_data="extract_sel|sec"), InlineKeyboardButton("­ƒòÆ Minutos", callback_data="extract_sel|min")],
            [InlineKeyboardButton("­ƒÄ» Frame Exacto", callback_data="extract_sel|exact")],
            [InlineKeyboardButton("­ƒöÖ Volver", callback_data="menu|tools")]
        ])
        await wait.edit("­ƒû╝ **Modo Extractor**\n┬┐C├│mo quieres extraer las im├ígenes?", reply_markup=kb)
    else:
        # Modo clásico: El usuario envió el video y AHORA elige
        url_storage[cid] = {'party_step': 'wait_mode', 'file': f_p}
        kb_p = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧩 Partes", callback_data="party_sel|parts"), InlineKeyboardButton("⏱ Tiempo", callback_data="party_sel|time")],
            [InlineKeyboardButton("✂️ Rango", callback_data="party_sel|range")],
            [InlineKeyboardButton("🔙 Volver", callback_data="menu|party_off")]
        ])
        await wait.edit("✂️ **Modo Party**\nSelecciona una opción:", reply_markup=kb_p)
