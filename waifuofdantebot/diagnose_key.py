import requests
import json

api_key = "AIzaSyDl7RbV8tI4gFD5Fy7vcoqtP_phTqh14v0"
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

print(f"Testing Key: {api_key[:10]}...")

try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print("Response Body:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")
