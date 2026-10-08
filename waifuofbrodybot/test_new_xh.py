import asyncio
from curl_cffi.requests import AsyncSession
import re
import json

async def get_xhamster_link(url):
    try:
        async with AsyncSession(impersonate='chrome') as s:
            r = await s.get(url)
            if r.status_code == 200:
                t = r.text
                
                if "/creators/" in url and "/shorts" in url:
                    match_short = re.search(r'href="(https://[^\"\']+/shorts/[^\"\']+)"', t)
                    if match_short:
                        short_url = match_short.group(1)
                        print("Found short URL:", short_url)
                        r2 = await s.get(short_url)
                        if r2.status_code == 200:
                            t = r2.text
                
                m3u8_url = None
                
                match_json = re.search(r'window\.(?:initials|__INITIAL_STATE__)\s*=\s*(\{.*?\});', t)
                if match_json:
                    try:
                        data = json.loads(match_json.group(1))
                        data_str = json.dumps(data)
                        match_m3u8 = re.search(r'(https?://[^\s\"\']+\.m3u8)', data_str)
                        if match_m3u8:
                            m3u8_url = match_m3u8.group(1)
                    except Exception as e:
                        print("JSON parse error:", e)
                
                if not m3u8_url:
                    match_url = re.search(r'(https?://[^\s\"\']+\.m3u8)', t)
                    if match_url:
                        m3u8_url = match_url.group(1).replace('\\/', '/')
                
                if not m3u8_url:
                    match_url = re.search(r'(https?:\/\/[^\s\"\']+\.m3u8)', t)
                    if match_url:
                        m3u8_url = match_url.group(1).replace('\\/', '/')
                        
                title = "Video de XHamster"
                match_title = re.search(r'<title[^>]*>(.*?)</title>', t, re.IGNORECASE)
                if match_title:
                    title = match_title.group(1).split('| xHamster')[0].replace('- xHamster', '').strip()
                
                return m3u8_url, title
    except Exception as e:
        print(f"Error XHamster M3U8: {e}")
    return None, None

async def main():
    u, t = await get_xhamster_link('https://es.xhamster.com/creators/nipple-stock/shorts')
    print("Playlist result:", u, t)
    
    u2, t2 = await get_xhamster_link('https://es.xhamster.com/shorts/need-ass-xhcnfbl')
    print("Short result:", u2, t2)
    
    u3, t3 = await get_xhamster_link('https://es.xhamster.com/videos/ultra-motherly-voluptuous-lady-6-xhK1Uvx')
    print("Normal video result:", u3, t3)

if __name__ == "__main__":
    asyncio.run(main())
