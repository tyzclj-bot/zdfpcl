import streamlit as st
import pandas as pd
import json # Added for force_extract_dump
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

def force_extract_dump(obj):
    st.write(f"DEBUG: force_extract_dump received: {type(obj)} - {obj}") # Debug print
    """
    暴力解包器：不管传入的是 tuple、list 还是 Pydantic 对象，
    强行找出带有 model_dump 或 dict 方法的实例并提取数据！
    """
    # 如果是字符串，尝试解析 JSON
    if isinstance(obj, str):
        try:
            parsed_json = json.loads(obj)
            # 如果解析出的 JSON 是一个字典且包含关键字段，认为找到了真实数据
            if isinstance(parsed_json, dict) and ("total_amount" in parsed_json or "totalAmt" in parsed_json):
                st.write(f"DEBUG: force_extract_dump returning JSON dict: {parsed_json}") # Debug print
                return parsed_json
            # 如果解析出的 JSON 是一个列表，遍历列表元素
            if isinstance(parsed_json, list):
                for item in parsed_json:
                    if isinstance(item, dict) and ("total_amount" in item or "totalAmt" in item):
                        st.write(f"DEBUG: force_extract_dump returning JSON list item: {item}") # Debug print
                        return item # 返回第一个包含关键字段的字典
        except json.JSONDecodeError:
            pass # 不是有效的 JSON 字符串，继续下面的逻辑

    # 如果是个 tuple 或 list，遍历它，把真正的数据体找出来
    if isinstance(obj, (tuple, list)):
        for item in obj:
            # 递归调用自身，处理嵌套的可能
            extracted = force_extract_dump(item)
            # 如果递归调用返回了非兜底数据，说明找到了
            if extracted and not (extracted.get("fallback_data") or extracted.get("raw_extracted_data")):
                st.write(f"DEBUG: force_extract_dump returning extracted from list/tuple: {extracted}") # Debug print
                return extracted
        # 如果遍历完所有元素都没找到，再尝试通用兜底
        returned_data = {"raw_extracted_data": str(obj)}
        st.write(f"DEBUG: force_extract_dump returning raw_extracted_data: {returned_data}") # Debug print
        return returned_data
    
    # 如果直接就是 Pydantic 对象
    if hasattr(obj, 'model_dump'):
        returned_data = obj.model_dump()
        st.write(f"DEBUG: force_extract_dump returning model_dump: {returned_data}") # Debug print
        return returned_data
    elif hasattr(obj, 'dict'):
        returned_data = obj.dict()
        st.write(f"DEBUG: force_extract_dump returning dict: {returned_data}") # Debug print
        return returned_data
    
    # 终极兜底
    returned_data = {"fallback_data": str(obj)}
    st.write(f"DEBUG: force_extract_dump returning fallback_data: {returned_data}") # Debug print
    return returned_data


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
                # This ensures that even if session state is lost (e.g., during app restart or hard refresh),
                # the verifier can be reconstructed based on a known, fixed value, allowing the auth flow
                # to complete without an "Invalid Grant" error.
                if not verifier:
                    verifier = FIXED_VERIFIER # Use the fixed verifier
                
                st.write(f"DEBUG: Attempting to exchange code with verifier: {verifier}") # Debug print
                try:
                    with st.spinner("Logging you in..."):
                        # Use the verifier in the code exchange
                        st.session_state.user, st.session_state.access_token = supabase.exchange_code_for_session(code, verifier)
                        st.write(f"DEBUG: Login successful. User: {st.session_state.user}") # Debug print
                        # Clear the code from the URL to prevent re-exchange on refresh
                        st.query_params.clear()
                        st.rerun()
                except Exception as e:
                    st.error(f"Authentication failed: {e}")
                    st.query_params.clear() # Clear problematic params
                    st.session_state.user = None
                    st.session_state.access_token = None
                    st.rerun()
            
            if st.session_state.user:
                st.markdown(f"""
                    <div class="account-card">
                        <img src="https://api.dicebear.com/7.x/initials/svg?seed={st.session_state.user.email}" class="user-avatar">
                        <p style="font-weight: 600; margin-bottom: 0.25rem;">{st.session_state.user.email}</p>
                        <p class="user-id">ID: {st.session_state.user.id[:8]}...</p>
                        <div class="secure-badge"><i class="fa-solid fa-lock"></i> Securely Authenticated</div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Credit display
                st.markdown("""
                    <div class="credit-card">
                        <p class="credit-label">Remaining Credits</p>
                        <p class="credit-amount">{st.session_state.credits}</p>
                    </div>
                """, unsafe_allow_html=True)
                
                if st.button("Logout", type="secondary"):
                    with st.spinner("Logging out..."):
                        supabase.sign_out()
                        st.session_state.user = None
                        st.session_state.access_token = None
                        st.session_state.credits = 0
                        st.rerun()
                
                # Direct QuickBooks Sync Button
                # st.markdown("""<div style="margin-top: 1rem;">""", unsafe_allow_html=True)
                # if st.button("Connect to QuickBooks", type="primary", key="connect_qb_btn"):
                #     # This would initiate the OAuth2 flow for QuickBooks
                #     st.info("QuickBooks integration coming soon! Join the waitlist.")
                #     show_waitlist_modal()
                # st.markdown("""</div>""", unsafe_allow_html=True)

                st.markdown("""<div style="margin-top: 1rem;">""", unsafe_allow_html=True)
                if st.button("Direct QuickBooks Sync (Beta)", type="primary", key="connect_qb_btn"):
                    show_waitlist_modal()
                st.markdown("""</div>""", unsafe_allow_html=True)

            else:
                st.info("Login to sync invoices directly to QuickBooks.")
                
                # Google OAuth Login
                # Ensure the redirect_uri matches your Streamlit app's URL
                google_signin_url = supabase.get_google_oauth_authorize_url(
                    redirect_uri=os.getenv("SUPABASE_REDIRECT_URI"),
                    # Optionally pass a state/verifier for PKCE flow (recommended)
                    # For simplicity, we're using a fixed verifier for now
                    # In a real app, generate a random one and store in session_state
                    state=FIXED_VERIFIER # Using fixed verifier for development
                )
                
                st.markdown(f"""
                    <a href="{google_signin_url}" target="_self" style="
                        display: inline-block;
                        background-color: #DB4437; /* Google Red */
                        color: white;
                        padding: 0.75rem 1.5rem;
                        text-decoration: none;
                        border-radius: 6px;
                        font-weight: 600;
                        text-align: center;
                        margin-top: 1rem;
                        width: 100%;
                    ">
                        <i class="fab fa-google"></i> Sign in with Google
                    </a>
                """, unsafe_allow_html=True)
                
                # Email/Password Login (optional)
                # with st.expander("Or sign in with Email", expanded=False):
                #     email = st.text_input("Email")
                #     password = st.text_input("Password", type="password")
                #     if st.button("Sign In"):
                #         try:
                #             user, token = supabase.sign_in_with_email(email, password)
                #             st.session_state.user = user
                #             st.session_state.access_token = token
                #             st.success("Logged in successfully!")
                #             st.rerun()
                #         except Exception as e:
                #             st.error(f"Login failed: {e}")

            st.markdown("---")
            st.markdown("**Resources**")
            st.markdown("[Help & Support](?nav=contact)")
            st.markdown("[Privacy Policy](?nav=privacy)")
            st.markdown("[Terms of Service](?nav=terms)")

    # --- Main Content ---
    st.title("AI Invoice Parser")
    st.markdown("Upload an invoice PDF or image, and our AI will extract key data points.")

    # File uploader
    uploaded_file = st.file_uploader("Choose an invoice file (PDF or Image)", type=["pdf", "png", "jpg", "jpeg"], key="invoice_uploader")

    extractor = get_extractor_v6()

    if uploaded_file is not None:
        file_type = uploaded_file.type
        st.write(f"DEBUG: Uploaded file type: {file_type}") # Debug print

        # Display spinner while processing
        with st.spinner(f"Processing {uploaded_file.name}..."):
            file_bytes = uploaded_file.getvalue()
            data = None
            
            if "pdf" in file_type:
                st.write("DEBUG: Processing as PDF") # Debug print
                # Use a NamedTemporaryFile for PDF processing
                with NamedTemporaryFile(delete=True, suffix=".pdf") as tmp_file:
                    tmp_file.write(file_bytes)
                    tmp_file_path = tmp_file.name
                    st.write(f"DEBUG: PDF written to temporary file: {tmp_file_path}") # Debug print
                    try:
                        data = extractor.process_pdf(tmp_file_path)
                        st.write(f"DEBUG: Data after process_pdf: {data}") # Debug print
                    except ValueError as ve:
                        st.warning(str(ve))
                        st.info("If this is a scanned PDF without embedded text, it might require OCR which is currently not fully integrated for PDFs.")
                    except Exception as e:
                        st.error(f"An unexpected error occurred during PDF processing: {e}")
                        st.exception(e) # Display full traceback in Streamlit
                        data = {"error": f"PDF processing failed: {e}", "raw_output": ""} # Fallback data
            elif "image" in file_type:
                st.write("DEBUG: Processing as image") # Debug print
                try:
                    data = extractor.extract_from_image(file_bytes)
                    st.write(f"DEBUG: Data after extract_from_image: {data}") # Debug print
                except Exception as e:
                    st.error(f"An error occurred during image processing: {e}")
                    st.exception(e) # Display full traceback
                    data = {"error": f"Image processing failed: {e}", "raw_output": ""} # Fallback data
            else:
                st.warning("Unsupported file type.")

            # Apply force_extract_dump to ensure consistent dictionary output
            if data is not None:
                st.write(f"DEBUG: Before force_extract_dump, data type: {type(data)}, value: {data}") # Debug print
                data = force_extract_dump(data)
                st.write(f"DEBUG: Data after force_extract_dump in main: {data}") # Debug print

            # Display extracted data
            if data and not data.get("fallback_data") and not data.get("error"):
                st.success("Invoice data extracted successfully!")
                
                # Check for critical fields
                vendor_name = data.get("vendor_name", "N/A")
                total_amount = data.get("total_amount", 0.0)
                currency = data.get("currency", "USD")
                invoice_number = data.get("invoice_number", "N/A")
                date = data.get("date", "N/A")
                items = data.get("items", [])

                st.subheader("Extracted Information")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Vendor Name", vendor_name)
                with col2:
                    st.metric("Total Amount", f"{currency} {total_amount:,.2f}")
                with col3:
                    st.metric("Invoice Number", invoice_number)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Date", date)
                with col2:
                    st.metric("Tax Amount", f"{currency} {data.get("tax_amount", 0.0):,.2f}")
                with col3:
                    st.metric("Due Date", data.get("due_date", "N/A"))

                if items:
                    st.subheader("Line Items")
                    # Convert items to DataFrame for better display
                    items_df = pd.DataFrame(items)
                    # Reorder columns for better readability
                    if not items_df.empty:
                        desired_columns = [
                            "description", "quantity", "unit_price", "total_price", "category"
                        ]
                        # Add missing columns with None/NaN values if they don't exist
                        for col in desired_columns:
                            if col not in items_df.columns:
                                items_df[col] = None
                        items_df = items_df[desired_columns]
                        st.dataframe(items_df, use_container_width=True)
                else:
                    st.info("No line items extracted.")

                # Raw AI Output (for debugging/advanced users)
                with st.expander("Raw AI Output (JSON)"):
                    # Display the data after force_extract_dump
                    st.json(data)
                
                # Generate CSV for QuickBooks
                csv_data = generate_quickbooks_csv(data)
                st.download_button(
                    label="Download QuickBooks CSV",
                    data=csv_data,
                    file_name=f"{vendor_name.replace(' ', '_')}_invoice_{invoice_number}_QB.csv",
                    mime="text/csv",
                    key="download_csv_button"
                )

            elif data and data.get("error"):
                st.error("An error occurred during extraction.")
                with st.expander("Error Details"):
                    st.json(data)
            elif data and data.get("fallback_data"):
                st.warning("Could not extract structured data. Displaying fallback data.")
                st.json(data)
            else:
                st.info("Upload an invoice file to see extracted data here.")
    else:
        st.info("Waiting for an invoice file upload.")

if __name__ == "__main__":
    main()
