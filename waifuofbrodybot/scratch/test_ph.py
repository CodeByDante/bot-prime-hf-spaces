import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from curl_cffi.requests import AsyncSession
import re
import html
from utils import load_cookies_dict, sel_cookie

async def main():
    # Let's use the active video from user's browser state
    url = "https://es.pornhub.com/view_video.php?viewkey=6713ce23ae69b"
    cookies_dict = load_cookies_dict(sel_cookie(url))
    print("Using cookies path:", sel_cookie(url))
    print("Cookies loaded count:", len(cookies_dict))
    
    async with AsyncSession(impersonate='chrome', cookies=cookies_dict) as s:
        r = await s.get(url)
        print("Status Code:", r.status_code)
        t = r.text
        
        # Save HTML to examine
        with open("ph_test.html", "w", encoding="utf-8") as f:
            f.write(t)
            
        print("HTML length:", len(t))
        
        # Search for m3u8
        m3u8_matches = re.findall(r'https?://[^\s"\'\\<>]+?\.m3u8[^\s"\'\\<>]*', t)
        print("Direct M3U8 matches count:", len(m3u8_matches))
        for m in m3u8_matches[:5]:
            print(m)
            
        # Search for flashvars or mediaDefinitions
        media_defs = re.findall(r'mediaDefinitions[^\n]*', t)
        print("\nmediaDefinitions lines:")
        for md in media_defs[:5]:
            print(md[:300])

        # Search for variable flashvars
        flashvars = re.findall(r'var\s+flashvars\s*=[^\n]*', t)
        print("\nflashvars lines:")
        for fv in flashvars[:5]:
            print(fv[:300])

if __name__ == "__main__":
    asyncio.run(main())
