import yt_dlp
import json

ydl_opts = {'quiet': True, 'extract_flat': True}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info('https://es.xhamster.com/creators/nipple-stock/shorts', download=False)
    if 'entries' in info and len(info['entries']) > 0:
        first = info['entries'][0]
        open('first_entry.json', 'w').write(json.dumps(first, indent=2))
        print("URL inside yt-dlp entry:", first.get('url'))
