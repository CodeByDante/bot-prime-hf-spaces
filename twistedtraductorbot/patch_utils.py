import os

path = "utils.py"
if not os.path.exists(path):
    print("utils.py not found")
    exit(1)

with open(path, "rb") as f:
    content = f.read().decode("utf-8", "ignore")

# Replacement 1: Add --write-metadata
# Only if not already present
if "--write-metadata" not in content:
    old_cmd = '"--destination", tmp_dir,'
    new_cmd = '"--destination", tmp_dir,\n        "--write-metadata",'
    content = content.replace(old_cmd, new_cmd)

# Replacement 2: Return values (Specific function return)
# We need to be careful not to replace other returns
# The function ends with: return files, tmp_dir
# And: return [], None

if "return files, tmp_dir, metadata_text" not in content:
    # We target the context around the return to be safe
    old_return = 'return files, tmp_dir'
    new_return = 'return files, tmp_dir, metadata_text'
    # Use the context of the glob loop to ensure we are in the right place
    context_marker = 'files.extend(glob.glob(f"{tmp_dir}/**/*.{ext}", recursive=True))'
    
    if context_marker in content:
        # Add metadata logic
        new_logic = """files.extend(glob.glob(f"{tmp_dir}/**/*.{ext}", recursive=True))

        # Metadata Extraction
        metadata_text = ""
        try:
            import json
            import glob # ensure glob is available
            json_files = glob.glob(f"{tmp_dir}/**/*.json", recursive=True)
            for jf in json_files:
                try:
                    with open(jf, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Try to find content/text
                        text_found = data.get('content') or data.get('description') or data.get('title') or data.get('full_text') or ""
                        if text_found:
                            metadata_text = str(text_found).strip()
                            break
                except: continue
        except: pass"""
        
        content = content.replace(context_marker, new_logic)
        # Now replace the return ONLY in this function scope?
        # Since replace is global, we need to be careful.
        # But `return files, tmp_dir` is very specific to this function signature in this file.
        content = content.replace(old_return, new_return)

# Replacement 3: Error return
old_err_return = 'return [], None'
new_err_return = 'return [], None, None'
if old_err_return in content:
    # Check if we haven't already done it
    if new_err_return not in content:
        content = content.replace(old_err_return, new_err_return)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Utils.py patched successfully")
