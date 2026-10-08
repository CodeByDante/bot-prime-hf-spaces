import asyncio
import urllib.request

def test_fetch():
    # Let's get the HLS URL from the page first
    # We can hardcode the one we just got or fetch it dynamically
    hls_url = "https://hls-cdn77.xvideos-cdn.com/SEu50pylUIvAFLjHId1vuw==,1784847147/89b72b4c-ab38-4c7c-8c09-1072257af480/0/hls.m3u8"
    try:
        req = urllib.request.Request(hls_url)
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            print("Successfully fetched without any special client/headers!")
            print(html[:200])
    except Exception as e:
        print("Failed to fetch with urllib:", e)

if __name__ == "__main__":
    test_fetch()
