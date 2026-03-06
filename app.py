import streamlit as st
import pandas as pd
import json
import os
import io
import time
from dotenv import load_dotenv
import traceback # For detailed error logging

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

    /* Custom style for the Download CSV button */
    [data-testid="stDownloadButton-download_csv_button"] button {
        background-color: #ef4444; /* A nice red color */
        color: white;
        font-size: 1.1rem; /* Slightly larger font */
        padding: 0.75rem 1.5rem; /* Larger padding */
        border-radius: 0.5rem; /* Consistent border-radius */
        border: 1px solid #dc2626; /* Darker red border */
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        transition: all 0.2s ease-in-out;
    }

    [data-testid="stDownloadButton-download_csv_button"] button:hover {
        background-color: #dc2626; /* Darker red on hover */
        border-color: #b91c1c;
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
def get_extractor_v6():
    """Use Streamlit cache to create and reuse AI extractor instance (Version 6 - Tax Validation)"""
    return AIInvoiceExtractor()

# --- Helper: Waitlist Modal (Fake Door Test) ---
if hasattr(st, "dialog"):
    dialog_decorator = st.dialog
elif hasattr(st, "experimental_dialog"):
    dialog_decorator = st.experimental_dialog
else:
    dialog_decorator = None

if dialog_decorator:
    @dialog_decorator("🚀 Private Beta Access")
    def show_waitlist_modal():
        st.markdown("""
            <div style="text-align: center; margin-bottom: 20px;">
                <h3 style="color: #1e293b; margin-top: 0;">Direct QuickBooks Sync</h3>
                <p style="color: #64748b; font-size: 16px;">
                    We are currently in <b>private beta</b> for direct API integration. <br>
                    Join the waitlist to get early access and <span style="color: #4f46e5; font-weight: 600;">50 bonus credits</span> when we launch.
                </p>
            </div>
        """, unsafe_allow_html=True)
        
        # Pre-fill email
        default_email = st.session_state.user.email if 'user' in st.session_state and st.session_state.user else ""
        email = st.text_input("Email for Early Access", value=default_email, placeholder="name@company.com")
        
        if st.button("✨ Join the Waitlist", type="primary", use_container_width=True):
            if email:
                # Log interest (Fake Door Metric)
                # In a real app, we'd do: supabase.table('waitlist').insert({'email': email})
                time.sleep(0.5)
                st.success("You're on the list! We'll notify you soon.")
                time.sleep(1.5)
                st.rerun()
            else:
                st.error("Please enter a valid email address.")
else:
    # Fallback for older Streamlit versions
    def show_waitlist_modal():
        with st.sidebar:
            st.info("We are currently in private beta for direct sync. Please contact support to join.")

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
                with st.container(border=True):
                    st.markdown("**Account Overview**")
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.image("https://api.dicebear.com/7.x/initials/svg?seed=" + st.session_state.user.email, width=50)
                    with col2:
                        st.write(f"Hello, **{st.session_state.user.email.split('@')[0]}**")
                        st.write(f"Credits: **{st.session_state.credits}**")
                    
                    # --- Pro Plan Button (Sidebar) ---
                    # Using st.markdown for custom HTML/CSS for a more prominent button
                    gumroad_checkout_url = "https://tyzclj.gumroad.com/l/quickbills"
                    st.markdown(f"""
                    <a href="{gumroad_checkout_url}" target="_blank" style="
                        display: inline-block;
                        background-color: #f59e0b; /* Amber 500 */
                        color: white;
                        padding: 0.75rem 1rem;
                        text-align: center;
                        border-radius: 0.5rem;
                        text-decoration: none;
                        font-weight: 700;
                        font-size: 1rem;
                        width: 100%;
                        margin-top: 1rem;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                        transition: all 0.2s ease-in-out;
                    ">
                        ✨ Subscribe to Pro - $19.99/mo
                    </a>
                    <div style="font-size: 0.75rem; color: #9ca3af; text-align: center; margin-top: 0.5rem;">
                        Secured by Gumroad
                    </div>
                    """, unsafe_allow_html=True)


                    if st.button("Logout", type="secondary", use_container_width=True):
                        with st.spinner("Logging out..."):
                            supabase.sign_out()
                            st.session_state.user = None
                            st.session_state.access_token = None
                            st.session_state.credits = 0
                            st.query_params.clear()
                            time.sleep(0.5)
                            st.rerun()
            else:
                st.info("Log in to unlock all features!")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Login with Google", use_container_width=True):
                        # Generate a random state for security (CSRF protection)
                        verifier = os.urandom(16).hex() # More robust verifier
                        st.session_state.oauth_verifier = verifier # Store in session state
                        oauth_url = supabase.get_google_oauth_url(verifier)
                        st.markdown(f'<a href="{oauth_url}" target="_self"><img src="https://developers.google.com/static/identity/images/btn_google_signin_dark_normal_v2.svg" alt="Sign in with Google"></a>', unsafe_allow_html=True)
                with col2:
                    if st.button("Login with Email", use_container_width=True):
                        st.warning("Email login is coming soon!")
                
                # --- Pro Plan Card for Guest Users ---
                gumroad_checkout_url = "https://tyzclj.gumroad.com/l/quickbills"
                st.markdown("""
                <div style="margin-top: 2rem; padding: 1.5rem; background-color: #ffffff; border-radius: 0.75rem; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05); text-align: center; border: 1px solid #e5e7eb;">
                    <h3 style="color: #4f46e5; margin-bottom: 0.5rem; font-size: 1.5rem;">Pro Plan</h3>
                    <p style="font-size: 2.25rem; font-weight: 700; color: #1e293b; margin-top: 0;">$19.99<span style="font-size: 1rem; color: #64748b;">/mo</span></p>
                    <ul style="list-style-type: none; padding: 0; margin-bottom: 1.5rem; color: #374151; text-align: left;">
                        <li style="margin-bottom: 0.5rem;"><span style="color: #10b981; margin-right: 0.5rem;">✔</span> Unlimited Invoice Processing</li>
                        <li style="margin-bottom: 0.5rem;"><span style="color: #10b981; margin-right: 0.5rem;">✔</span> Direct QuickBooks Sync</li>
                        <li style="margin-bottom: 0.5rem;"><span style="color: #10b981; margin-right: 0.5rem;">✔</span> Priority Support</li>
                        <li style="margin-bottom: 0.5rem;"><span style="color: #10b981; margin-right: 0.5rem;">✔</span> Early Access to New Features</li>
                    </ul>
                    <a href="{gumroad_checkout_url}" target="_blank" style="
                        display: inline-block;
                        background-color: #4f46e5; /* Indigo 600 */
                        color: white;
                        padding: 0.75rem 1.5rem;
                        text-align: center;
                        border-radius: 0.5rem;
                        text-decoration: none;
                        font-weight: 600;
                        font-size: 1.1rem;
                        width: 100%;
                        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                        transition: all 0.2s ease-in-out;
                    ">
                        Subscribe Now
                    </a>
                    <div style="font-size: 0.75rem; color: #9ca3af; text-align: center; margin-top: 0.5rem;">
                        Secured by Gumroad
                    </div>
                </div>
                """, unsafe_allow_html=True)


    # --- Main Content Area ---
    st.title("AI Invoice Parser")
    st.subheader("Automate your bookkeeping with intelligent invoice extraction.")

    if st.session_state.user:
        if st.session_state.credits <= 0:
            st.warning("You have no credits left. Please upgrade to a Pro Plan to continue processing invoices.")
            # --- Out of Credits Button ---
            gumroad_checkout_url = "https://tyzclj.gumroad.com/l/quickbills"
            st.markdown(f"""
            <a href="{gumroad_checkout_url}" target="_blank" style="
                display: inline-block;
                background-color: #ef4444; /* Red 500 */
                color: white;
                padding: 0.75rem 1.5rem;
                text-align: center;
                border-radius: 0.5rem;
                text-decoration: none;
                font-weight: 700;
                font-size: 1.1rem;
                width: 100%;
                max-width: 300px; /* Limit width */
                margin-top: 1rem;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                transition: all 0.2s ease-in-out;
            ">
                Upgrade to Pro Plan
            </a>
            """, unsafe_allow_html=True)
            st.stop() # Stop further execution if no credits

    # --- Upload Section ---
    uploaded_file = st.file_uploader(
        "Upload an invoice (PDF or Image)",
        type=["pdf", "png", "jpg", "jpeg"],
        help="Supported formats: PDF, PNG, JPG, JPEG. Max file size: 10MB."
    )

    if uploaded_file is not None:
        file_details = {"filename": uploaded_file.name, "filetype": uploaded_file.type}
        st.write("File uploaded:", file_details)

        file_bytes = uploaded_file.read()
        
        # Use a temporary file to save the uploaded content if needed by underlying libraries
        # with NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
        #     tmp_file.write(file_bytes)
        #     tmp_file_path = tmp_file.name

        extractor = get_extractor_v6()
        data = None

        status = st.status("Processing invoice...", expanded=True)

        if "pdf" in uploaded_file.type:
            st.info("Detected PDF upload. Starting text extraction...")
            status.update(label="Extracting text from PDF...", state="running", expanded=True)
            try:
                # Reverted OCR fallback for now, focusing on text-based PDFs as per user request
                data = extractor.process_pdf(file_bytes)
                st.info("PDF text extraction completed.")
            except Exception as e:
                st.error(f"PDF Processing Error: {e}\n\nFull Traceback:\n```\n{traceback.format_exc()}\n```")
                status.update(label="PDF Processing Failed", state="error", expanded=True)
                return
        elif uploaded_file.type.startswith("image"):
            st.info("Detected image upload. Starting OCR process...")
            st.write("Optimizing image for OCR...")
            try:
                data = extractor.extract_from_image(file_bytes)
                st.info("Image OCR processing completed.")
            except Exception as e:
                st.error(f"Image OCR Error: {e}\n\nFull Traceback:\n```\n{traceback.format_exc()}\n```")
                status.update(label="Image Processing Failed", state="error", expanded=True)
                return

        if data:
            status.update(label="AI processing invoice data...", state="running", expanded=True)
            # Further processing (AI extraction, etc.) would go here
            # For now, let's assume 'data' is the final extracted info

            st.success("Invoice processed successfully!")
            status.update(label="Invoice Processing Complete", state="complete", expanded=False)

            st.subheader("Extracted Data")
            st.json(data)

            # --- Display Items in a Table ---
            if "items" in data and data["items"]:
                st.subheader("Line Items")
                # Convert items to DataFrame for display
                items_df = pd.DataFrame(data["items"])
                st.dataframe(items_df, use_container_width=True)

            # --- Download CSV Button ---
            csv_data = generate_quickbooks_csv(data)
            st.download_button(
                label="Download CSV File",
                data=csv_data,
                file_name=f"{file_details['filename'].split('.')[0]}_quickbills.csv",
                mime="text/csv",
                key="download_csv_button"
            )

            # --- Sync to QuickBooks Button ---
            # Changed as per user request to reflect "Pro Plan Coming Soon"
            st.button("Auto-Sync (Pro Plan Coming Soon)", disabled=True)

            # --- Credit Deduction ---
            if st.session_state.user:
                if st.session_state.credits > 0:
                    st.session_state.credits -= 1 # Deduct one credit per successful processing
                    # In a real app, update this in Supabase:
                    # supabase.update_user_credits(st.session_state.user.id, st.session_state.credits)
                    st.sidebar.write(f"Credits remaining: {st.session_state.credits}")
                    st.success("1 credit deducted for processing.")
                else:
                    st.warning("No credits to deduct. This should not happen if previous check works.")

        else:
            st.error("Error: Could not extract data from the invoice.")
            status.update(label="Extraction Failed", state="error", expanded=True)

    st.markdown("""
    ---
    <div style="text-align: center; font-size: 0.8rem; color: #6b7280; margin-top: 2rem;">
        <p>© 2026 QuickBills AI. All rights reserved.</p>
        <p>
            <a href="?nav=privacy" target="_self" style="color: #6b7280; text-decoration: none;">Privacy Policy</a>
            <span style="margin: 0 0.5rem;">|</span>
            <a href="?nav=terms" target="_self" style="color: #6b7280; text-decoration: none;">Terms of Service</a>
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
