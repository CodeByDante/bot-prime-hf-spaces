import json
import re

d = open('xh_vid_json.json', encoding='utf-8').read()
matches = re.findall(r'https?://[^\s\"\']+\.m3u8', d)
if matches:
    print("Found direct match:", matches[0])
else:
    matches_escaped = re.findall(r'https?:\/\/[^\s\"\']+\.m3u8', d)
    if matches_escaped:
        print("Found escaped match:", matches_escaped[0].replace('\\/', '/'))
    else:
        print("No m3u8 found in json text!")
