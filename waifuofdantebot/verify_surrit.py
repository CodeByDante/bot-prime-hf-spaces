import yt_dlp
import json

urls = [
    "https://surrit.com/ed92d56f-9e55-4fdc-94b5-fcec4a0fb4d9/1080p/video.m3u8",
    "https://surrit.com/ed92d56f-9e55-4fdc-94b5-fcec4a0fb4d9/720p/video.m3u8"
]

ydl_opts = {'quiet': True, 'nocheckcertificate': True}

print("Running YT-DLP Check...")
for u in urls:
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(u, download=False)
            print(f"\n--- URL: {u} ---")
            print(f"ID: {info.get('id')}")
            print(f"Webpage URL: {info.get('webpage_url')}")
            print(f"Original URL: {info.get('original_url')}")
    except Exception as e:
        print(f"Error {u}: {e}")
