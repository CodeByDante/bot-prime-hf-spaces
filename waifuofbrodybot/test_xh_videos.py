import asyncio
from curl_cffi.requests import AsyncSession
import re

async def main():
    async with AsyncSession(impersonate='chrome') as s:
        r = await s.get('https://es.xhamster.com/videos/need-ass-xhcnfbl')
        t = r.text
        m = re.findall(r'https://[^\"\']+\.m3u8', t)
        print("Status:", r.status_code)
        print("m3u8 in videos page:", m)

if __name__ == "__main__":
    asyncio.run(main())
