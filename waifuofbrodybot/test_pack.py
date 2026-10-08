
from utils import get_random_pack_image
import os

print("Testing Pack Selection...")

# Test Specific
img = get_random_pack_image("tetas")
print(f"Propuesta Tetas: {img}")
if img and "tetas" in img: print("✅ Test Tetas OK")
else: print("❌ Test Tetas Failed")

# Test General
img_g = get_random_pack_image("general")
print(f"Propuesta General: {img_g}")
if img_g: print("✅ Test General OK")
else: print("❌ Test General Failed")

# Test Empty
img_e = get_random_pack_image("culos")
print(f"Propuesta Culos (Empty): {img_e}")
if img_e is None: print("✅ Test Empty OK")
else: print("❌ Test Empty Failed (Should be None)")
