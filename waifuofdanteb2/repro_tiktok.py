import asyncio
import aiohttp
import json

URL = "https://www.tiktok.com/@entitydante/photo/7557919556937731383"

async def get_cobalt_link(url, quality='1080'):
    try:
        api_url = "https://api.cobalt.tools/api/json"
        c_qual = "1080"
        
        payload = {
            "url": url,
            "vQuality": c_qual,
            "isAudioOnly": False,
            "noTTWatermark": True
        }
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        
        print(f"🧬 Cobalt Request: {payload}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as resp:
                data = await resp.json()
                print(f"Cobalt Response: {data}")
                
                if 'url' in data:
                    return data['url']
                elif 'picker' in data:
                     for p in data['picker']:
                         if 'url' in p: return p['url']
    except Exception as e:
        print(f"❌ Error Cobalt: {e}")
    return None

if __name__ == "__main__":
    result = asyncio.run(get_cobalt_link(URL))
    print(f"Result URL: {result}")
