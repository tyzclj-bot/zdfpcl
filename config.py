import os
from dotenv import load_dotenv

load_dotenv()

# DeepSeek API Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# QuickBooks Configuration (Placeholder)
QUICKBOOKS_CLIENT_ID = os.getenv("QUICKBOOKS_CLIENT_ID")
QUICKBOOKS_CLIENT_SECRET = os.getenv("QUICKBOOKS_CLIENT_SECRET")
QUICKBOOKS_REALM_ID = os.getenv("QUICKBOOKS_REALM_ID")
QUICKBOOKS_ENV = os.getenv("QUICKBOOKS_ENV", "sandbox")  # sandbox or production
