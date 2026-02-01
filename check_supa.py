
import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

print(f"Testing connection to: {url}")
# print(f"Key: {key}")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}

try:
    # Try to fetch user_credits structure (even if empty) to check auth
    # Or just health check if available, but REST endpoint is better to test Key
    # We'll try to select from a non-existent table or just root to see if we get 401
    response = requests.get(f"{url}/rest/v1/", headers=headers)
    print(f"Root Status: {response.status_code}")
    
    # Try to query the version or something public if possible, 
    # but usually we check if we get a 401 (Unauthorized) or 403 (Forbidden) vs 200 or 404
    # If key is invalid, we likely get 401 or 403.
    
    # Let's try to access the user_credits table which we know exists
    response = requests.get(f"{url}/rest/v1/user_credits?select=count", headers=headers)
    print(f"Table Access Status: {response.status_code}")
    print(f"Response: {response.text}")

except Exception as e:
    print(f"Error: {e}")
