import asyncio
import sys
import os

# Add parent directory to sys.path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from downloader import get_xvideos_link

async def test_integration():
    url = "https://www.xvideos.es/video.uaeppioa2d8/se_folla_a_joven_de_21_anos_despues_de_la_disco_sexo_en_auto_publico"
    print("Testing get_xvideos_link with URL:", url)
    m3u8_url, title = await get_xvideos_link(url)
    print("RESULT:")
    print("m3u8_url:", m3u8_url)
    print("title:", title)
    
    if m3u8_url and "hls.m3u8" in m3u8_url and "se folla a joven de 21" in title:
        print("\n✅ Verification Successful!")
    else:
        print("\n❌ Verification Failed!")

if __name__ == "__main__":
    asyncio.run(test_integration())
