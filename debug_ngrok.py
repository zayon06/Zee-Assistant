import httpx
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("OLLAMA_HOST")
print(f"Testing URL: {url}/api/tags")

headers = {'ngrok-skip-browser-warning': 'true'}
try:
    with httpx.Client(headers=headers) as client:
        resp = client.get(f"{url}/api/tags")
        print(f"Status Code: {resp.status_code}")
        print(f"Body: {resp.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
