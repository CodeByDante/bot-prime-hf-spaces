from google import genai
from google.genai import types

api_key = "AIzaSyDl7RbV8tI4gFD5Fy7vcoqtP_phTqh14v0"
client = genai.Client(api_key=api_key)

models_to_test = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-2.0-flash-exp", # Experimental
    "gemini-1.0-pro" # Old reliable
]

print("Starting Model Test...")

for model_name in models_to_test:
    print(f"\nTesting: {model_name}")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=["Hello, say hi."]
        )
        print(f"✅ SUCCESS with {model_name}!")
        print(f"Response: {response.text}")
        break # Found a working one
    except Exception as e:
        print(f"❌ FAILED {model_name}: {e}")
