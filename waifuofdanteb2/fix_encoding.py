
import os

# Content to append
new_function = r"""
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- HELPER: PAGINATION GRID ---
def generate_grid_keyboard(current_idx, total_items, prefix_sel, prefix_nav, prefix_jump, prefix_back='menu|tools', extra_rows=None):
    '''
    Genera un teclado de cuadrícula (5x2) para selección paginada.
    - current_idx: índice actual (0-based) para resaltar (opcional).
    - total_items: total de elementos.
    - prefix_sel: callback base para selección (ej: 'tiktok|sel|'). Appends index.
    - prefix_nav: callback base para nav (ej: 'tiktok|nav|'). Appends '{cur}|prev' or '{cur}|next'.
    - prefix_jump: callback para input manual (ej: 'tiktok|jump').
    - prefix_back: callback para volver.
    '''
    page_size = 10
    current_page = current_idx // page_size
    start_idx = current_page * page_size
    end_idx = min(start_idx + page_size, total_items)
    
    buttons = []
    
    # Grid 5x2
    # Row 1: 1-5
    row1 = []
    for i in range(start_idx, min(start_idx + 5, end_idx)):
        # Display is 1-based (i+1)
        # Highlight current? Maybe simply numbers.
        lbl = f'✅ {i+1}' if i == current_idx else f'{i+1}'
        row1.append(InlineKeyboardButton(lbl, callback_data=f'{prefix_sel}{i}'))
    buttons.append(row1)
    
    # Row 2: 6-10
    if end_idx > start_idx + 5:
        row2 = []
        for i in range(start_idx + 5, end_idx):
             lbl = f'✅ {i+1}' if i == current_idx else f'{i+1}'
             row2.append(InlineKeyboardButton(lbl, callback_data=f'{prefix_sel}{i}'))
        buttons.append(row2)

    # Nav Row: [< Prev] [Jump] [Next >]
    nav_row = []
    
    # Prev (If not first page)
    if start_idx > 0:
        # Jump back 10
        target = max(0, start_idx - 10)
        nav_row.append(InlineKeyboardButton('⬅️ Anterior', callback_data=f'{prefix_nav}{current_idx}|prev'))
    else:
        nav_row.append(InlineKeyboardButton('☁️ Inicio', callback_data='ignore'))
        
    # Jump Button
    nav_row.append(InlineKeyboardButton('🔢 Ir a...', callback_data=f'{prefix_jump}'))
    
    # Next (If not last page)
    if end_idx < total_items:
        # Jump forward 10
        # target = start_idx + 10 (handled by logic)
        nav_row.append(InlineKeyboardButton('Siguiente ➡️', callback_data=f'{prefix_nav}{current_idx}|next'))
    else:
        nav_row.append(InlineKeyboardButton('☁️ Fin', callback_data='ignore'))
        
    buttons.append(nav_row)
    
    # Extra Rows (Control buttons like 'Add', 'Random', 'Delete')
    if extra_rows:
        for r in extra_rows:
            buttons.append(r)
            
    # Back Row defaults
    # buttons.append([InlineKeyboardButton('🔙 Volver', callback_data=prefix_back)])
    
    return InlineKeyboardMarkup(buttons)
"""

try:
    # Read Clean File
    with open("utils_clean.py", "r", encoding="utf-8") as f:
        clean_content = f.read()

    # Write to utils.py
    with open("utils.py", "w", encoding="utf-8") as f:
        f.write(clean_content)
        f.write("\n")
        f.write(new_function)
        
    print("SUCCESS: utils.py restored.")
except Exception as e:
    print(f"ERROR: {e}")
