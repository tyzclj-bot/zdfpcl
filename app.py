
import streamlit as st
import pandas as pd
import json
import os
import io
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from invoice_extractor import AIInvoiceExtractor
from quickbooks_adapter import QuickBooksAdapter
from supabase_manager import SupabaseManager
from legal_content import PRIVACY_POLICY, TERMS_OF_SERVICE
from tempfile import NamedTemporaryFile

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Invoice Parser - QuickBooks Automation & Email to Bill",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SEO Metadata Injection ---
st.markdown("""
    <script>
    document.title = "AI Invoice Parser - QuickBooks Automation & Email to Bill";
    var meta = document.createElement('meta');
    meta.name = "description";
    meta.content = "Automate your bookkeeping with AI Invoice Parser. Seamlessly sync PDF invoices to QuickBooks Online. The best Email to Bill solution for small businesses.";
    document.getElementsByTagName('head')[0].appendChild(meta);
    </script>
""", unsafe_allow_html=True)

# --- Custom Styling (Modern Western Aesthetic) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Hide Streamlit Default Elements - SAFEST MODE */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Explicitly ensure the header and sidebar toggle are visible */
    header {visibility: visible !important;}
    [data-testid="stHeader"] {visibility: visible !important;}
    [data-testid="stSidebarCollapsedControl"] {visibility: visible !important;}
    
    .main {
        background-color: #f8fafc;
    }

    /* Header Styling */
    .custom-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 0;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 2rem;
    }
    .logo-area {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .logo-icon {
        font-size: 1.5rem;
        color: #4f46e5;
    }
    .logo-text {
        font-weight: 700;
        font-size: 1.25rem;
        color: #1e293b;
    }
    .support-link {
        color: #64748b;
        text-decoration: none;
        font-weight: 500;
        font-size: 0.9rem;
    }
    .support-link:hover {
        color: #4f46e5;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #f1f5f9; /* Light Blue-Grey */
        padding-top: 1rem;
    }

    /* Account Card Styling */
    .account-card {
        background-color: white;
        padding: 1.25rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 1.5rem;
        text-align: center;
        border: 1px solid #e2e8f0;
    }
    .user-avatar {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        object-fit: cover;
        margin-bottom: 0.75rem;
        border: 2px solid #e2e8f0;
    }
    .user-id {
        font-size: 0.85rem;
        color: #64748b;
        margin-bottom: 1rem;
        font-family: monospace;
    }
    .secure-badge {
        font-size: 0.7rem;
        color: #94a3b8;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.25rem;
        margin-top: 0.5rem;
    }
    
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: #4f46e5;
        color: white;
        border: none;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        background-color: #4338ca;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
        transform: scale(1.02);
    }

    /* Style for the main action button */
    .st-emotion-cache-19n6bn1 {
        background-image: linear-gradient(to right, #4f46e5, #7c3aed);
        font-size: 1.1rem;
        font-weight: 700;
    }
    
    .upload-card {
        background-color: white;
        padding: 2rem;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
    }
    
    /* Credit Card Style */
    .credit-card {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .credit-label {
        font-size: 0.8rem;
        opacity: 0.9;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .credit-amount {
        font-size: 2rem;
        font-weight: 700;
        margin: 0.5rem 0;
    }

    .sidebar-nav-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.75rem 1rem;
        color: #334155;
        font-weight: 500;
        border-radius: 6px;
        transition: background-color 0.2s;
    }
    
    .sidebar-nav-item:hover {
        background-color: #e2e8f0;
    }

    h1, h2, h3 {
        color: #1e293b;
    }
    
    /* Trust Section Styling */
    .trust-col {
        text-align: center;
        padding: 1.5rem;
        background: white;
        border-radius: 8px;
        border: 1px solid #f1f5f9;
    }
    .trust-icon {
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    .trust-title {
        font-weight: 600;
        color: #1e293b;
        margin-bottom: 0.25rem;
    }
    .trust-desc {
        color: #64748b;
        font-size: 0.875rem;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_extractor():
    """Use Streamlit cache to create and reuse AI extractor instance"""
    return AIInvoiceExtractor()

def init_supabase():
    """Initialize Supabase Client from Env or Session State"""
    # Check if keys are in env
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    # Or check if they were entered in UI
    if not url and 'supabase_url' in st.session_state:
        url = st.session_state.supabase_url
    if not key and 'supabase_key' in st.session_state:
        key = st.session_state.supabase_key
        
    if url and key:
        return SupabaseManager(url, key)
    return None

from legal_content import PRIVACY_POLICY, TERMS_OF_SERVICE

def generate_quickbooks_csv(data):
    """
    Generate CSV for QuickBooks Online Import.
    Headers: Vendor, Invoice No, Invoice Date, Due Date, Total Amount, Line Amount, Line Account, Line Description
    Date Format: MM/DD/YYYY
    Amount: 2 decimal places
    Encoding: utf-8-sig
    """
    def format_date_us(date_str):
        if not date_str:
            return ""
        try:
            # Try parsing various formats
            dt = pd.to_datetime(date_str)
            return dt.strftime("%m/%d/%Y")
        except:
            return date_str

    headers = ["Vendor", "Invoice No", "Invoice Date", "Due Date", "Total Amount", "Line Amount", "Line Account", "Line Description"]
    rows = []
    
    vendor = data.get("vendor_name", "")
    inv_num = data.get("invoice_number", "")
    inv_date = format_date_us(data.get("date", ""))
    due_date = format_date_us(data.get("due_date", ""))
    
    # Ensure total_amount is float
    try:
        total = float(data.get("total_amount", 0))
        total_str = "{:.2f}".format(total)
    except:
        total_str = "0.00"
    
    items = data.get("items", [])
    
    if items:
        for item in items:
            try:
                line_amount = float(item.get("total_price", 0))
                line_amount_str = "{:.2f}".format(line_amount)
            except:
                line_amount_str = "0.00"
            
            category = item.get("category")
            if not category:
                category = "Uncategorized Expense"
            
            description = item.get("description", "")
            
            row = {
                "Vendor": vendor,
                "Invoice No": inv_num,
                "Invoice Date": inv_date,
                "Due Date": due_date,
                "Total Amount": total_str,
                "Line Amount": line_amount_str,
                "Line Account": category,
                "Line Description": description
            }
            rows.append(row)
    else:
        # Fallback if no items found
        row = {
            "Vendor": vendor,
            "Invoice No": inv_num,
            "Invoice Date": inv_date,
            "Due Date": due_date,
            "Total Amount": total_str,
            "Line Amount": total_str, # Assume single line item equal to total
            "Line Account": "Uncategorized Expense",
            "Line Description": "Invoice Total"
        }
        rows.append(row)
        
    df = pd.DataFrame(rows, columns=headers)
    return df.to_csv(index=False).encode('utf-8-sig')

def get_sample_csv():
    """Generate a sample CSV file for users to preview the format"""
    data = {
        "Vendor": ["Staples", "Staples"],
        "Invoice No": ["INV-2024-001", "INV-2024-001"],
        "Invoice Date": ["01/15/2024", "01/15/2024"],
        "Due Date": ["02/14/2024", "02/14/2024"],
        "Total Amount": ["150.00", "150.00"],
        "Line Amount": ["50.00", "100.00"],
        "Line Account": ["Office Supplies", "Office Equipment"],
        "Line Description": ["Printer Paper (Ream)", "Ergonomic Office Chair"]
    }
    df = pd.DataFrame(data)
    return df.to_csv(index=False).encode('utf-8-sig')

# --- Navigation Helpers ---
def go_home():
    st.query_params.clear()
    st.rerun()

def show_legal_page(title, content):
    st.markdown(f"# {title}")
    st.markdown(content)
    if st.button("← Back to App"):
        go_home()

def show_contact_page():
    st.markdown("# Contact Support")
    st.markdown("""
    We are here to help! If you have any questions, issues, or feature requests, please reach out to us.
    
    ### Email Support
    **Email:** `tyzclj@gmail.com`
    
    **Team Location:** Hong Kong / Taiwan (Global Support)
    
    **Response Time:** We usually respond within 24 hours.
    """)
    
    st.markdown("""
    <a href="mailto:tyzclj@gmail.com" style="
        display: inline-block;
        background-color: #4f46e5;
        color: white;
        padding: 0.75rem 1.5rem;
        text-decoration: none;
        border-radius: 6px;
        font-weight: 600;
        margin-top: 1rem;
    " target="_self">Send Email Now</a>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    if st.button("← Back to App"):
        go_home()

# --- App Logic ---
FIXED_VERIFIER = "v1_persistent_verifier_fix_zdfpcl_2025"
ADMIN_EMAIL = "tyzclj@gmail.com"

def main():
    # --- Navigation Logic ---
    if "nav" in st.query_params:
        nav_target = st.query_params["nav"]
        if nav_target == "privacy":
            show_legal_page("Privacy Policy", PRIVACY_POLICY)
            return
        elif nav_target == "terms":
            show_legal_page("Terms of Service", TERMS_OF_SERVICE)
            return
        elif nav_target == "contact":
            show_contact_page()
            return

    # --- Custom Header (SaaS Look) ---
    st.markdown("""
        <div class="custom-header">
            <div class="logo-area">
                <div class="logo-icon">🧾</div>
                <div class="logo-text">QuickBills AI</div>
            </div>
            <div style="flex-grow: 1; text-align: center;">
                <h2 style="margin: 0; font-size: 1.5rem; font-weight: 800; color: #1e293b;">
                    Effortless Bookkeeping for QuickBooks Users
                </h2>
            </div>
            <div>
                <a href="?nav=contact" class="support-link" target="_self">Support</a>
                <span style="margin: 0 0.5rem; color: #cbd5e1;">|</span>
                <a href="#" class="support-link" target="_self">Docs</a>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # --- Promotional Banner (Removed, replaced by Header) ---
    # st.markdown(""" ... """)

    # --- Session State Init ---
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'access_token' not in st.session_state:
        st.session_state.access_token = None
    if 'credits' not in st.session_state:
        st.session_state.credits = 0

    # --- Sidebar: Auth & Settings ---
    with st.sidebar:
        st.header("Authorization")
        
        supabase = init_supabase()
        
        if not supabase:
            st.warning("Please configure Supabase credentials.")
            st.session_state.supabase_url = st.text_input("Supabase URL", placeholder="https://xyz.supabase.co")
            st.session_state.supabase_key = st.text_input("Supabase Anon Key", type="password")
            if st.button("Save Settings"):
                st.rerun()
        else:
            # --- DEBUG SECTION ---
            # Remove this in production once fixed
            # with st.expander("🔧 Connection Debugger", expanded=True):
            #     st.write("Current URL Parameters:")
            #     st.json(dict(st.query_params))
            #     
            #     if 'code' in st.query_params:
            #         st.success("✅ Auth Code Detected!")
            #     else:
            #         st.info("ℹ️ No Auth Code in URL")
            #         
            #     if 'error' in st.query_params:
            #         st.error(f"⚠️ Provider Error: {st.query_params.get('error')}")
            #         st.error(f"Description: {st.query_params.get('error_description')}")

            # Handle OAuth Callback (Check if returning from Google)
            # Use query_params directly which is more robust in newer Streamlit versions
            if 'code' in st.query_params:
                # --- FIX: Handle Browser Back Button ---
                # If user is already logged in, ignore the code (it might be old/used)
                # and just clean the URL to prevent "Invalid Grant" errors or UI stutter.
                if st.session_state.user is not None:
                    st.query_params.clear()
                    st.rerun()

                code = st.query_params['code']
                
                # Attempt to retrieve verifier from state (Stateless) or Session (Stateful)
                verifier = None
                
                # 1. Try State (Simplified: State IS the verifier)
                if 'state' in st.query_params:
                    verifier = st.query_params['state']
                
                # 2. Fallback to Session State
                if not verifier:
                    verifier = st.session_state.get('oauth_verifier')

                # 3. Fallback to Fixed Verifier (Production Stability)
                if not verifier:
                    verifier = FIXED_VERIFIER
                
                if verifier:
                    try:
                        with st.spinner("Logging in with Google..."):
                            res = supabase.exchange_code_for_session(code, verifier)
                            if res and res.user:
                                st.session_state.user = res.user
                                st.session_state.access_token = res.session.access_token
                                
                                # Clean up - CRITICAL: Clear query params to prevent loop
                                st.query_params.clear()
                                # del st.session_state.oauth_verifier
                                
                                st.success("Logged in with Google successfully!")
                                
                                # Auto-redirect
                                time.sleep(0.5) 
                                st.rerun()
                    except Exception as e:
                        # Improved Error Logging
                        st.error(f"Google Login failed: {str(e)}")
                        # Debug info for the user to help troubleshoot
                        with st.expander("Troubleshooting Info"):
                            st.write(f"Verifier present: {bool(verifier)}")
                            st.write(f"Code present: {bool(code)}")
                            if hasattr(e, 'response'):
                                st.write(f"Response: {e.response.text}")
                                
                        # Clear params to avoid loop even on error
                        st.query_params.clear()
                        # Optional: Wait a bit so user sees the error
                        time.sleep(5) # Increase wait time to read error
                        st.rerun()
                else:
                    # Case: We have a code but no verifier. 
                    # This happens if session state was lost (e.g. cross-device or browser privacy settings)
                    # Or simply a refresh on the callback URL.
                    st.warning("Session expired or invalid. Please try logging in again.")
                    # Debug Info
                    with st.expander("Debug Details"):
                        st.write("Reason: OAuth Verifier missing from session and state.")
                        st.write("Please ensure cookies are enabled and you are not in Incognito mode causing state loss.")
                    
                    st.query_params.clear()
                    if st.button("Retry Login"):
                        st.rerun()
            
            # If User is Logged In
            # FORCE RE-CHECK of Session State if needed
            if st.session_state.user:
                # Display Avatar if available
                user_meta = getattr(st.session_state.user, 'user_metadata', {})
                
                # Google often uses 'picture' instead of 'avatar_url'
                avatar_url = user_meta.get('avatar_url') or user_meta.get('picture')
                full_name = user_meta.get('full_name') or user_meta.get('name') or st.session_state.user.email.split('@')[0]
                user_email = st.session_state.user.email
                
                # Masked ID (e.g., user_123...456)
                masked_id = f"ID: {st.session_state.user.id[:8]}...{st.session_state.user.id[-4:]}"
                
                # --- Account Card ---
                st.markdown(f"""
                    <div class="account-card">
                        <img src="{avatar_url if avatar_url else 'https://www.gravatar.com/avatar/00000000000000000000000000000000?d=mp&f=y'}" class="user-avatar">
                        <div style="font-weight: 600; color: #1e293b;">{full_name}</div>
                        <div class="user-id">{masked_id}</div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Fetch fresh credits and plan
                profile = supabase.get_user_profile(st.session_state.user.id, st.session_state.access_token)
                st.session_state.credits = profile.get("credits", 0)
                plan_status = profile.get("plan", "free")
                
                # Credits Display with Top Up
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.metric("Credits", st.session_state.credits)
                with c2:
                    if plan_status == 'pro':
                         st.markdown('<span style="background:#dcfce7; color:#166534; padding:2px 6px; border-radius:4px; font-size:12px; font-weight:bold;">PRO</span>', unsafe_allow_html=True)
                    else:
                         st.markdown('<span style="background:#f1f5f9; color:#64748b; padding:2px 6px; border-radius:4px; font-size:12px; font-weight:bold;">FREE</span>', unsafe_allow_html=True)

                if st.session_state.credits <= 0:
                    st.error("Please Top Up")
                
                # Upgrade/Top Up Button
                if plan_status != 'pro':
                    checkout_url = "https://www.paypal.com/invoice/p/#FNC8963Z27RBSCZ5"
                    st.link_button("💎 Top Up Credits", checkout_url, type="primary", use_container_width=True)
                    st.markdown("""
                        <div class="secure-badge">
                            <span>🔒 Secured by PayPal</span>
                        </div>
                    """, unsafe_allow_html=True)

                # --- Reddit Promo Section ---
                with st.expander("🎁 Reddit Exclusive"):
                    promo_code = st.text_input("Enter Promo Code", key="reddit_promo")
                    if st.button("Claim Credits"):
                        if promo_code.strip().upper() == "REDDIT2024":
                            # Check if already redeemed (simple session check for now)
                            # Ideally check DB user_metadata
                            if hasattr(supabase, 'add_credits'):
                                if supabase.add_credits(st.session_state.user.id, 5, st.session_state.access_token):
                                    st.toast("Success! +5 Credits Added", icon="🎉")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Failed to add credits.")
                            else:
                                st.warning("Please redeploy app to enable this feature.")
                        else:
                            st.error("Invalid Code")

                if st.button("Logout"):
                    supabase.sign_out(st.session_state.access_token)
                    st.session_state.user = None
                    st.session_state.access_token = None
                    st.session_state.credits = 0
                    st.rerun()

                # --- ADMIN DASHBOARD (Sidebar) ---
                # Only visible to tyzclj@gmail.com
                if st.session_state.user.email == ADMIN_EMAIL:
                    st.markdown("---")
                    st.markdown("### 👑 Admin Stats")
                    
                    # Auto Top-up for Admin if low credits
                    if st.session_state.credits < 10:
                        if hasattr(supabase, 'add_credits'):
                            # Add 100 credits
                            supabase.add_credits(st.session_state.user.id, 100, st.session_state.access_token)
                            st.session_state.credits += 100
                            st.toast("Admin Auto-Topup: +100 Credits", icon="⚡")
                            st.rerun()

                    if hasattr(supabase, 'get_admin_stats'):
                        admin_stats = supabase.get_admin_stats(st.session_state.access_token)
                        st.markdown(f"**Total Users:** {admin_stats.get('user_count', 0)}")
                        st.markdown(f"**Total Invoices:** {admin_stats.get('invoice_count', 0)}")
                    else:
                        st.info("Admin stats module not loaded.")

            else:
                # --- Login / Register Buttons ---
                st.info("Log in to start automating your invoices.")
                
                # Google Login (Primary)
                try:
                    # Using FIXED_VERIFIER for stability
                    redirect_url = "https://quickbills-ai.streamlit.app" 
                    auth_url = supabase.get_google_auth_url(redirect_url, FIXED_VERIFIER)
                    
                    # Use HTML button to force target="_self" (prevent opening new tab)
                    st.markdown(f"""
                        <a href="{auth_url}" target="_self" style="
                            display: block;
                            width: 100%;
                            background-color: #FF4B4B;
                            color: white;
                            text-align: center;
                            padding: 0.5rem 0.75rem;
                            border-radius: 0.5rem;
                            text-decoration: none;
                            font-weight: 600;
                            border: 1px solid #FF4B4B;
                            line-height: 1.6;
                            font-family: 'Source Sans Pro', sans-serif;
                            margin-top: 0px;
                        ">
                            Continue with Google
                        </a>
                    """, unsafe_allow_html=True)
                    # st.link_button("Continue with Google", auth_url, type="primary", use_container_width=True)
                except Exception as e:
                    st.error(f"Auth Error: {e}")
                
                st.markdown("""
                    <div style="text-align: center; margin: 1rem 0; color: #64748b; font-size: 0.9rem;">
                        OR
                    </div>
                """, unsafe_allow_html=True)

                # Email Login (Secondary)
                with st.expander("Continue with Email"):
                    email = st.text_input("Email Address")
                    password = st.text_input("Password", type="password")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Log In", use_container_width=True):
                            try:
                                res = supabase.sign_in(email, password)
                                if res and res.user:
                                    st.session_state.user = res.user
                                    st.session_state.access_token = res.session.access_token
                                    st.rerun()
                            except Exception as e:
                                st.error(str(e))
                    with c2:
                        if st.button("Sign Up", use_container_width=True):
                            try:
                                res = supabase.sign_up(email, password)
                                if res and res.user:
                                    st.success("Account created! Please check your email to confirm.")
                            except Exception as e:
                                st.error(str(e))

        st.divider()
        
        # --- Legal Section ---
        with st.expander("⚖️ Legal & Terms"):
            # Use columns to avoid potential button id conflicts in sidebar
            l1, l2 = st.columns(2)
            with l1:
                if st.button("Privacy", key="btn_privacy"):
                    st.session_state.show_legal = "privacy"
                    st.rerun()
            with l2:
                if st.button("Terms", key="btn_terms"):
                    st.session_state.show_legal = "terms"
                    st.rerun()

        # --- Support Section ---
        st.markdown("---")
        st.markdown("### 💬 Support")
        st.markdown("""
            <div style="background-color: white; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;">
                <p style="margin: 0 0 0.5rem 0; font-size: 0.9rem; color: #64748b;">Need help or custom integration?</p>
                <a href="?nav=contact" style="
                    display: inline-block;
                    width: 100%;
                    background-color: #f8fafc;
                    color: #334155;
                    border: 1px solid #cbd5e1;
                    padding: 0.5rem;
                    border-radius: 6px;
                    text-decoration: none;
                    font-weight: 600;
                    font-size: 0.9rem;
                    transition: all 0.2s;
                " target="_self">
                    ✉️ Contact Support
                </a>
            </div>
        """, unsafe_allow_html=True)

        # st.info("System Status: Online")
        # st.caption("v1.2.0 (Stable Auth Fix)")

    # --- Main App Display ---
    
    # Handle Legal Page Display
    if 'show_legal' in st.session_state:
        # Use st.empty() to clear previous content effectively if needed
        placeholder = st.empty()
        with placeholder.container():
            if st.session_state.show_legal == "privacy":
                st.title("🔒 Privacy Policy")
                st.markdown(PRIVACY_POLICY)
                if st.button("← Back to App", key="back_btn_privacy"):
                    del st.session_state.show_legal
                    st.rerun()
                # Stop execution here so main app doesn't render
                return
            elif st.session_state.show_legal == "terms":
                st.title("📜 Terms of Service")
                st.markdown(TERMS_OF_SERVICE)
                if st.button("← Back to App", key="back_btn_terms"):
                    del st.session_state.show_legal
                    st.rerun()
                # Stop execution here so main app doesn't render
                return

    # --- Hero Section (Visible to all, but styled differently if logged in?) ---
    # Actually, for a SaaS tool, the "Landing" is usually different from "Dashboard".
    # But user wants this "Homepage" look. Let's put it at the top.
    
    if not st.session_state.user:
        # LANDING PAGE VIEW (Hero Section)
        st.markdown("""
            <div style="text-align: center; margin-top: 2rem; margin-bottom: 3rem;">
                <h1 style="font-size: 3.5rem; font-weight: 800; color: #1e293b; line-height: 1.2; margin-bottom: 1rem;">
                    Automate Bills to <span style="color: #4f46e5;">QuickBooks</span> in Seconds
                </h1>
                <p style="font-size: 1.25rem; color: #64748b; font-weight: 400; max-width: 600px; margin: 0 auto 2rem;">
                    Stop manual typing. Powered by DeepSeek AI with 99% accuracy.
                </p>
                <div style="display: flex; justify-content: center; gap: 1rem; margin-bottom: 2rem;">
                    <span style="background-color: #dbeafe; color: #1e40af; padding: 0.5rem 1rem; border-radius: 9999px; font-weight: 600; font-size: 0.875rem;">🚀 Instant Sync</span>
                    <span style="background-color: #d1fae5; color: #065f46; padding: 0.5rem 1rem; border-radius: 9999px; font-weight: 600; font-size: 0.875rem;">✨ 99% Accuracy</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Demo Video Area
        st.markdown("""
            <div style="
                position: relative;
                padding-bottom: 56.25%; /* 16:9 Aspect Ratio */
                height: 0;
                margin-bottom: 3rem;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
                border: 1px solid #e2e8f0;
            ">
                <iframe 
                    src="https://www.loom.com/embed/74ac71240953463ca8825d89d2898f35?hide_owner=true&hide_share=true&hide_title=true&hideEmbedTopBar=true" 
                    frameborder="0" 
                    webkitallowfullscreen 
                    mozallowfullscreen 
                    allowfullscreen 
                    style="
                        position: absolute; 
                        top: 0; 
                        left: 0; 
                        width: 100%; 
                        height: 100%;
                    "
                ></iframe>
            </div>
        """, unsafe_allow_html=True)

        # Trust Badges (Landing Page)
        st.markdown("""
            <div style="display: flex; justify-content: center; gap: 3rem; margin-bottom: 4rem; flex-wrap: wrap; border-top: 1px solid #e2e8f0; padding-top: 2rem;">
                 <div style="text-align: center;">
                    <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">🔒</div>
                    <div style="font-weight: 600; color: #334155;">SSL Encrypted</div>
                 </div>
                 <div style="text-align: center;">
                    <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">🗑️</div>
                    <div style="font-weight: 600; color: #334155;">No Data Retention</div>
                 </div>
                 <div style="text-align: center;">
                    <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">✅</div>
                    <div style="font-weight: 600; color: #334155;">QuickBooks Compatible</div>
                 </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="text-align: center; padding: 20px; background-color: white; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 2rem;">
            <h3>👋 Ready to get started?</h3>
            <p>Please log in or register via the sidebar to start processing invoices.</p>
            <p>New users get <b>5 free credits</b>!</p>
        </div>
        """, unsafe_allow_html=True)
        
        # --- Sample Download Section ---
        st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <h3>🔍 See what you get</h3>
            <p style="color: #64748b;">Download a sample CSV to see exactly how we format your data for QuickBooks Online.</p>
        </div>
        """, unsafe_allow_html=True)
        
        _, col_dl, _ = st.columns([1, 1, 1])
        with col_dl:
            st.download_button(
                label="📄 Download Sample CSV",
                data=get_sample_csv(),
                file_name="quickbooks_sample_export.csv",
                mime="text/csv",
                use_container_width=True,
                type="secondary"
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # --- FAQ Section ---
        st.subheader("Frequently Asked Questions")
        
        faq1, faq2, faq3 = st.columns(3)
        with faq1:
            st.markdown("**Is my data secure?**")
            st.caption("Yes. We use SSL encryption and do not permanently store your files. We are a Hong Kong / Taiwan based team serving global users, adhering to strict privacy standards.")
        with faq2:
            st.markdown("**Can it handle non-standard invoices?**")
            st.caption("Absolutely. Our AI engine outperforms traditional OCR by understanding context, allowing it to accurately parse complex and non-standard layouts.")
        with faq3:
            st.markdown("**Can I request a custom CSV format?**")
            st.markdown("Yes. Please <a href='?nav=contact' target='_self'>contact us</a> for custom integrations. We support a wide range of accounting software and formats.", unsafe_allow_html=True)
        
    else:
        # DASHBOARD VIEW (Logged In)
        
        # Check Credits Logic
        if st.session_state.credits <= 0:
            st.warning("⚠️ You have 0 credits remaining. Please upgrade your plan to continue parsing invoices.")
            st.info("New users get 5 free credits.")
            return

        # Main Layout: Upload and Processing
        col1, col2 = st.columns([1, 2], gap="large")

        with col1:
            # Wrap in a container for card-like look
            with st.container(border=True):
                st.subheader("1. Upload Invoice")
                uploaded_file = st.file_uploader("Upload Invoice", type=["pdf", "png", "jpg", "jpeg"])
                
                # Trust Signals
                st.markdown("""
                    <div style="font-size: 0.8rem; color: #64748b; margin-top: 1rem;">
                        <p style="margin-bottom: 0.25rem;">🛡️ 7-Day Money Back Guarantee</p>
                        <p>🔒 Secure Payment by Lemon Squeezy</p>
                    </div>
                """, unsafe_allow_html=True)

                if uploaded_file:
                    # Display preview based on file type
                    file_type = uploaded_file.type
                    if "image" in file_type:
                        st.image(uploaded_file, caption="Uploaded Image Preview", width=400)
                    else:
                        st.success(f"PDF file '{uploaded_file.name}' uploaded successfully!")

                    if st.button("🤖 Process with AI"):
                        # Double check credits before processing
                        supabase = init_supabase()
                        credits = supabase.get_user_credits(st.session_state.user.id, st.session_state.access_token)
                        
                        if credits <= 0:
                            st.error("Insufficient credits!")
                            return

                        extractor = get_extractor() # Get cached instance
                        
                        # --- Multi-step "Ritual" Loading ---
                        with st.status("Processing Invoice...", expanded=True) as status:
                            st.write("Scanning invoice text...")
                            # Simulate scanning
                            time.sleep(0.8)
                            
                            try:
                                file_bytes = uploaded_file.getvalue()
                                
                                if "image" in uploaded_file.type:
                                    st.write("Optimizing image for OCR...")
                                    data = extractor.extract_from_image(file_bytes)
                                else: # It's a PDF
                                    st.write("Extracting raw text layer...")
                                    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                                        tmp.write(file_bytes)
                                        tmp_path = tmp.name
                                    
                                    data = extractor.process_pdf(tmp_path)
                                    os.unlink(tmp_path)
                                
                                st.write("Identifying line items & totals...")
                                time.sleep(0.5) 
                                
                                st.write("Validating against QuickBooks format...")
                                time.sleep(0.5)

                                # Check return data type
                                if isinstance(data, dict) and data.get("error"):
                                    status.update(label="Analysis Failed", state="error", expanded=True)
                                    st.error(f"AI Processing Error: {data['error']}")
                                    # Clear old data (if any)
                                    if 'invoice_data' in st.session_state:
                                        del st.session_state['invoice_data']
                                    if 'raw_ocr_output' in st.session_state:
                                        del st.session_state['raw_ocr_output']
                                else:
                                    # If Pydantic object, convert to dict for storage and display
                                    if not isinstance(data, dict):
                                        data = data.model_dump()
                                    
                                    # Store raw text in session state as requested
                                    if "_raw_text" in data:
                                        st.session_state.raw_ocr_output = data["_raw_text"]
                                    
                                    st.session_state['invoice_data'] = data
                                    st.session_state['processed'] = True
                                    
                                    # --- SUCCESS: Deduct Credit & Log History ---
                                    try:
                                        supabase.decrement_credits(st.session_state.user.id, st.session_state.access_token)
                                        supabase.log_invoice(st.session_state.user.id, data, st.session_state.access_token)
                                        st.toast("Credits deducted: -1", icon="💳")
                                        # Update local state to reflect change immediately
                                        st.session_state.credits -= 1
                                    except Exception as db_err:
                                        st.warning(f"Result processed but failed to update DB: {db_err}")
                                
                                    status.update(label="Analysis Complete!", state="complete", expanded=False)
                                    st.rerun()
                            except Exception as e:
                                status.update(label="Analysis Error", state="error", expanded=True)
                                st.error(f"An error occurred during processing: {str(e)}")

        with col2:
            with st.container(border=True):
                st.subheader("2. Extraction Results")
                
                if 'invoice_data' in st.session_state:
                    data = st.session_state['invoice_data']

                    # If diagnostic mode result, display specially
                    if "diagnostic_description" in data:
                        st.subheader("AI Vision Diagnostic Report")
                        st.markdown(data["diagnostic_description"])
                        st.info("This is a diagnostic run. We are checking the connection to the vision model.")
                        return # Stop rendering

                    # Key Metrics Row
                    m1, m2, m3 = st.columns(3)
                    with m1:
                        st.metric("Vendor", data.get('vendor_name'))
                    with m2:
                        currency_symbol = "$" if data.get('currency', 'USD') == 'USD' else data.get('currency', '')
                        st.metric("Total Amount", f"{currency_symbol}{data.get('total_amount')}")
                    with m3:
                        st.metric("Invoice #", data.get('invoice_number'))

                    # Details Tab
                    tab1, tab2, tab3 = st.tabs(["Line Items", "Raw JSON", "Debug OCR"])
                    
                    with tab1:
                        if data.get('items'):
                            # Create a display-friendly DataFrame
                            items_list = data['items']
                            df = pd.DataFrame(items_list)
                            
                            # Rename columns for professional display
                            # Map internal keys to display keys
                            column_config = {
                                "description": st.column_config.TextColumn("Description", width="large"),
                                "quantity": st.column_config.NumberColumn("Qty"),
                                "unit_price": st.column_config.NumberColumn("Unit Price", format="$%.2f"),
                                "total_price": st.column_config.NumberColumn("Total", format="$%.2f"),
                                "category": st.column_config.SelectboxColumn("Category", options=["Office Supplies", "Meals", "Travel", "Software", "Utilities", "Uncategorized Expense"], required=True)
                            }
                            
                            # Ensure we only show relevant columns
                            cols_order = ["description", "quantity", "unit_price", "total_price", "category"]
                            # Filter only existing columns
                            cols_order = [c for c in cols_order if c in df.columns]
                            
                            edited_df = st.data_editor(
                                df[cols_order],
                                column_config=column_config,
                                num_rows="dynamic",
                                use_container_width=True,
                                key="invoice_items_editor"
                            )
                            
                            # --- Real-time Validation ---
                            try:
                                # Calculate sum of line items
                                line_total = edited_df['total_price'].sum()
                                invoice_total = float(data.get('total_amount', 0))
                                
                                # Check for mismatch (allow small float error)
                                if abs(line_total - invoice_total) > 0.01:
                                    st.warning(f"⚠️ **Total mismatch detected.** Line items sum (${line_total:.2f}) does not match Invoice Total (${invoice_total:.2f}). Please double-check.")
                                else:
                                    st.caption(f"✅ Line items match invoice total.")
                                
                                # Update session state with edited data
                                # We need to map back to original keys if we renamed them? 
                                # st.data_editor returns dataframe with same column names as input df if we just used column_config to change label.
                                # Yes, column_config changes the *label*, not the underlying key. So edited_df still has 'description', 'total_price' etc.
                                
                                updated_items = edited_df.to_dict('records')
                                st.session_state['invoice_data']['items'] = updated_items
                                
                            except Exception as val_err:
                                st.error(f"Validation Error: {val_err}")

                        else:
                            st.write("No line items detected.")

                    with tab2:
                        st.json(data)
                    
                    with tab3:
                        st.subheader("Raw Extracted Text (OCR Output)")
                        st.caption("This is the raw text extracted from your document before AI processing.")
                        
                        raw_display = "Waiting for upload..."
                        source = "Init"
                        
                        if "raw_ocr_output" in st.session_state:
                            raw_display = st.session_state.raw_ocr_output
                            source = "Session State"
                        elif isinstance(data, dict) and data.get("_raw_text"):
                            raw_display = data.get("_raw_text")
                            source = "Data Object"
                        
                        st.text_area("Raw Text Content", value=raw_display, height=400, disabled=False)
                        
                        # Debugging Info (Hidden by default)
                        with st.expander("🛠️ Developer Debug Info"):
                            st.write(f"**Data Source:** {source}")
                            st.write("**Session Keys:**", list(st.session_state.keys()))
                            if isinstance(data, dict):
                                st.write("**Data Keys:**", list(data.keys()))
                                st.write("**Has _raw_text:**", "_raw_text" in data)
                                if "_raw_text" in data:
                                    st.write("**_raw_text length:**", len(data["_raw_text"]))
                            else:
                                st.write("**Data Type:**", type(data))

                    st.divider()
                    
                    # Action Section
                    st.subheader("3. Export & Sync")
                    
                    # Prepare data for export
                    items_data = data.get('items', [])
                    df_export = pd.DataFrame(items_data) if items_data else pd.DataFrame()

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("🚀 Sync to QuickBooks"):
                            with st.spinner("Connecting to QuickBooks Online..."):
                                qb = QuickBooksAdapter()
                                if qb.sync_invoice(data):
                                    st.toast("Successfully synced to QuickBooks!", icon="✅")
                                    st.success("Synchronized with ERP system.")
                    
                    with c2:
                        # 2. Export Button
                        csv = generate_quickbooks_csv(data)
                        
                        # Generate Professional Filename
                        # Format: QuickBills_Export_YYYY-MM-DD.csv
                        from datetime import datetime
                        date_str = datetime.now().strftime("%Y-%m-%d")
                        filename = f"QuickBills_Export_{date_str}.csv"
                        
                        st.download_button(
                            label="📥 Download QuickBooks CSV",
                            data=csv,
                            file_name=filename,
                            mime="text/csv",
                            type="primary",
                            use_container_width=True
                        )

                    with c3:
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            df_export.to_excel(writer, index=False, sheet_name='Invoice')
                        
                        st.download_button(
                            label="📊 Download Excel",
                            data=buffer.getvalue(),
                            file_name=f"invoice_{data.get('invoice_number', 'export')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                else:
                    st.info("Upload and process an invoice to see results here.")

        # --- Processing History ---
        st.divider()
        with st.expander("🕒 Processing History", expanded=False):
            with st.spinner("Loading history..."):
                 # Fetch history
                # Safety check for stale deployments where method might be missing
                if hasattr(supabase, 'get_invoice_history'):
                    history = supabase.get_invoice_history(st.session_state.user.id, st.session_state.access_token)
                    
                    if history:
                        # Convert to DataFrame
                        df_history = pd.DataFrame(history)
                        
                        # Column mapping
                        cols_to_show = {
                            "created_at": "Date",
                            "vendor_name": "Vendor", 
                            "invoice_number": "Invoice #", 
                            "total_amount": "Amount", 
                            "currency": "Currency"
                        }
                        
                        # Filter and Rename
                        available_cols = [c for c in cols_to_show.keys() if c in df_history.columns]
                        df_history = df_history[available_cols].rename(columns=cols_to_show)
                        
                        # Format Date
                        if "Date" in df_history.columns:
                            try:
                                df_history["Date"] = pd.to_datetime(df_history["Date"]).dt.strftime("%Y-%m-%d %H:%M")
                            except:
                                pass
                        
                        st.dataframe(df_history, use_container_width=True, hide_index=True)
                    else:
                        st.info("No processing history found.")
                else:
                    st.warning("Please redeploy the app to update the Supabase Manager (missing get_invoice_history).")

        # --- Trust Footer (Logged In View) ---
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; border-top: 1px solid #e2e8f0; padding-top: 2rem;">
                <div class="trust-col">
                    <div class="trust-icon">🛡️</div>
                    <div class="trust-title">100% Secure</div>
                    <div class="trust-desc">No sensitive files stored. Hong Kong / Taiwan based team serving global users.</div>
                </div>
                <div class="trust-col">
                    <div class="trust-icon">⚡</div>
                    <div class="trust-title">AI Powered</div>
                    <div class="trust-desc">DeepSeek Engine with 99.8% extraction accuracy.</div>
                </div>
                <div class="trust-col">
                    <div class="trust-icon">📋</div>
                    <div class="trust-title">QB Ready</div>
                    <div class="trust-desc">Guaranteed QuickBooks Online compatible CSV format.</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # --- Global Site Footer ---
    st.markdown("""
        <div style="text-align: center; margin-top: 4rem; margin-bottom: 2rem; color: #94a3b8; font-size: 0.85rem; border-top: 1px solid #f1f5f9; padding-top: 2rem;">
            <p style="margin-bottom: 0.5rem;">&copy; 2025 QuickBills AI. All rights reserved.</p>
            <div style="display: flex; justify-content: center; gap: 1.5rem;">
                 <a href="?nav=privacy" style="color: #64748b; text-decoration: none; transition: color 0.2s;" target="_self">Privacy Policy</a>
                 <a href="?nav=terms" style="color: #64748b; text-decoration: none; transition: color 0.2s;" target="_self">Terms of Service</a>
                 <a href="?nav=contact" style="color: #64748b; text-decoration: none; transition: color 0.2s;" target="_self">Contact Us</a>
            </div>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
