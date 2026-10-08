
import requests

url = "https://www.facebook.com/share/r/1DYog1F7xE/"
try:
    # Use a user-agent to avoid immediate blocking, though FB is tough
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.head(url, allow_redirects=True, headers=headers, timeout=10)
    print(f"Initial URL: {url}")
    print(f"Final URL: {response.url}")
    
    # Also try GET if HEAD doesn't give the full path (sometimes HEAD is limited)
    if "share/r" in response.url:
         print("HEAD didn't resolve fully, trying GET...")
         response = requests.get(url, headers=headers, timeout=10)
         print(f"GET Final URL: {response.url}")

except Exception as e:
    print(f"Error: {e}")
