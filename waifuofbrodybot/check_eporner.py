import aiohttp
import asyncio

async def check_url():
    url = "https://www.eporner.com/dload/gUfgGJfDswu/1080/15012343-1080p.mp4"
    print(f"Checking URL: {url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            print(f"Status: {resp.status}")
            print(f"Content-Type: {resp.headers.get('Content-Type')}")
            if resp.status != 200:
                print("URL is not accessible.")
            else:
                print("URL is accessible.")
                content = await resp.read()
                print(f"Content-Length: {len(content)}")

if __name__ == "__main__":
    asyncio.run(check_url())
