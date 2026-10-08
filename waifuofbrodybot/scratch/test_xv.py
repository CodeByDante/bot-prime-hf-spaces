import asyncio
import re
import html
from curl_cffi.requests import AsyncSession

async def main():
    url = "https://www.xvideos.es/video.uaeppioa2d8/se_folla_a_joven_de_21_anos_despues_de_la_disco_sexo_en_auto_publico"
    async with AsyncSession(impersonate='chrome') as s:
        r = await s.get(url)
        t = r.text
        
        m3u8_url = None
        match_hls = re.search(r"html5player\.setVideoHLS\s*\(\s*['\"](https?://[^'\"]+\.m3u8[^'\"]*)['\"]\s*\)", t)
        if not match_hls:
            match_hls = re.search(r"html5player\.setVideoHLS\s*\(\s*['\"](https?(?::\\/\\/|:\/\/)[^'\"]+\.m3u8[^'\"]*)['\"]\s*\)", t)
        
        if match_hls:
            m3u8_url = match_hls.group(1).replace('\\/', '/')
            
        title = "Video de XVideos"
        match_title_tag = re.search(r'<title[^>]*>(.*?)</title>', t, re.IGNORECASE)
        if match_title_tag:
            title = match_title_tag.group(1)
            # Case-insensitive split
            title = re.split(r'\s+-\s+xvideos', title, flags=re.IGNORECASE)[0].strip()
        else:
            match_player_title = re.search(r"html5player\.setVideoTitle\s*\(\s*['\"](.*?)['\"]\s*\)", t)
            if match_player_title:
                title = match_player_title.group(1)
                
        title = html.unescape(title).strip()
        
        print("Extracted M3U8 URL:", m3u8_url)
        print("Extracted Title:", title)
        print("Repr:", repr(title))

if __name__ == "__main__":
    asyncio.run(main())
