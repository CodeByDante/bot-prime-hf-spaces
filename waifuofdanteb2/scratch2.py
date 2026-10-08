import requests
import re

url = 'https://www.fireload.com/e3040cd8cf17853d'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
r = requests.get(url, headers=headers)
print("Looking for JS...")
# find all scripts
scripts = re.findall(r'<script[^>]*>(.*?)</script>', r.text, re.DOTALL | re.IGNORECASE)
for i, s in enumerate(scripts):
    if 'function' in s or 'dlink' in s:
        print(f"--- Script {i} ---")
        print(s.strip()[:500])
