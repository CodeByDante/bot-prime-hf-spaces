import urllib.request

req = urllib.request.Request('https://hentaila.com/media/akane-wa-tsumare-somerareru/1', headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    with open('scratch_html.txt', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Done")
except Exception as e:
    print(e)
