import yt_dlp

url = 'https://es.xhamster.com/creators/nipple-stock/shorts'
ydl_opts = {}
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        print("Success!")
        print("Title:", info.get('title'))
        print("Entries:", len(info.get('entries', [])) if 'entries' in info else 0)
        
        # if entries, get first url
        if 'entries' in info and info['entries']:
            print("First video m3u8 or formats:", [f.get('url') for f in info['entries'][0].get('formats', []) if 'm3u8' in str(f.get('url'))])
except Exception as e:
    print("Error:", e)
