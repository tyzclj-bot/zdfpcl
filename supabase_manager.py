
import requests
import json
import secrets
import hashlib
import base64
import re
from datetime import datetime, timezone
from urllib.parse import urlencode


def verify_gumroad_license(license_key):
    """
    极简硬核验证逻辑：直接使用指定的 product_id。
    """
    url = "https://api.gumroad.com/v2/licenses/verify"
    
    # 替换成最原始、最硬核的这两行，不要加任何其他多余的参数
    payload = {
        "product_id": "2YPoqUVEGzeHGGpxmm8ktA==",
        "license_key": license_key
    }
    
    try:
        response = requests.post(url, data=payload, timeout=10)
        data = response.json()
        
        if not data.get("success"):
            return False, data.get("message", "秘钥无效")
            
        # 保持基础的订阅过期检查
        sub_end = data.get("subscription_ended_at")
        if sub_end:
            try:
                end_dt = datetime.fromisoformat(sub_end.replace("Z", "+00:00"))
                if end_dt.timestamp() < datetime.now(timezone.utc).timestamp():
                    return False, "订阅已过期"
            except Exception:
                return False, "订阅状态解析失败"
        
        return True, "验证成功"
    except Exception as e:
        return False, f"验证请求失败: {e}"


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

    def get_google_auth_url(self, redirect_to, fixed_verifier=None):
        """
        Convenience method specifically for Google Login.
        Wraps get_oauth_url with 'google' provider.
        Returns ONLY the auth_url (handling verifier storage is up to the caller/wrapper, 
        but here we assume the caller handles the verifier if they need it, 
        or we just return the URL).
        
        Wait, the app expects just the URL from this method based on usage:
        auth_url = supabase.get_google_auth_url(redirect_url, FIXED_VERIFIER)
        
        So we should update get_oauth_url to be more flexible or just wrap it here.
        """
        url, _ = self.get_oauth_url("google", redirect_to, fixed_verifier)
        return url

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
        """Get full profile including credits, plan, and license_key"""
        endpoint = f"{self.url}/rest/v1/user_credits?user_id=eq.{user_id}&select=credits_remaining,plan_status,license_key"
        try:
            response = requests.get(endpoint, headers=self._get_headers(access_token))
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return {
                        "credits": data[0].get('credits_remaining', 0),
                        "plan": data[0].get('plan_status', 'free'),
                        "license_key": data[0].get('license_key') or None,
                    }
            if response.status_code == 400:
                fallback = f"{self.url}/rest/v1/user_credits?user_id=eq.{user_id}&select=credits_remaining,plan_status"
                r = requests.get(fallback, headers=self._get_headers(access_token))
                if r.status_code == 200 and r.json():
                    d = r.json()[0]
                    return {"credits": d.get('credits_remaining', 0), "plan": d.get('plan_status', 'free'), "license_key": None}
            return {"credits": 0, "plan": "free", "license_key": None}
        except Exception as e:
            print(f"Error fetching profile: {e}")
            return {"credits": 0, "plan": "free", "license_key": None}

    def get_user_license_key(self, user_id, access_token):
        """获取用户绑定的 Gumroad 秘钥"""
        profile = self.get_user_profile(user_id, access_token)
        return profile.get("license_key")

    def save_license_key(self, user_id, license_key, access_token):
        """将有效的 Gumroad 秘钥保存到当前用户的 Supabase 记录"""
        headers = self._get_headers(access_token)
        endpoint = f"{self.url}/rest/v1/user_credits"
        patch_endpoint = f"{endpoint}?user_id=eq.{user_id}"
        payload = {"license_key": license_key.strip(), "plan_status": "pro"}
        patch_res = requests.patch(patch_endpoint, json=payload, headers=headers)
        if patch_res.status_code in (200, 204):
            return True, "秘钥已绑定"
        if patch_res.status_code == 404 or (patch_res.status_code == 204 and not patch_res.content):
            insert_payload = {"user_id": user_id, "license_key": license_key.strip(), "plan_status": "pro", "credits_remaining": 5}
            insert_res = requests.post(endpoint, json=insert_payload, headers=headers)
            if insert_res.status_code in (200, 201):
                return True, "秘钥已绑定"
            return False, insert_res.text or "保存失败"
        return False, patch_res.text or "保存失败"

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

    def add_credits(self, user_id, amount, access_token):
        """Add credits to user (e.g. for promo codes)"""
        current = self.get_user_credits(user_id, access_token)
        endpoint = f"{self.url}/rest/v1/user_credits?user_id=eq.{user_id}"
        payload = {"credits_remaining": current + amount}
        res = requests.patch(endpoint, json=payload, headers=self._get_headers(access_token))
        if res.status_code == 200:
            print(f"DEBUG: Supabase add_credits successful. Status: {res.status_code}")
            return True, "积分添加成功。"
        else:
            error_message = res.text
            print(f"DEBUG: Supabase add_credits failed. Status: {res.status_code}, Response: {error_message}")
            return False, f"积分添加失败：{res.status_code} - {error_message}"

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

    def get_invoice_history(self, user_id, access_token):
        """Fetch invoice processing history for the user"""
        endpoint = f"{self.url}/rest/v1/invoice_history?user_id=eq.{user_id}&order=created_at.desc"
        try:
            response = requests.get(endpoint, headers=self._get_headers(access_token))
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error fetching history: {e}")
            return []

    def get_admin_stats(self, access_token):
        """Fetch admin stats (User count, Invoice count) via RPC"""
        endpoint = f"{self.url}/rest/v1/rpc/get_admin_stats"
        try:
            # We must use POST for RPC calls in Supabase
            response = requests.post(endpoint, headers=self._get_headers(access_token))
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Admin RPC failed: {response.text}")
                return None
        except Exception as e:
            print(f"Error fetching admin stats: {e}")
            return None

    def update_plan_status(self, user_id, new_status, access_token):
        """Update user's plan status (e.g., 'free', 'pro', 'expired') or create if not exists"""
        headers = self._get_headers(access_token)
        endpoint = f"{self.url}/rest/v1/user_credits"

        # Attempt to PATCH (update) existing record
        patch_endpoint = f"{endpoint}?user_id=eq.{user_id}"
        payload = {"plan_status": new_status}
        patch_res = requests.patch(patch_endpoint, json=payload, headers=headers)

        if patch_res.status_code == 200:
            print(f"DEBUG: Supabase update_plan_status (PATCH) successful. Status: {patch_res.status_code}")
            return True, "计划状态更新成功。"
        elif patch_res.status_code == 204: # No content, likely no row to update, so try to insert
            print(f"DEBUG: Supabase update_plan_status (PATCH) received 204. No existing record for user_id {user_id}. Attempting INSERT.")
            # Attempt to POST (insert) new record
            insert_payload = {"user_id": user_id, "plan_status": new_status, "credits_remaining": 0} # Default credits to 0, will be added by add_credits later
            insert_res = requests.post(endpoint, json=insert_payload, headers=headers)

            if insert_res.status_code == 201: # 201 Created for successful insert
                print(f"DEBUG: Supabase update_plan_status (INSERT) successful. Status: {insert_res.status_code}")
                return True, "用户信用记录创建并计划状态更新成功。"
            else:
                error_message = insert_res.text
                print(f"DEBUG: Supabase update_plan_status (INSERT) failed. Status: {insert_res.status_code}, Response: {error_message}")
                return False, f"用户信用记录创建失败：{insert_res.status_code} - {error_message}"
        else: # General PATCH failure
            error_message = patch_res.text
            print(f"DEBUG: Supabase update_plan_status (PATCH) failed. Status: {patch_res.status_code}, Response: {error_message}")
            return False, f"计划状态更新失败：{patch_res.status_code} - {error_message}"


    def grant_premium_membership(self, user_id, access_token, initial_credits=50):
        """Grants premium membership and initial credits upon payment"""
        # Update plan status to 'pro'
        success, message = self.update_plan_status(user_id, 'pro', access_token)
        if not success:
            return False, message
        
        # Add initial credits
        success, message = self.add_credits(user_id, initial_credits, access_token)
        if not success:
            return False, message
            
        return True, "高级会员已成功开通，并已添加积分。"


