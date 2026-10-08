import os
import re
import argparse

def remove_kemono_ids(root_dir):
    """
    Recursively scans the directory and renames folders by removing 
    patterns like ' [123456]' or '[123456]' from the end of their names.
    """
    if not os.path.isdir(root_dir):
        print(f"Error: The directory '{root_dir}' does not exist.")
        return

    # Pattern: optional space, followed by '[', then 1 or more digits, then ']'
    # We use $ to make sure it's at the end of the folder name, or we can just 
    # replace it anywhere. It's safer to just replace it anywhere if it matches.
    # Pattern explanation: \s* matches spaces, \[\d+\] matches [12345]
    pattern = re.compile(r'\s*\[\d+\]\s*$')

    # We walk bottom-up so that renaming a parent folder doesn't break the paths for its children
    renamed_count = 0
    
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        # Rename files first
        for filename in filenames:
            name, ext = os.path.splitext(filename)
            if pattern.search(name):
                new_name = pattern.sub('', name).strip() + ext
                
                if not new_name or new_name == ext:
                    continue
                    
                old_path = os.path.join(dirpath, filename)
                new_path = os.path.join(dirpath, new_name)
                
                if not os.path.exists(new_path):
                    try:
                        os.rename(old_path, new_path)
                        print(f"Renamed file: '{filename}' -> '{new_name}'")
                        renamed_count += 1
                    except Exception as e:
                        print(f"Failed to rename file '{filename}': {e}")

        # Rename folders
        for dirname in dirnames:
            if pattern.search(dirname):
                new_name = pattern.sub('', dirname).strip()
                
                if not new_name:
                    continue

                old_path = os.path.join(dirpath, dirname)
                new_path = os.path.join(dirpath, new_name)

                if os.path.exists(new_path):
                    print(f"Cannot rename folder '{dirname}' to '{new_name}' because the destination already exists.")
                    continue

                try:
                    os.rename(old_path, new_path)
                    print(f"Renamed folder: '{dirname}' -> '{new_name}'")
                    renamed_count += 1
                except Exception as e:
                    print(f"Failed to rename folder '{dirname}': {e}")

    print(f"\nScan complete. Total folders renamed: {renamed_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove Kemono post IDs (e.g. '[12345]') from folder names.")
    parser.add_argument("path", nargs='?', default=".", help="The root directory to scan (default is current directory)")
    
    args = parser.parse_args()
    
    print(f"Starting to scan: {os.path.abspath(args.path)}\n")
    remove_kemono_ids(args.path)
