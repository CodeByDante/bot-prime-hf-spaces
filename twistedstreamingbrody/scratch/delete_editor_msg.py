import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

old_code = """                elif getattr(resp, 'raw_text', ''):
                    txt = resp.raw_text.strip()
                    if txt.startswith('/'): continue
                    await msg.edit(buttons=None)
                    
                    doc = db.collection('videos').document(txt).get()"""

new_code = """                elif getattr(resp, 'raw_text', ''):
                    txt = resp.raw_text.strip()
                    if txt.startswith('/'): continue
                    try:
                        await msg.delete()
                    except:
                        await msg.edit(buttons=None)
                    
                    doc = db.collection('videos').document(txt).get()"""

code = code.replace(old_code, new_code)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Message delete patch applied successfully.")
