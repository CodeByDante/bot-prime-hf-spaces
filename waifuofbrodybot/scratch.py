import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget

l_u = 'https://missav.ws/en/huntc-262'

# Target user agent for Chrome 110
chrome_110_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'

y_o = {
    'verbose': True,
    'quiet': False, 
    'force_ipv4': False, 
    'nocheckcertificate': True, 
    'cookiefile': 'cookies/cookies_jav.txt',
    'http_headers': {
        'Referer': 'https://missav.ws/',
        'User-Agent': chrome_110_ua,
    }
}

try:
    y_o['impersonate'] = ImpersonateTarget.from_str('chrome-110')
except Exception as e_imp:
    print(f"Error setting yt-dlp impersonate: {e_imp}")
    y_o['extractor_args'] = {'generic': ['impersonate=chrome']}

try:
    with yt_dlp.YoutubeDL(y_o) as ydl:
        y_i = ydl.extract_info(l_u, download=False)
        print("Success! Title:", y_i.get('title'))
except Exception as e:
    import traceback
    traceback.print_exc()
