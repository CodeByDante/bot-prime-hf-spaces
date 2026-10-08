import re
import json

t = open('xh_test.html', encoding='utf-8').read()

m1 = re.search(r'window\.initials\s*=\s*(\{.*?\});', t)
if m1:
    data = json.loads(m1.group(1))
    open('xh_json.json', 'w', encoding='utf-8').write(json.dumps(data, indent=2))
    print("Keys in initials:", data.keys())
