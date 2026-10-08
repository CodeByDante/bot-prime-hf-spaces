import re
import time

def verify_logic(l_u):
    print(f"Testing URL: {l_u}")
    is_direct = any(x in l_u for x in ['mediafire.com', 'yourupload.com', 'mp4upload.com', 'rule34video.com/get_file/'])
    
    # Eporner Direct Check
    eporner_id = None
    if "eporner.com" in l_u and "/dload/" in l_u:
        is_direct = True
        try:
            # URL format: .../dload/VIDEO_ID/...
            parts = l_u.split('/dload/')
            if len(parts) > 1:
                eporner_id = parts[1].split('/')[0]
        except: pass

    if not is_direct and re.search(r'\.(mp4|mkv|webm|avi|mov)(/|\?|$)', l_u, re.I): is_direct = True

    if is_direct:
        # Use Eporner ID if available, otherwise fallback to timestamp
        final_id = f"eporner_{eporner_id}" if eporner_id else f"direct_{int(time.time())}"
        print(f"Final ID: {final_id}")
        return final_id
    else:
        print("Not detected as direct.")
        return None

# Test Case
url = "https://www.eporner.com/dload/2pBe2ZZDqtG/720/15686822-720p.mp4"
extracted_id = verify_logic(url)

expected = "eporner_2pBe2ZZDqtG"
if extracted_id == expected:
    print("✅ SUCCESS: ID extracted correctly.")
else:
    print(f"❌ FAILURE: Expected {expected}, got {extracted_id}")
