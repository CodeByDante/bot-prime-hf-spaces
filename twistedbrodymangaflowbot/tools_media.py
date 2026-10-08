import os
import time
import asyncio
from pyrogram.errors import FloodWait
from database import update_progress

async def progreso(cur, tot, msg, times, act, orig_id=None):
    if not msg: return
    now = time.time()
    if not orig_id: orig_id = msg.id # Fallback
    
    safe_cur = int(cur) if cur else 0
    safe_tot = int(tot) if tot else 0
    
    if safe_tot == 0: return

    per = safe_cur * 100 / safe_tot
    
    if isinstance(times, (int, float)):
         times = [times, 0]
    
    last_time = times[0]
    last_per = times[1]
    
    if (now - last_time) > 8 or (per - last_per) > 5 or safe_cur == safe_tot:
        times[0] = now
        times[1] = per
        
        try:
            mb_cur = safe_cur / (1024 * 1024)
            mb_tot = safe_tot / (1024 * 1024)
            
            action_text = act if act else "Enviando"
            emoji = "⬇️" if "Descargando" in action_text else "📤"
            
            from database import task_progress
            existing_url = task_progress.get(msg.chat.id, {}).get(orig_id, {}).get('url', 'N/A')
            update_progress(msg.chat.id, orig_id, percent=per, status=f"{action_text} {emoji}", speed=f"{mb_cur:.1f}MB", url=existing_url)
            
            txt = f"{emoji} {action_text} 📁 `{mb_cur:.1f}/{mb_tot:.1f} MB` (`{per:.1f}%`)"
            print(f"🔄 Progress: {mb_cur:.1f}/{mb_tot:.1f} MB ({per:.1f}%)")
            await msg.edit_text(txt)
            
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            pass