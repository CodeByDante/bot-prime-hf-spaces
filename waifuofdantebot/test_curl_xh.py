import asyncio, re
from curl_cffi.requests import AsyncSession

async def main():
    url = 'https://es.xhamster.com/videos/ultra-motherly-voluptuous-lady-6-xhK1Uvx'
    async with AsyncSession(impersonate='chrome') as s:
        r = await s.get(url)
        print('Status:', r.status_code)
        match = re.search(r'(https://[^\"\']+\.m3u8)', r.text)
        if match:
            print('Found:', match.group(1))
        else:
            print('Not found')
asyncio.run(main())
