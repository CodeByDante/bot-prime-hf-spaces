import asyncio
import os
import sys

# Add current path to sys path to import handlers
sys.path.append(r"c:\Users\Gonzalo\Desktop\userbotFileStream")

from handlers.list import CATEGORIES, COMMANDS_METADATA, get_command_count

def build_list():
    category_groups = {cat: [] for cat in CATEGORIES}
    for cmd in COMMANDS_METADATA:
        cat = cmd.get("category", "Otros")
        if cat not in category_groups:
            category_groups[cat] = []
        category_groups[cat].append(cmd)
        
    category_chunks = []
    
    for cat in CATEGORIES:
        cmds_in_cat = category_groups[cat]
        if not cmds_in_cat:
            continue
            
        cat_lines = [f"📂 **{cat}**"]
        
        sorted_cmds = sorted(cmds_in_cat, key=lambda c: get_command_count(c["name"]))
        
        for cmd in sorted_cmds:
            title_raw = cmd['title']
            parts = title_raw.split(" ", 1)
            cmd_name = parts[0]
            rest_title = f" {parts[1]}" if len(parts) > 1 else ""
            
            mono_title = f"`{cmd_name}`{rest_title}"
            cat_lines.append(f"• {mono_title} : {cmd['usage']}")
            
        category_chunks.append("\n".join(cat_lines))
        
    category_chunks.append("🌐 **Guía interactiva detallada:**\nhttps://telegra.ph/comandos-09-01")
    list_text = "\n\n".join(category_chunks)
    return list_text

if __name__ == "__main__":
    try:
        text = build_list()
        print("GENERATED SUCCESSFULLY")
        print("LENGTH:", len(text))
        # Check if there are any markdown parsing errors possible
        # Telethon uses markdown, we can check for unclosed backticks
        backtick_count = text.count("`")
        print("BACKTICKS:", backtick_count)
        if backtick_count % 2 != 0:
            print("ERROR: Unclosed backticks!")
    except Exception as e:
        print("ERROR:", e)
