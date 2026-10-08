import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

old_handle_document = """@client.on(events.NewMessage(pattern=r'^/start (folder_)?[a-zA-Z0-9_-]{20}$'))
@client.on(events.NewMessage(pattern=r'^(folder/|folder_)?[a-zA-Z0-9_-]{20}$'))
async def handle_document_id(event):
    text = event.raw_text.strip()
    is_folder_request = False"""

new_handle_document = """@client.on(events.NewMessage(pattern=r'^/start (folder_)?[a-zA-Z0-9_-]{20}$'))
@client.on(events.NewMessage(pattern=r'^(folder/|folder_)?[a-zA-Z0-9_-]{20}$'))
async def handle_document_id(event):
    if editor_mode_active.get(event.chat_id, False):
        return
        
    text = event.raw_text.strip()
    is_folder_request = False"""

code = code.replace(old_handle_document, new_handle_document)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Patch for disabling delivery in editor mode applied successfully.")
