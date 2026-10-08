import os

with open('bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

def get_block(start_marker, end_marker=None):
    start_idx = -1
    for i, l in enumerate(lines):
        if start_marker in l:
            start_idx = i
            break
    if start_idx == -1: return []
    
    if not end_marker:
        return lines[start_idx:]
        
    end_idx = -1
    for i in range(start_idx + 1, len(lines)):
        if end_marker in lines[i]:
            end_idx = i
            break
    
    if end_idx == -1: return lines[start_idx:]
    return lines[start_idx:end_idx]

core_lines = lines[:214] # Everything before # --- MANEJADORES ---
buscador_lines_1 = get_block("# --- MODO BUSCADOR ---", "active_tasks = {}")
subidor_lines = get_block("active_tasks = {}", "# --- CONFIGURACIÓN Y FUNCIONES DE BÚSQUEDA POR ID ---")
buscador_lines_2 = get_block("# --- CONFIGURACIÓN Y FUNCIONES DE BÚSQUEDA POR ID ---", "# --- MODO EDITOR ---")
editor_lines = get_block("# --- MODO EDITOR ---", None)

with open('core.py', 'w', encoding='utf-8') as f:
    f.writelines(core_lines)

with open('bot_buscador.py', 'w', encoding='utf-8') as f:
    f.writelines(buscador_lines_1)
    f.writelines(buscador_lines_2)

with open('bot_subidor.py', 'w', encoding='utf-8') as f:
    f.writelines(subidor_lines)

with open('bot_editor.py', 'w', encoding='utf-8') as f:
    f.writelines(editor_lines)

print("Splitting complete.")
