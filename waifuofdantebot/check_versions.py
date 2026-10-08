import sys
import shutil

try:
    import yt_dlp
    print(f"yt-dlp version: {yt_dlp.version.__version__}")
except ImportError:
    print("yt-dlp not installed in python env")

gdl = shutil.which("gallery-dl")
print(f"gallery-dl path: {gdl}")

# Also try running gallery-dl command just in case it's in a local folder
import subprocess
try:
    subprocess.run(["gallery-dl", "--version"], check=False)
except FileNotFoundError:
    print("gallery-dl command not found")

import os
if os.path.exists("bin/gallery-dl.exe"):
    print("gallery-dl found in bin/")
if os.path.exists("gallery-dl.exe"):
    print("gallery-dl found in root")
