import asyncio, re
from curl_cffi.requests import AsyncSession

async def main():
    url = 'https://es.xhamster.com/videos/ultra-motherly-voluptuous-lady-6-xhK1Uvx'
    async with AsyncSession(impersonate='chrome') as s:
        r = await s.get(url)
        print('Status:', r.status_code)
        match_title = re.search(r'<title[^>]*>(.*?)</title>', r.text, re.IGNORECASE)
        if match_title:
            t = match_title.group(1).replace(' - xHamster', '').strip()
            print('Title:', t)
asyncio.run(main())
