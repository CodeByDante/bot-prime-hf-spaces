import urllib.request
import re

req = urllib.request.Request('https://hentaila.com/media/akane-wa-tsumare-somerareru/1', headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    # Search for all episodes list if it exists
    episodes = re.findall(r'href="([^"]+)"[^>]*>\s*Episodio \d+\s*<', html, re.IGNORECASE)
    print("Episodes from list:", episodes)
    
    # Or search for the Next button
    next_btn = re.search(r'href="([^"]+)"[^>]*>\s*Siguiente', html, re.IGNORECASE)
    if next_btn:
        print("Siguiente URL:", next_btn.group(1))
    else:
        print("Siguiente URL no encontrada")
except Exception as e:
    print(e)
