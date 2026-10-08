import asyncio, aiohttp, re

async def main():
    url = 'https://es.xhamster.com/videos/a-home-encounter-with-an-uninvited-voluptuous-xhx5p30'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'}
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=headers) as r:
            print('Status:', r.status)
            html = await r.text()
            print('HTML len:', len(html))
            match = re.search(r'(https://[^\"\']+\.m3u8)', html)
            if match:
                print('Found:', match.group(1))
            else:
                print('Not found')
asyncio.run(main())
