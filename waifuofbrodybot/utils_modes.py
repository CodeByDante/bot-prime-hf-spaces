import asyncio
from database import get_config, user_config

# --- EXCLUSIVE MODE HELPER ---
async def set_exclusive_mode(chat_id, mode_key, is_toggle=True):
    """
    Activa un modo exclusivo, desactivando otros que puedan crear conflicto.
    Lista de modos exclusivos:
    - cut_init_mode
    - cut_auto_mode (puede coexistir?)
    - extract_mode
    - party_mode (implícito en url_storage)
    - tagger_mode
    - research_mode
    - collage_mode (legacy)
    - video_mixer_mode
    - gif_mode
    - mp3_mode
    - sticker_mode
    - saucenao_mode
    """
    conf = get_config(chat_id)
    current = conf.get(mode_key, False)
    target_val = not current if is_toggle else True
    
    print(f"DEBUG EXCLUSIVE: CID={chat_id} Key={mode_key} Current={current} Target={target_val}")
    
    # Ensure Conf exists in Global Dict (Consistency)
    if chat_id not in user_config:
        user_config[chat_id] = conf

    # Si estamos apagando, solo apagamos y guardamos
    if not target_val:
        conf[mode_key] = False
        user_config[chat_id][mode_key] = False # Force Global Update
        print(f"DEBUG EXCLUSIVE: Forced OFF. New Val in Dict: {user_config[chat_id].get(mode_key)}")
        
        from firebase_service import save_user_config_fb
        asyncio.create_task(save_user_config_fb(chat_id, conf))
        return False, None

    # Si estamos encendiendo, apagamos conflictos
    conflict_modes = [
        'cut_init_mode', 'extract_mode', 'gif_mode', 'mp3_mode', 'sticker_mode', 
        'saucenao_mode', 'tagger_mode', 'research_mode', 'collage_mode', 'video_mixer_mode',
        'tiktok_fast_mode', 'parallel_thumb_mode', 'fusion_mode',
        'smart_cut_mode', 'sub_mode', 'waifux2_mode', 'convert_qh_mode', 
        'convert_h264_mode', 'resize_mode', 'custom_thumb_mode',
        'translate_manga_mode', 'viral_mode', 'party_mode', 'cut_auto_mode', 'smart_cut_auto_mode'
    ]
    
    # Mapping for Human Readable Names
    MODE_NAMES = {
        'cut_init_mode': 'Corte Inteligente', 
        'extract_mode': 'Extractor',
        'gif_mode': 'Modo GIF',
        'mp3_mode': 'Modo MP3',
        'sticker_mode': 'Modo Sticker',
        'saucenao_mode': 'SauceNAO',
        'tagger_mode': 'Tagger',
        'research_mode': 'Deep Research',
        'collage_mode': 'Collage',
        'video_mixer_mode': 'Video Mixer',
        'tiktok_fast_mode': 'Tiktok Fast',
        'parallel_thumb_mode': 'Miniatura Personalizada',
        'fusion_mode': 'Modo Fusión',
        'smart_cut_mode': 'Smart Cut',
        'sub_mode': 'Subtitulado AI',
        'waifux2_mode': 'Waifu2x',
        'convert_qh_mode': 'Convertidor QH',
        'convert_h264_mode': 'Convertidor H.264',
        'resize_mode': 'Dimensionador',
        'custom_thumb_mode': 'Miniatura Manual',
        'translate_manga_mode': 'Traductor Manga',
        'viral_mode': 'Shorts Virales',
        'party_mode': 'Modo Party',
        'cut_auto_mode': 'Auto Corte',
        'smart_cut_auto_mode': 'Smart Cut Auto'
    }
    
    disabled_list = []
    for m in conflict_modes:
        if m != mode_key and conf.get(m):
            conf[m] = False
            # Get readable name or fallback to key
            name = MODE_NAMES.get(m, m)
            disabled_list.append(name)
            
    conf[mode_key] = True
    
    from firebase_service import save_user_config_fb
    asyncio.create_task(save_user_config_fb(chat_id, conf))
    
    disabled_str = ", ".join(disabled_list) if disabled_list else None
    return True, disabled_str
