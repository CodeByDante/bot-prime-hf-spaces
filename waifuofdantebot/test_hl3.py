import urllib.request
import re

req = urllib.request.Request('https://hentaila.com/media/kegareboshi/3', headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    servers = re.findall(r'server\s*:\s*"([^"]+)"\s*,\s*url\s*:\s*"([^"]+)"', html, re.IGNORECASE)
    print('Servers found:')
    for s, u in servers:
        print(s, '-', u.replace('\\/', '/'))
except Exception as e:
    print('Error:', e)
