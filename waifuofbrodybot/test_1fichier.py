import urllib.request
import urllib.parse
import re

url = 'https://1fichier.com/?hhkny06tj2exkk50uu2s'
req1 = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp1 = urllib.request.urlopen(req1)
cookie = resp1.headers.get('Set-Cookie', '')
print('Cookie:', cookie)

data = urllib.parse.urlencode({}).encode('utf-8')
req2 = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0', 'Cookie': cookie})
try:
    resp2 = urllib.request.urlopen(req2)
    html2 = resp2.read().decode('utf-8')
    if 'You must wait' in html2 or 'You have to wait' in html2:
        print('Wait enforced by server')
        print(html2[:500])
    else:
        print('Success!')
        match = re.search(r'href="([^"]+)" class="btn-general btn-orange"', html2)
        if match:
            print('Download link:', match.group(1))
        else:
            print('Could not find link. HTML size:', len(html2))
            with open('test_1fichier2.html', 'w', encoding='utf-8') as f:
                f.write(html2)
except Exception as e:
    print('Error:', e)
