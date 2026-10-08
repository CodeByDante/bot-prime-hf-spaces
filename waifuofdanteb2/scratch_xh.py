import cloudscraper
import re

scraper = cloudscraper.create_scraper()
url = 'https://es.xhamster.com/creators/nipple-stock/shorts'
t = scraper.get(url).text
print("xhcdn in t:", 'xhcdn' in t)
matches = re.findall(r'https?://[^\s"\'<>]+?\.m3u8', t)
print("Matches:", matches)
