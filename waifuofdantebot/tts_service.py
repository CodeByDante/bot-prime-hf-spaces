import asyncio
import os
import edge_tts
import time

# --- MAPPING PERSONALIDAD -> VOZ (Latin / Spain Neural) ---
# Available Edge Voices (approximate):
# es-MX-DaliaNeural (Female, Soft/Generic)
# es-MX-JorgeNeural (Male, Generic)
# es-ES-ElviraNeural (Female, Sharp/Mature)
# es-ES-AlvaroNeural (Male, Deep/Pro)
# es-AR-ElenaNeural (Female, Argentinian)
# es-AR-TomasNeural (Male, Argentinian)

VOICE_MAP = {
    'formal': 'es-MX-JorgeNeural',      # Hombre Mexicano (Formal)
    'pasiva': 'es-MX-DaliaNeural',      # Mujer Mexicana (Suave y Humana)
    'profesional': 'es-MX-JorgeNeural', # Hombre corporativo
    'agresiva': 'es-VE-PaolaNeural',    # Mujer Venezolana (Fuerte)
    'nsfw': 'es-MX-DaliaNeural',        # Waifu (Dalia es la voz latina más natural y estándar)
    'timida': 'es-CO-SalomeNeural',     # Tímida (Colombiana suave)
    'default': 'es-MX-DaliaNeural'      # Default Latina
}

async def generate_tts_audio(text, persona='default'):
    """
    Genera un archivo de audio (MP3) a partir de texto usando edge-tts.
    Retorna la ruta del archivo o None si falla.
    """
    if not text: return None
    
    # 1. Clean Text Enhanced
    import re
    # Remove Markdown (asterisks, bold, etc)
    clean_text = text.replace('*', '').replace('_', '').replace('`', '')
    
    # Remove Stuttering (e.g. "H-hola", "s-soy") -> Replace with single word
    # Regex: Look for single letter followed by hyphen and the same letter again (case insensitive)
    # This replaces "T-t" with "T", "s-s" with "s", effectively removing the stutter for audio.
    clean_text = re.sub(r'\b([a-zA-ZáéíóúñÁÉÍÓÚÑ])-\1', r'\1', clean_text, flags=re.IGNORECASE)
    
    # Remove excessive dots (keep pause but not too long) "..." -> "."
    clean_text = re.sub(r'\.{2,}', '.', clean_text)
    
    # Remove actions in parenthesis/brackets if any left (sometimes AI puts them)
    clean_text = re.sub(r'\s*\(.*?\)\s*', ' ', clean_text)
    clean_text = re.sub(r'\s*\[.*?\]\s*', ' ', clean_text) 
    
    # 2. Select Voice
    voice = VOICE_MAP.get(persona, VOICE_MAP['default'])
    
    # 3. Output Path
    out_file = f"tts_{int(time.time())}.mp3"
    
    try:
        # Create Communicate object
        communicate = edge_tts.Communicate(clean_text, voice)
        
        # Save to file
        await communicate.save(out_file)
        
        if os.path.exists(out_file):
            return out_file
            
    except Exception as e:
        print(f"❌ Error Generating TTS: {e}")
        
    return None
