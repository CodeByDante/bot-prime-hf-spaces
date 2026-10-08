import os

file_path = "c:/Users/Gonzalo/Downloads/Twisted Brody Waifus & Creampie/utils.py"

# New content for the function
new_function_code = '''def format_tracemoe_results(data):
    """Formatea resultados de trace.moe + anilist info EXTENDIDO."""
    if not data or isinstance(data, str) or 'result' not in data:
        return "🤷‍♂️ **Trace.moe: Sin resultados.**", None, False
        
    results = data['result']
    if not results:
        return "🤷‍♂️ **Trace.moe: Sin coincidencias.**", None, False
        
    # Filtrar y tomar el mejor
    best = results[0]
    similarity = float(best.get('similarity', 0)) * 100
    
    if similarity < 85.0: 
        return "🤷‍♂️ **Trace.moe: Sin coincidencias sólidas (<85%).**", None, False
        
    # Obtener info extra de Anilist
    anilist_id = best.get('anilist', None)
    meta = {}
    if anilist_id:
        from utils import get_anilist_info # Ensure import if needed, or rely on global
        meta = get_anilist_info(anilist_id) or {}
        
    # --- PROCESAR DATOS DE ANILIST ---
    
    # 1. Títulos
    titles = meta.get('title', {})
    title_romaji = titles.get('romaji', 'Desconocido')
    title_native = titles.get('native')
    
    # 2. Info
    episodes = meta.get('episodes', '?')
    duration = meta.get('duration', '?')
    fmt = meta.get('format', 'TV')
    
    desc_type = f"{episodes} ep. ({duration} min) {fmt} anime."
    
    start = meta.get('startDate', {})
    end = meta.get('endDate', {})
    s_date = f"{start.get('year', '?')}-{start.get('month', '?')}-{start.get('day', '?')}"
    e_date = f"{end.get('year', '?')}-{end.get('month', '?')}-{end.get('day', '?')}"
    aired = f"Airing from {s_date} to {e_date}."

    # 3. Alias
    aliases = meta.get('synonyms', [])
    alias_str = aliases[0] if aliases else "None"

    # 4. Géneros
    genres = meta.get('genres', [])
    genre_str = ", ".join(genres[:3]) if genres else "Unknown"

    # 5. Studios
    studios_node = meta.get('studios', {}).get('nodes', [])
    studios_str = "Unknown"
    if studios_node:
        studios_str = ", ".join([s['name'] for s in studios_node])

    # 6. Clip Match
    match_episode = best.get('episode', '?')
    time_pos = best.get('from', 0)
    m, s = divmod(int(time_pos), 60)
    time_str = f"{m}:{s:02d}"

    # NSFW Check
    is_adult = meta.get('isAdult', False)
    video_preview = best.get('video', '')
    
    # --- CONSTRUIR EL MENSAJE FINAL (EXACTO) ---
    msg = f"""
📁 Trace moe resultados
📁 Similitud: {similarity:.2f}%

📁 Title: `{title_romaji}`
📁 `{title_native if title_native else ''}`
📁 Info: {desc_type}
{aired}
📁 Alias: `{alias_str}`
📁 Genre: {genre_str}
📁 Studio: {studios_str}
📁 Clip Match: Episode: {match_episode} (Time: {time_str})
"""
        
    return msg, video_preview, is_adult
'''

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    output_lines = []
    
    # State machine to skip the FIRST definition of format_tracemoe_results
    # and REPLACE the SECOND definition.
    
    found_first_def = False
    skipping_first = False
    
    found_second_def = False
    skipping_second = False
    replaced_second = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Detect function start
        if line.strip().startswith("def format_tracemoe_results(data):"):
            if not found_first_def:
                # Found the first one (the duplicate/bad one). Start skipping.
                found_first_def = True
                skipping_first = True
                
                # Check where this function ends (naive check: next def or special comment)
                # In the file, it seems followed by # --- TRACE.MOE API SERVICE --- (approx)
                # We will skip until we see a line starting with 'def ' or '# ---' that is NOT this function
                i += 1
                continue
            else:
                # Found the second one! This is where we want to put the NEW code.
                found_second_def = True
                skipping_second = True
                
                if not replaced_second:
                    output_lines.append(new_function_code + "\n")
                    replaced_second = True
                
                i += 1
                continue

        if skipping_first:
            # We are inside the first unwanted function.
            # Stop skipping if we hit a new function definition or section header
            if line.strip().startswith("def ") or line.strip().startswith("# --- TRACE.MOE API SERVICE ---"):
                skipping_first = False
                output_lines.append(line) # Keep this line (it's the next thing)
            # Else: Drop the line
            i += 1
            continue
            
        if skipping_second:
            # We are inside the second function (which we already replaced).
            # Stop skipping if we hit end of file or next def (though it's likely EOF)
             if line.strip().startswith("def "): # Safety break if there is another function
                skipping_second = False
                output_lines.append(line)
             # Else: Drop the line
             i += 1
             continue
             
        # Normal line, keep it
        output_lines.append(line)
        i += 1

    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)
        
    print("Successfully cleaned up utils.py")

except Exception as e:
    print(f"Error: {e}")
