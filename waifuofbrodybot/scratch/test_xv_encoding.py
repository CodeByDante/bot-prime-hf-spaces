import asyncio
from curl_cffi.requests import AsyncSession

async def main():
    url = "https://www.xvideos.es/video.uaeppioa2d8/se_folla_a_joven_de_21_anos_despues_de_la_disco_sexo_en_auto_publico"
    async with AsyncSession(impersonate='chrome') as s:
        r = await s.get(url)
        print("Response encoding:", getattr(r, 'encoding', None))
        print("Response charset:", getattr(r, 'charset', None))
        
        # Test UTF-8 decoding
        try:
            val_utf8 = r.content.decode('utf-8')
            print("UTF-8 decoded title snippet:")
            import re
            m = re.search(r'<title[^>]*>(.*?)</title>', val_utf8, re.I)
            if m:
                print("Title UTF-8:", repr(m.group(1)))
        except Exception as e:
            print("UTF-8 failed:", e)

        # Test ISO-8859-1 decoding
        try:
            val_iso = r.content.decode('iso-8859-1')
            print("ISO-8859-1 decoded title snippet:")
            import re
            m = re.search(r'<title[^>]*>(.*?)</title>', val_iso, re.I)
            if m:
                print("Title ISO-8859-1:", repr(m.group(1)))
        except Exception as e:
            print("ISO-8859-1 failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
