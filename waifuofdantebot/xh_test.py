import asyncio
from curl_cffi.requests import AsyncSession

async def main():
    async with AsyncSession(impersonate='chrome') as s:
        r = await s.get('https://es.xhamster.com/creators/nipple-stock/shorts')
        with open('xh_test.html', 'w', encoding='utf-8') as f:
            f.write(r.text)
        print("Done")

if __name__ == "__main__":
    asyncio.run(main())
