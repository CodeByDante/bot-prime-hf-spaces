import os
import urllib.request
import urllib.parse

def fix_all_lfs_files():
    base_url = "https://huggingface.co/spaces/codebydante/waifuofbrodybot/resolve/main/"
    print("Scanning for Git LFS pointers to download...")
    count = 0
    for root, dirs, files in os.walk("."):
        if ".git" in root or ".venv" in root or "__pycache__" in root: 
            continue
        for name in files:
            filepath = os.path.join(root, name)
            try:
                with open(filepath, 'rb') as f:
                    header = f.read(50)
                if b"version https://git-lfs.github.com/spec/v1" in header:
                    rel_path = os.path.relpath(filepath, ".").replace('\\', '/')
                    url = base_url + urllib.parse.quote(rel_path)
                    print(f"Downloading {rel_path}...")
                    try:
                        urllib.request.urlretrieve(url, filepath)
                        print(f"Successfully downloaded {rel_path}")
                        count += 1
                    except Exception as e:
                        print(f"Error downloading {rel_path}: {e}")
            except Exception:
                pass
    print(f"Done. Fixed {count} LFS files.")

if __name__ == "__main__":
    fix_all_lfs_files()
