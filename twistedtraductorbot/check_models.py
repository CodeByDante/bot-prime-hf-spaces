from google import genai
import os

api_key = "AIzaSyDl7RbV8tI4gFD5Fy7vcoqtP_phTqh14v0"

try:
    client = genai.Client(api_key=api_key)
    print("Checking available models...")
    
    # List models (using v1beta method if needed, or standard)
    # The new SDK structure might differ, commonly it's client.models.list()
    
    # We'll try the standard way for this SDK
    for model in client.models.list():
        print(f"Found model: {model.name}")
        
except Exception as e:
    print(f"Error listing models: {e}")
