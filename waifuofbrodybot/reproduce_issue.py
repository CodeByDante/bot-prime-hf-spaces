import aiohttp
import asyncio
import sys

URL = "https://www.eporner.com/dload/gUfgGJfDswu/1080/150"

async def check_url():
    print(f"Checking URL: {URL}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(URL, allow_redirects=True) as resp:
                print(f"Status: {resp.status}")
                print(f"Final URL: {resp.url}")
                print(f"Content-Type: {resp.headers.get('Content-Type')}")
                print(f"Content-Disposition: {resp.headers.get('Content-Disposition')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_url())
