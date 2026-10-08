import urllib.request
import re

req = urllib.request.Request('https://www.mp4upload.com/embed-58800c5xeii3.html', headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    match = re.search(r'src:\s*\"([^\"]+\.mp4)\"', html)
    if match:
        print('Found:', match.group(1))
    else:
        print('Not found. HTML preview:', html[:500])
except Exception as e:
    print('Error:', e)
