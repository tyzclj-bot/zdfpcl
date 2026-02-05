
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
# Enter your Supabase Edge Function URL here
# Can be found in Supabase Dashboard -> Edge Functions
# E.g.: https://ezbzgduznostwxkbufya.supabase.co/functions/v1/lemon_squeezy_webhook
FUNCTION_URL = "https://ezbzgduznostwxkbufya.supabase.co/functions/v1/lemon_squeezy_webhook"

# Your Webhook Secret (Must match if signature verification is enabled in Function)
WEBHOOK_SECRET = "test_secret" 

# Mock Lemon Squeezy Webhook Payload
# Key fields are meta.event_name and meta.custom_data.user_id
payload = {
    "meta": {
        "event_name": "order_created",
        "custom_data": {
            "user_id": "YOUR_USER_ID_HERE"  # ⚠️ Please replace with a real User ID you registered
        }
    },
    "data": {
        "id": "123",
        "attributes": {
            "total": 1000,
            "currency": "USD",
            "status": "paid"
        }
    }
}

def test_webhook():
    print(f"Testing Webhook: {FUNCTION_URL}")
    
    # Note: If your Function has signature verification enabled, you need to generate a real HMAC SHA256 signature here
    # To simplify testing, you can temporarily comment out the signature verification in the Edge Function, or use a real key to generate the signature
    
    headers = {
        "Content-Type": "application/json",
        "x-signature": "mock_signature" # If not signed correctly, might return 401
    }

    try:
        response = requests.post(FUNCTION_URL, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("⚠️ Please ensure you have deployed the Edge Function and replaced the user_id in the script")
    # test_webhook() # Uncomment to run
