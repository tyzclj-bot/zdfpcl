
import os
from gotrue import SyncGoTrueClient
from postgrest import SyncPostgrestClient

class SupabaseManager:
    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        
        # Initialize Auth Client
        self.auth = SyncGoTrueClient(
            url=f"{url}/auth/v1",
            headers=self.headers,
            storage_key="supabase.auth.token"
        )

    def get_db_client(self, access_token=None):
        """
        Get a Postgrest client. 
        If access_token is provided, use it for Authorization (RLS).
        Otherwise, use the anon key.
        """
        headers = self.headers.copy()
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
            
        return SyncPostgrestClient(
            base_url=f"{self.url}/rest/v1",
            headers=headers
        )

    def sign_up(self, email, password):
        return self.auth.sign_up({
            "email": email, 
            "password": password
        })

    def sign_in(self, email, password):
        return self.auth.sign_in_with_password({
            "email": email, 
            "password": password
        })

    def sign_out(self):
        return self.auth.sign_out()
        
    def get_user_credits(self, user_id, access_token):
        """Get remaining credits for a user"""
        db = self.get_db_client(access_token)
        try:
            # First try to get existing record
            response = db.from_("user_credits").select("credits_remaining").eq("user_id", user_id).execute()
            
            if response.data:
                return response.data[0]['credits_remaining']
            else:
                # If no record exists, this might be a new user who wasn't caught by a trigger (fallback)
                # Or we can insert a default record here if we have permissions
                # For now, let's assume 0 or handle it gracefully
                return 0
        except Exception as e:
            print(f"Error fetching credits: {e}")
            return 0

    def decrement_credits(self, user_id, access_token):
        """Decrement 1 credit from user"""
        db = self.get_db_client(access_token)
        # We need to call a stored procedure or just update. 
        # Ideally use an RPC 'decrement_credit' to be safe, but simple update is fine for MVP.
        # Fetch current first
        current = self.get_user_credits(user_id, access_token)
        if current > 0:
            db.from_("user_credits").update({"credits_remaining": current - 1}).eq("user_id", user_id).execute()
            return True
        return False

    def log_invoice(self, user_id, invoice_data, access_token):
        """Log the successful extraction to history"""
        db = self.get_db_client(access_token)
        record = {
            "user_id": user_id,
            "vendor_name": invoice_data.get("vendor_name"),
            "total_amount": invoice_data.get("total_amount"),
            "currency": invoice_data.get("currency", "CNY"),
            "invoice_number": invoice_data.get("invoice_number")
        }
        db.from_("invoice_history").insert(record).execute()
