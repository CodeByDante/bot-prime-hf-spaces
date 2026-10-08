import re

t = open('xh_test.html', encoding='utf-8').read()
matches = re.findall(r'https://[^\"\']*xhcdn[^\"\']*', t)
for m in set(matches):
    print(m)
