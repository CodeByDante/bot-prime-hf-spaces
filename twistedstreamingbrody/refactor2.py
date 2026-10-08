import re

def add_mode_filter(filename, mode_name):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    out_lines = []
    out_lines.append("import asyncio\nimport uuid\nimport time\n")
    out_lines.append("from telethon import events, Button\n")
    out_lines.append("from telethon.tl.types import KeyboardButtonSimpleWebView, KeyboardButtonWebView\n")
    out_lines.append("from google.cloud.firestore_v1.base_query import FieldFilter\n")
    out_lines.append("from core import *\n\n")
    
    i = 0
    while i < len(lines):
        line = lines[i]
        out_lines.append(line)
        if line.strip().startswith('@client.on('):
            # next line is usually async def ...
            i += 1
            if i < len(lines):
                next_line = lines[i]
                out_lines.append(next_line)
                if next_line.strip().startswith('async def '):
                    # extract the indent
                    indent = next_line[:len(next_line) - len(next_line.lstrip())]
                    # get event param name
                    match = re.search(r'async def \w+\((.*?)\):', next_line)
                    if match:
                        param = match.group(1).split(',')[0].strip()
                        if param in ('event', 'event_or_query', 'e'):
                            out_lines.append(f"{indent}    chat_id = getattr({param}, 'chat_id', getattr(getattr({param}, 'message', None), 'chat_id', None))\n")
                            out_lines.append(f"{indent}    if user_modes.get(chat_id) != '{mode_name}': return\n")
        i += 1

    with open(filename, 'w', encoding='utf-8') as f:
        f.writelines(out_lines)

add_mode_filter('bot_subidor.py', 'subidor')
add_mode_filter('bot_editor.py', 'editor')
add_mode_filter('bot_buscador.py', 'buscador')
print("Done")
