import asyncio
from curl_cffi.requests import AsyncSession
import re

async def main():
    async with AsyncSession(impersonate='chrome') as s:
        r = await s.get('https://es.xhamster.com/shorts/need-ass-xhcnfbl')
        t = r.text
        m = re.findall(r'https://[^\"\']+\.m3u8', t)
        print("m3u8 in short page:", m)

if __name__ == "__main__":
    asyncio.run(main())
