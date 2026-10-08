
import yt_dlp

url = "https://www.facebook.com/share/r/1DYog1F7xE/"

opts = {
    'quiet': True,
    # 'extract_flat': True, # REMOVED to allow full resolution
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
}

try:
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        print(f"I found: {info.get('webpage_url')}")
        print(f"ID: {info.get('id')}")
        
except Exception as e:
    print(f"Error: {e}")
