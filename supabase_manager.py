
import requests
import json
import secrets
import hashlib
import base64
from urllib.parse import urlencode

class SupabaseManager:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip('/')
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }

    def _get_headers(self, access_token=None):
        headers = self.headers.copy()
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    def sign_up(self, email, password):
        endpoint = f"{self.url}/auth/v1/signup"
        payload = {"email": email, "password": password}
        response = requests.post(endpoint, json=payload, headers=self.headers)
        
        if response.status_code not in [200, 201]:
             # Try to extract error message
             try:
                 err = response.json()
                 msg = err.get('msg') or err.get('message') or err.get('error_description') or response.text
             except:
                 msg = response.text
             raise Exception(f"Signup failed: {msg}")
             
        return self._parse_auth_response(response.json())

    def sign_in(self, email, password):
        endpoint = f"{self.url}/auth/v1/token?grant_type=password"
        payload = {"email": email, "password": password}
        response = requests.post(endpoint, json=payload, headers=self.headers)
        
        if response.status_code != 200:
            try:
                 err = response.json()
                 msg = err.get('msg') or err.get('message') or err.get('error_description') or response.text
            except:
                 msg = response.text
            raise Exception(f"Login failed: {msg}")
            
        return self._parse_auth_response(response.json())

    def sign_out(self, access_token=None):
        if not access_token:
            return
        endpoint = f"{self.url}/auth/v1/logout"
        requests.post(endpoint, headers=self._get_headers(access_token))

    def get_oauth_url(self, provider, redirect_to, fixed_verifier=None):
        """
        Generates the OAuth URL for the given provider using PKCE flow.
        Returns (auth_url, code_verifier)
        """
        # Force cache bust
        # 1. Generate Code Verifier
        # Use fixed verifier if provided (solves Streamlit session loss), else random
        if fixed_verifier:
            code_verifier = fixed_verifier
        else:
            code_verifier = secrets.token_urlsafe(96)[:128]
        
        # 2. Generate Code Challenge (SHA256 of verifier, base64url encoded)
        hashed = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(hashed).decode('utf-8').rstrip('=')

        # 3. Encode verifier in state (Stateless PKCE for Streamlit)
        # REMOVED STATE completely to test if provider accepts empty state
        # Some providers/libraries are picky about state format.
        # We will rely on session_state fallback if state is stripped.
        state = "dummy_state" 
        
        # 4. Construct URL
        params = {
            "provider": provider,
            "redirect_to": redirect_to,
            "code_challenge": code_challenge,
            "code_challenge_method": "s256",
            # "state": state # Temporarily remove state to isolate the issue
        }
        query_string = urlencode(params)
        auth_url = f"{self.url}/auth/v1/authorize?{query_string}"
        
        return auth_url, code_verifier

    def exchange_code_for_session(self, auth_code, code_verifier):
        """
        Exchanges the authorization code for a session using PKCE.
        """
        endpoint = f"{self.url}/auth/v1/token?grant_type=pkce"
        payload = {
            "auth_code": auth_code,
            "code_verifier": code_verifier
        }
        response = requests.post(endpoint, json=payload, headers=self.headers)
        
        if response.status_code != 200:
            try:
                err = response.json()
                msg = err.get('msg') or err.get('message') or err.get('error_description') or response.text
            except:
                msg = response.text
            raise Exception(f"OAuth exchange failed: {msg}")
            
        return self._parse_auth_response(response.json())

    def _parse_auth_response(self, data):
        # Create a simple object structure similar to what the SDK returns
        class AuthResponse:
            def __init__(self, data):
                self.user = User(data.get('user', {})) if data.get('user') else None
                self.session = Session(data) if 'access_token' in data else None
        
        class User:
            def __init__(self, data):
                self.id = data.get('id')
                self.email = data.get('email')
                self.user_metadata = data.get('user_metadata', {})
        
        class Session:
            def __init__(self, data):
                self.access_token = data.get('access_token')
                
        return AuthResponse(data)
        
    def get_user_credits(self, user_id, access_token):
        """Get remaining credits for a user"""
        endpoint = f"{self.url}/rest/v1/user_credits?user_id=eq.{user_id}&select=credits_remaining"
        try:
            response = requests.get(endpoint, headers=self._get_headers(access_token))
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return data[0]['credits_remaining']
            # Fallback
            return 0
        except Exception as e:
            print(f"Error fetching credits: {e}")
            return 0

    def get_user_profile(self, user_id, access_token):
        """Get full profile including credits and plan"""
        endpoint = f"{self.url}/rest/v1/user_credits?user_id=eq.{user_id}&select=credits_remaining,plan_status"
        try:
            response = requests.get(endpoint, headers=self._get_headers(access_token))
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return {
                        "credits": data[0].get('credits_remaining', 0),
                        "plan": data[0].get('plan_status', 'free')
                    }
            return {"credits": 0, "plan": "free"}
        except Exception as e:
            print(f"Error fetching profile: {e}")
            return {"credits": 0, "plan": "free"}

    def decrement_credits(self, user_id, access_token):
        """Decrement 1 credit from user"""
        # Ideally use RPC, but simple update for MVP
        current = self.get_user_credits(user_id, access_token)
        if current > 0:
            endpoint = f"{self.url}/rest/v1/user_credits?user_id=eq.{user_id}"
            payload = {"credits_remaining": current - 1}
            requests.patch(endpoint, json=payload, headers=self._get_headers(access_token))
            return True
        return False

    def log_invoice(self, user_id, invoice_data, access_token):
        """Log the successful extraction to history"""
        endpoint = f"{self.url}/rest/v1/invoice_history"
        record = {
            "user_id": user_id,
            "vendor_name": invoice_data.get("vendor_name"),
            "total_amount": str(invoice_data.get("total_amount")),
            "currency": invoice_data.get("currency", "CNY"),
            "invoice_number": invoice_data.get("invoice_number")
        }
        requests.post(endpoint, json=record, headers=self._get_headers(access_token))

