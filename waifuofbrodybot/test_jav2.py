import re

html = """eval(function(p,a,c,k,e,d){e=function(c){return c.toString(36)};if(!''.replace(/^/,String)){while(c--){d[c.toString(a)]=k[c]||c.toString(a)}k=[function(e){return d[e]}];e=function(){return'\\w+'};c=1};while(c--){if(k[c]){p=p.replace(new RegExp('\\b'+e(c)+'\\b','g'),k[c])}}return p}('f=\\'8://7.6/5-4-3-2-1/e.0\\';d=\\'8://7.6/5-4-3-2-1/c/9.0\\';b=\\'8://7.6/5-4-3-2-1/a/9.0\\';',16,16,'m3u8|bcd55e6a53be|bfb3|4ee0|03bc|a321f1a9|com|surrit|https|video|1080p|source1280|720p|source842|playlist|source'.split('|'),0,{}))"""

def find_surrit_uuid(html_text):
    match = re.search(r"'([^']+)'\.split\('\|'\)", html_text)
    if not match: return None
    words = match.group(1).split('|')
    
    match_p = re.search(r"\}\('(.*?)', *\d+, *\d+,", html_text)
    if match_p:
        p = match_p.group(1)
        # convert base 36
        def base36(i):
            digits = "0123456789abcdefghijklmnopqrstuvwxyz"
            res = ""
            while i > 0:
                res = digits[i % 36] + res
                i //= 36
            return res or "0"
            
        for i, word in enumerate(words):
            if not word: continue
            idx = base36(i)
            p = re.sub(r'\b' + idx + r'\b', word, p)
            
        m3u8_links = re.findall(r'(https?://surrit\.com[^\s\'"]+\.m3u8)', p)
        if m3u8_links:
            return m3u8_links[0]
            
    return None

print(find_surrit_uuid(html))
