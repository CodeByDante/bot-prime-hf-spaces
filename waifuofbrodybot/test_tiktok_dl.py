import asyncio
import aiohttp
import json

URL = "https://www.tiktok.com/@entitydante/photo/7557919556937731383"

async def test_cobalt_v10():
    print(f"Testing Cobalt v10 with URL: {URL}")
    
    api_url = "https://api.cobalt.tools"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    payload = {
        "url": URL,
        "videoQuality": "1080"
    }
    
    print(f"Payload: {json.dumps(payload)}")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(api_url, json=payload, headers=headers) as resp:
                print(f"Status: {resp.status}")
                text = await resp.text()
                print(f"Response: {text[:500]}") # Truncate log
                
                if resp.status == 200:
                    data = json.loads(text)
                    if 'url' in data or 'picker' in data or 'status' in data:
                        print("✅ Cobalt v10 Success!")
                else:
                    print("❌ Cobalt v10 Failed.")
                    
        except Exception as e:
            print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_cobalt_v10())
