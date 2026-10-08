import asyncio
from curl_cffi.requests import AsyncSession
import re
import json

async def main():
    async with AsyncSession(impersonate='chrome') as s:
        r = await s.get('https://es.xhamster.com/videos/need-ass-xhcnfbl')
        t = r.text
        m1 = re.search(r'window\.initials\s*=\s*(\{.*?\});', t)
        if m1:
            data = json.loads(m1.group(1))
            open('xh_vid_json.json', 'w', encoding='utf-8').write(json.dumps(data, indent=2))
            print("initials found in video page!")
        else:
            print("initials not found in video page")

if __name__ == "__main__":
    asyncio.run(main())
