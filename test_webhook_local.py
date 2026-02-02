
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
# 这里填入你的 Supabase Edge Function URL
# 可以在 Supabase Dashboard -> Edge Functions 找到
# 例如: https://ezbzgduznostwxkbufya.supabase.co/functions/v1/lemon_squeezy_webhook
FUNCTION_URL = "https://ezbzgduznostwxkbufya.supabase.co/functions/v1/lemon_squeezy_webhook"

# 你的 Webhook Secret (如果你在 Function 中启用了签名验证，这里必须匹配)
WEBHOOK_SECRET = "test_secret" 

# 模拟 Lemon Squeezy 的 Webhook Payload
# 关键字段是 meta.event_name 和 meta.custom_data.user_id
payload = {
    "meta": {
        "event_name": "order_created",
        "custom_data": {
            "user_id": "你的_USER_ID_在这里"  # ⚠️ 请替换为你注册的一个真实 User ID
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
    
    # 注意：如果你的 Function 启用了签名验证，你需要在这里生成真实的 HMAC SHA256 签名
    # 为了简化测试，你可以暂时在 Edge Function 中注释掉签名验证部分，或者使用真实密钥生成签名
    
    headers = {
        "Content-Type": "application/json",
        "x-signature": "mock_signature" # 如果没有正确签名，可能会返回 401
    }

    try:
        response = requests.post(FUNCTION_URL, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("⚠️ 请先确保你已经部署了 Edge Function 并且替换了脚本中的 user_id")
    # test_webhook() # 取消注释来运行
