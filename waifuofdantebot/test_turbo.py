import subprocess

cmd = [
    r'c:\Users\Gonzalo\Desktop\waifu\waifuofbrodybot\tools\N_m3u8DL-RE.exe',
    'https://surrit.com/a321f1a9-03bc-4ee0-bfb3-bcd55e6a53be/playlist.m3u8',
    '-H', 'Referer: https://missav.ws/',
    '-H', 'Origin: https://missav.ws',
    '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
    '--save-name', 'test_turbo',
    '--save-dir', '.',
    '--tmp-dir', 'tmp',
]

res = subprocess.run(cmd, capture_output=True, text=True)
print("STDOUT:")
print(res.stdout)
print("STDERR:")
print(res.stderr)
