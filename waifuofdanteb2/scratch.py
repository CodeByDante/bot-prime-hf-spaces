import requests
import re

url = 'https://www.fireload.com/e3040cd8cf17853d/1201_1_SUB.mp4?pt=TDBKQ1RFMHpRVWRRWlhCbGIxRTVlbWR4Unk5c1p6MDlPaUx6L2Z1UTFlQnBJL2F1aWJlNms1UT0%3D'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
r = requests.get(url, headers=headers)
print("Status:", r.status_code)
print("HTML snippet:", r.text[:300])

match_btn = re.search(r'href="([^"]+)"\s+id="downloadButton"', r.text)
if match_btn:
    print("Download Button:", match_btn.group(1))
else:
    print("No downloadButton found")

# Look for any url containing /download/ or similar
print("Links found:", re.findall(r'href="([^"]+)"', r.text)[:5])
