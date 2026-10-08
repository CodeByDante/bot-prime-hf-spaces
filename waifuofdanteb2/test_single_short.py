import yt_dlp
ydl_opts = {'quiet': True}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info('https://es.xhamster.com/shorts/need-ass-xhcnfbl', download=False)
    for f in info.get('formats', []):
        if 'm3u8' in f.get('url', ''):
            print(f.get('url'))
            break
