import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from curl_cffi.requests import AsyncSession
from utils import load_cookies_dict, sel_cookie
from downloader import get_pornhub_link

async def main():
    url = "https://es.pornhub.com/view_video.php?viewkey=ph5a2535e8b581c"
    cookies_dict = load_cookies_dict(sel_cookie(url))
    print("Using cookies path:", sel_cookie(url))
    print("Cookies loaded count:", len(cookies_dict))
    
    async with AsyncSession(impersonate='chrome', cookies=cookies_dict) as s:
        r = await s.get(url)
        print("Status Code:", r.status_code)
        t = r.text
        
        # Save HTML to examine
        with open("ph_test_2.html", "w", encoding="utf-8") as f:
            f.write(t)
            
        print("HTML length:", len(t))
        
        # Test function
        m3u8_url, title = await get_pornhub_link(url, 'best')
        print("RESULT:")
        print("m3u8_url:", m3u8_url)
        print("title:", title)

if __name__ == "__main__":
    asyncio.run(main())
