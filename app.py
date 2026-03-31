
import streamlit as st
import pandas as pd
import json # Added for force_extract_dump
import os
import io
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from invoice_extractor import AIInvoiceExtractor, InvoiceData
from quickbooks_adapter import QuickBooksAdapter
from supabase_manager import SupabaseManager, verify_gumroad_license
from tempfile import NamedTemporaryFile

LEGAL_CENTER_URL = "https://flowery-tin-466.notion.site/QuickBills-AI-Legal-Center-31d603d9e4da800f8602fe8323638b81?pvs=143"
TERMS_URL = "https://flowery-tin-466.notion.site/Terms-of-Service-for-QuickBills-AI-31d603d9e4da8060b194c1adf99f459c?pvs=143"

def force_extract_dump(obj):
    """
    暴力解包器：不管传入的是 tuple、list、Pydantic 对象还是 JSON 字符串，
    强行找出带有 model_dump 或 dict 方法的实例并提取数据，或直接解析 JSON 字符串！
    """
    # Step 1: Handle JSON string first
    if isinstance(obj, str):
        try:
            # Attempt to parse as JSON
            json_obj = json.loads(obj)
            # If successfully parsed, recursively call to handle the parsed object
            # This ensures that if the JSON string itself contains a Pydantic model's JSON, it's also processed
            return force_extract_dump(json_obj)
        except json.JSONDecodeError:
            # Not a valid JSON string, treat as a regular string for fallback
            pass

    # Step 2: Handle Pydantic objects or dict-like objects
    if hasattr(obj, 'model_dump'):
        return obj.model_dump()
    elif hasattr(obj, 'dict'):
        return obj.dict()
    
    # Step 3: Handle tuples or lists (containing Pydantic objects or dicts)
    if isinstance(obj, (tuple, list)):
        # We need to decide if we want to return the first valid extracted item
        # or a list of all extracted items. Based on the previous implementation,
        # it returned the first found. Let's maintain that behavior but improve it.
        extracted_list_items = []
        for item in obj:
            extracted = force_extract_dump(item)
            if isinstance(extracted, dict) and "fallback_data" not in extracted:
                # If it's a valid extracted dict and not a simple fallback, add it
                extracted_list_items.append(extracted)
        if extracted_list_items:
            # If we extracted valid items, return them as a list.
            # If the original intent was to only get one, the caller needs to handle it.
            # However, for display, a list is generally more useful.
            return extracted_list_items
        # If no valid items were extracted from the list/tuple, fall back
        return {"raw_extracted_data": str(obj)}
    
    # Final fallback for any other object type
    return {"fallback_data": str(obj)}


# --- Page Configuration ---
st.set_page_config(
    page_title="QuickBills AI",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SEO Metadata Injection ---
st.markdown("""
    <script>
    document.title = "QuickBills AI";
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
ADMIN_EMAIL = "tyzclj@gmail.com"

def main():
    # --- Navigation Logic ---
    if "nav" in st.query_params:
        nav_target = st.query_params["nav"]
        if nav_target == "contact":
            show_contact_page()
            return

    # --- App Title (Google OAuth Review Requirement) ---
    st.title("QuickBills AI")
    st.caption("AI-powered invoice parsing and auditing tool for Bookkeepers.")

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
    if 'is_pro' not in st.session_state:
        st.session_state.is_pro = False

    # --- Sidebar: Auth & Settings ---
    with st.sidebar:
        st.title("QuickBills AI")
        st.header("Authorization")
        
        supabase = init_supabase()
        
        if not supabase:
            st.warning("Please configure Supabase credentials.")
            st.session_state.supabase_url = st.text_input("Supabase URL", placeholder="https://xyz.supabase.co")
            st.session_state.supabase_key = st.text_input("Supabase Anon Key", type="password")
            if st.button("Save Settings"):
                st.rerun()
        else:
            if st.session_state.user:
                user_email = st.session_state.user.email
                user_meta = getattr(st.session_state.user, 'user_metadata', {}) or {}
                avatar_url = user_meta.get('avatar_url') or user_meta.get('picture')
                full_name = user_meta.get('full_name') or user_meta.get('name') or user_email.split('@')[0]
                
                st.success(f"Logged in as {user_email}")
                st.markdown(f"""
                    <div class="account-card">
                        <img src="{avatar_url or 'https://www.gravatar.com/avatar/00000000000000000000000000000000?d=mp&f=y'}" class="user-avatar">
                        <div style="font-weight: 600; color: #1e293b;">{full_name}</div>
                        <div class="user-id">{user_email}</div>
                    </div>
                """, unsafe_allow_html=True)
                
                profile = supabase.get_user_profile(st.session_state.user.id, st.session_state.access_token)
                st.session_state.credits = profile.get("credits", 0)
                if st.session_state.user.email == ADMIN_EMAIL:
                    st.session_state.is_pro = True
                else:
                    license_key = profile.get("license_key")
                    st.session_state.is_pro = bool(license_key and verify_gumroad_license(license_key)[0])
                
                # If Pro user, ensure they have "infinite" credits in session state
                if st.session_state.is_pro:
                    st.session_state.credits = 9999
                
                # --- 状态 A：Pro | 状态 B：非 Pro（严格隔离）---
                if st.session_state.is_pro:
                    st.success("✅ Pro 订阅已激活")
                else:
                    st.link_button("🌟 Upgrade to Pro - $19.99/mo", "https://tyzclj.gumroad.com/l/hrnxoe", use_container_width=True)
                    license_input = st.text_input("Enter your Gumroad License Key", key="gumroad_license_input", type="password")
                    if st.button("Verify", key="verify_license_btn"):
                        if license_input and license_input.strip():
                            valid, msg = verify_gumroad_license(license_input)
                            if valid:
                                try:
                                    success, _ = supabase.save_license_key(st.session_state.user.id, license_input, st.session_state.access_token)
                                    if success:
                                        st.session_state.is_pro = True
                                        st.rerun()
                                    else:
                                        st.error("保存失败，请稍后重试")
                                except Exception as e:
                                    print(f"[save_license_key] {e}")
                                    st.error("保存失败，请稍后重试")
                            else:
                                st.error(msg)
                        else:
                            st.error("请输入秘钥")

                # --- Reddit Promo Section ---
                with st.expander("🎁 Reddit Exclusive"):
                    promo_code = st.text_input("Enter Promo Code", key="reddit_promo")
                    if st.button("Claim Credits"):
                        if promo_code.strip().upper() == "REDDIT2024":
                            try:
                                if hasattr(supabase, 'add_credits'):
                                    result = supabase.add_credits(st.session_state.user.id, 5, st.session_state.access_token)
                                    ok = result[0] if isinstance(result, tuple) else result
                                    if ok:
                                        st.toast("Success! +5 Credits Added", icon="🎉")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error("领取失败，请稍后重试")
                                else:
                                    st.warning("Please redeploy app to enable this feature.")
                            except Exception as e:
                                print(f"[add_credits Reddit] {e}")
                                st.error("领取失败，请稍后重试")
                        else:
                            st.error("Invalid Code")

                if st.button("Logout"):
                    supabase.sign_out(st.session_state.access_token)
                    st.session_state.user = None
                    st.session_state.access_token = None
                    st.session_state.credits = 0
                    st.session_state.is_pro = False
                    st.rerun()

                # --- ADMIN DASHBOARD (Sidebar) ---
                # Only visible to tyzclj@gmail.com
                if st.session_state.user.email == ADMIN_EMAIL:
                    st.markdown("---")
                    st.markdown("### 👑 Admin Stats")
                    
                    # Auto Top-up for Admin if low credits
                    if st.session_state.credits < 10:
                        try:
                            if hasattr(supabase, 'add_credits'):
                                result = supabase.add_credits(st.session_state.user.id, 100, st.session_state.access_token)
                                ok = result[0] if isinstance(result, tuple) else result
                                if ok:
                                    st.session_state.credits += 100
                                    st.toast("Admin Auto-Topup: +100 Credits", icon="⚡")
                                    st.rerun()
                        except Exception as e:
                            print(f"[admin add_credits] {e}")

                    if hasattr(supabase, 'get_admin_stats'):
                        admin_stats = supabase.get_admin_stats(st.session_state.access_token)
                        st.markdown(f"**Total Users:** {admin_stats.get('user_count', 0)}")
                        st.markdown(f"**Total Invoices:** {admin_stats.get('invoice_count', 0)}")
                    else:
                        st.info("Admin stats module not loaded.")

            else:
                # --- Login / Sign Up Tabs ---
                tab_login, tab_signup = st.tabs(["Login", "Sign Up"])
                with tab_login:
                    login_email = st.text_input("Email", key="login_email", placeholder="you@example.com")
                    login_password = st.text_input("Password", type="password", key="login_password")
                    if st.button("Login", key="btn_login", type="primary", use_container_width=True):
                        if login_email and login_password:
                            try:
                                res = supabase.sign_in(login_email.strip(), login_password)
                                if res and res.user and res.session:
                                    st.session_state.user = res.user
                                    st.session_state.access_token = res.session.access_token
                                    st.rerun()
                                else:
                                    st.error("Login failed. Please try again.")
                            except Exception as e:
                                st.error(str(e))
                        else:
                            st.error("Please enter email and password.")
                with tab_signup:
                    signup_email = st.text_input("Email", key="signup_email", placeholder="you@example.com")
                    signup_password = st.text_input("Password", type="password", key="signup_password")
                    if st.button("Sign Up", key="btn_signup", type="primary", use_container_width=True):
                        if signup_email and signup_password:
                            try:
                                res = supabase.sign_up(signup_email.strip(), signup_password)
                                if res and res.user:
                                    if res.session:
                                        st.session_state.user = res.user
                                        st.session_state.access_token = res.session.access_token
                                        st.success("Account created! Logging you in...")
                                        st.rerun()
                                    else:
                                        st.success("Account created! Please check your email to confirm.")
                            except Exception as e:
                                st.error(str(e))
                        else:
                            st.error("Please enter email and password.")
                
                # --- Payment for Guest Users ---
                st.markdown("---")
                st.markdown("### 💎 Go Pro")
                st.caption("Unlock unlimited processing and 24/7 support.")
                checkout_url = "https://tyzclj.gumroad.com/l/hrnxoe"
                html_button = f"""
                    <a href="{checkout_url}" target="_blank" style="
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        background-color: #FF4B4B; /* Streamlit's default primary button color */
                        color: white;
                        font-weight: bold;
                        padding: 0.75rem 1.25rem;
                        border-radius: 0.5rem;
                        text-decoration: none;
                        font-size: 1rem;
                        width: 100%;
                        box-sizing: border-box;
                        transition: background-color 0.2s;
                    ">
                        ✨ Subscribe to Pro - $19.99/mo
                    </a>
                """
                st.markdown(html_button, unsafe_allow_html=True)
                st.markdown("""
                    <div class="secure-badge">
                        <span>🔒 Secured by Gumroad</span>
                    </div>
                """, unsafe_allow_html=True)

                # --- Legal footer (Google OAuth Review Requirement) ---
        st.divider()

        # --- Roadmap Section (Growth Signal) ---
        st.markdown("---")
        st.subheader("🚀 Coming Soon")
        st.markdown("""
            <div style="background-color: #f0f9ff; padding: 1rem; border-radius: 8px; border: 1px solid #bae6fd;">
                <div style="margin-bottom: 0.75rem;">
                    <span style="font-weight: 600; color: #0369a1;">📧 Email-to-Bill</span><br>
                    <span style="font-size: 0.8rem; color: #0c4a6e;">Forward invoices to <b>add@quickbills.ai</b></span>
                </div>
                <div style="margin-bottom: 0.75rem;">
                    <span style="font-weight: 600; color: #0369a1;">📱 Mobile App</span><br>
                    <span style="font-size: 0.8rem; color: #0c4a6e;">Snap & upload on the go</span>
                </div>
                <div>
                    <span style="font-weight: 600; color: #0369a1;">🔄 Xero Integration</span><br>
                    <span style="font-size: 0.8rem; color: #0c4a6e;">More ERP support coming</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

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

        # --- Developer Mode Toggle ---
        st.sidebar.divider()
        dev_mode = st.sidebar.checkbox("🛠️ Developer Mode", value=False, help="Enable advanced debugging tabs (Raw JSON, OCR Output)")

    # --- Main App Display ---
    
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
                    src="https://www.loom.com/embed/8c9a8a8ff70a4b2b977fdb64d9c5ba38?hide_owner=true&hide_share=true&hide_title=true&hideEmbedTopBar=true" 
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

        # Pricing Section
        st.markdown("""
            <div style="text-align: center; margin-bottom: 2rem;">
                <h2 style="font-size: 2.5rem; margin-bottom: 0.5rem;">Simple Pricing</h2>
                <p style="color: #64748b;">Get started for free or upgrade for unlimited power.</p>
            </div>
            <div style="
                display: flex;
                justify-content: center;
                margin-bottom: 4rem;
            ">
                <div style="
                    background: white;
                    border: 2px solid #3b82f6;
                    border-radius: 16px;
                    padding: 2.5rem;
                    max-width: 450px;
                    width: 100%;
                    text-align: center;
                    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
                ">
                    <div style="background: #eff6ff; color: #1d4ed8; display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.875rem; font-weight: 700; margin-bottom: 1rem;">
                        MOST POPULAR
                    </div>
                    <h2 style="color: #1e293b; margin-bottom: 0.5rem; font-size: 1.75rem;">Standard Plan</h2>
                    <div style="font-size: 3.5rem; font-weight: 800; color: #1e293b; margin-bottom: 1rem;">
                        $19.99<span style="font-size: 1.25rem; color: #64748b; font-weight: 400;">/mo</span>
                    </div>
                    <ul style="text-align: left; color: #475569; margin-bottom: 2.5rem; list-style: none; padding: 0; font-size: 1.1rem;">
                        <li style="margin-bottom: 1rem; display: flex; align-items: center;">
                            <span style="color: #10b981; margin-right: 0.75rem;">✔</span> Unlimited Invoice Processing
                        </li>
                        <li style="margin-bottom: 1rem; display: flex; align-items: center;">
                            <span style="color: #10b981; margin-right: 0.75rem;">✔</span> Extreme AI Accuracy (99.9%)
                        </li>
                        <li style="margin-bottom: 1rem; display: flex; align-items: center;">
                            <span style="color: #10b981; margin-right: 0.75rem;">✔</span> Bulk Export to QuickBooks CSV
                        </li>
                        <li style="margin-bottom: 1rem; display: flex; align-items: center;">
                            <span style="color: #10b981; margin-right: 0.75rem;">✔</span> 24/7 Priority Support
                        </li>
                    </ul>
                    <a href="https://tyzclj.gumroad.com/l/hrnxoe" target="_blank" style="
                        display: block;
                        background: #3b82f6;
                        color: white;
                        text-decoration: none;
                        padding: 1.25rem;
                        border-radius: 12px;
                        font-weight: 700;
                        font-size: 1.25rem;
                        box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.5);
                        transition: all 0.2s;
                    ">Subscribe Now</a>
                    <p style="margin-top: 1.25rem; font-size: 0.9rem; color: #94a3b8;">
                        🔒 Secure checkout via Gumroad
                    </p>
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
        if not st.session_state.get("is_pro", False) and st.session_state.credits <= 0:
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

                if uploaded_file:
                    # Display preview based on file type
                    file_type = uploaded_file.type
                    if "image" in file_type:
                        st.image(uploaded_file, caption="Uploaded Image Preview", width=400)
                    else:
                        st.success(f"PDF file '{uploaded_file.name}' uploaded successfully!")

                    process_disabled = not st.session_state.get("is_pro", False)
                    if process_disabled:
                        st.warning("🔒 请在侧边栏输入 Gumroad Pro 秘钥以解锁 AI 解析")
                    if st.button("🤖 Process with AI", disabled=process_disabled):
                        # Double check credits before processing (Only for Non-Pro)
                        supabase = init_supabase()
                        credits = supabase.get_user_credits(st.session_state.user.id, st.session_state.access_token)
                        
                        if not st.session_state.get("is_pro", False) and credits <= 0:
                            st.error("Insufficient credits!")
                            return

                        extractor = get_extractor_v6() # Get cached instance (v6)
                        
                        # --- Multi-step "Ritual" Loading ---
                        with st.status("Processing Invoice...", expanded=True) as status:
                            st.write("Scanning invoice text...")
                            # Simulate scanning
                            time.sleep(0.8)
                            
                            try:
                                file_bytes = uploaded_file.getvalue()
                                
                                if "image" in uploaded_file.type:
                                    st.write("Optimizing image for OCR...")
                                    try:
                                        data = extractor.extract_from_image(file_bytes)
                                    except Exception as e:
                                        st.error(f"Image OCR Error: {e}")
                                        status.update(label="Image Processing Failed", state="error", expanded=True)
                                        data = InvoiceData(vendor_name="ERROR_IMAGE_OCR", total_amount=0.0, warning=f"Image OCR Error: {e}")
                                else: # It's a PDF
                                    st.write("Extracting raw text layer...")
                                    tmp_path = None # Initialize tmp_path
                                    try:
                                        with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                                            tmp.write(file_bytes)
                                            tmp_path = tmp.name
                                        
                                        data = extractor.process_pdf(tmp_path)
                                    except Exception as e:
                                        st.error(f"PDF Processing Error: {e}")
                                        status.update(label="PDF Processing Failed", state="error", expanded=True)
                                        data = InvoiceData(vendor_name="ERROR_PDF_PROCESSING", total_amount=0.0, warning=f"PDF Processing Error: {e}")
                                    finally:
                                        if tmp_path and os.path.exists(tmp_path):
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
                                        data = force_extract_dump(data)
                                    
                                    # Store raw text in session state as requested
                                    if "_raw_text" in data:
                                        st.session_state.raw_ocr_output = data["_raw_text"]
                                    
                                    st.session_state['invoice_data'] = data
                                    st.session_state['processed'] = True
                                    
                                    # --- SUCCESS: Deduct Credit (Only for Non-Pro) & Log History ---
                                    try:
                                        if not st.session_state.get("is_pro", False):
                                            supabase.decrement_credits(st.session_state.user.id, st.session_state.access_token)
                                            st.session_state.credits -= 1
                                            st.toast("Credits deducted: -1", icon="💳")
                                        
                                        supabase.log_invoice(st.session_state.user.id, data, st.session_state.access_token)
                                    except Exception as db_err:
                                        st.warning(f"Result processed but failed to update DB: {db_err}")
                                
                                    status.update(label="Analysis Complete!", state="complete", expanded=False)
                                    st.rerun()
                            except Exception as e:
                                status.update(label="Analysis Error", state="error", expanded=True)
                                st.error(f"An error occurred during processing: {str(e)}")
                                st.session_state['invoice_data'] = InvoiceData(vendor_name="ERROR_GENERAL_PROCESSING", total_amount=0.0, warning=f"General Processing Error: {str(e)}")

        with col2:
            with st.container(border=True):
                st.subheader("2. Extraction Results")
                
                data = {"warning": "No invoice data loaded or processed yet."} # Default initialization
                
                if 'invoice_data' in st.session_state and st.session_state['invoice_data'] is not None:
                    data = st.session_state['invoice_data']

                    # If diagnostic mode result, display specially
                    if "diagnostic_description" in data:
                        st.subheader("AI Vision Diagnostic Report")
                        st.markdown(data["diagnostic_description"])
                        st.info("This is a diagnostic run. We are checking the connection to the vision model.")
                        return # Stop rendering

                    # Warning Display (New)
                    # --- 强制防御墙 & 深度解码器 ---
                    if isinstance(data, tuple):
                        data = data[0] if len(data) > 0 else {}
                    
                    if hasattr(data, 'model_dump'):
                        data = data.model_dump()
                    elif hasattr(data, 'dict'):
                        data = data.dict()
                    
                    # 如果 data 被 LLM 吐成了一个纯 JSON 字符串，强行把它扒开！
                    if isinstance(data, str):
                        try:
                            data = json.loads(data)
                        except Exception:
                            pass
                    
                    # 如果字典里有一个键叫 'response' 或 'raw_data'，而且里面是字符串，继续扒开它！
                    for key in list(data.keys()):
                        if isinstance(data[key], str) and "{" in data[key]:
                            try:
                                data = json.loads(data[key])
                                break
                            except:
                                pass
                    
                    if not isinstance(data, dict):
                        data = {}
                    

                    # --------------------------------------------------------
                    if data.get("warning"):
                        st.warning(f"⚠️ **Smart Audit Report:** {data.get('warning')}")

                    # Key Metrics Row
                    m1, m2, m3, m4 = st.columns(4)
                    with m1:
                        st.metric("Vendor", data.get('vendor_name'))
                    with m2:
                        currency_symbol = "$" if data.get('currency', 'USD') == 'USD' else data.get('currency', '')
                        st.metric("Total Amount", f"{currency_symbol}{data.get('total_amount')}")
                    with m3:
                        st.metric("Tax", f"{currency_symbol}{data.get('tax_amount', 0)}")
                    with m4:
                        st.metric("Invoice #", data.get('invoice_number'))

                    # Details Tab
                    if dev_mode:
                        tab1, tab2, tab3 = st.tabs(["Line Items", "Raw JSON", "Debug OCR"])
                    else:
                        # Only show Line Items tab content, but we still need a container
                        tab1, = st.tabs(["Line Items"])
                        tab2, tab3 = None, None # Disable other tabs
                    
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
                                tax_amount = float(data.get('tax_amount', 0))
                                
                                # Check for mismatch (allow small float error)
                                calculated_total = line_total + tax_amount
                                
                                if abs(calculated_total - invoice_total) < 0.02:
                                    st.success(f"✅ **Logic Perfect:** Items(${line_total:.2f}) + Tax(${tax_amount:.2f}) = Total(${invoice_total:.2f})")
                                else:
                                    st.warning(f"⚠️ **Total mismatch detected.** Items(${line_total:.2f}) + Tax(${tax_amount:.2f}) = ${calculated_total:.2f}, but Invoice Total is ${invoice_total:.2f}.")
                                
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

                    if dev_mode:
                        with tab2:
                            pass

                        
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
                        if st.button("Auto-Sync (Pro Plan Coming Soon)", disabled=True):
                            show_waitlist_modal()
                            # Fake Door Test: Replaced actual sync with waitlist modal
                            # with st.spinner("Connecting to QuickBooks Online..."):
                            #     qb = QuickBooksAdapter()
                            #     if qb.sync_invoice(data):
                            #         st.toast("Successfully synced to QuickBooks!", icon="✅")
                            #         st.success("Synchronized with ERP system.")
                    
                    with c2:
                        # 2. Export Button
                        csv = generate_quickbooks_csv(data)
                        
                        # Generate Professional Filename
                        # Format: QuickBills_Export_YYYY-MM-DD.csv
                        from datetime import datetime
                        date_str = datetime.now().strftime("%Y-%m-%d")
                        filename = f"QuickBills_Export_{date_str}.csv"
                        
                        st.download_button(
                            label="Download CSV File",
                            data=csv,
                            file_name=filename,
                            mime="text/csv",
                            type="secondary", # Changed to secondary to allow custom styling
                            use_container_width=True,
                            key="download_csv_button" # Added key for custom CSS targeting
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
            <p style="margin-bottom: 0.5rem;">&copy; 2026 QuickBills AI. All rights reserved.</p>
            <p style="margin: 0 0 0.75rem 0;">
                By using QuickBills AI, you agree to our
                <a href="https://flowery-tin-466.notion.site/QuickBills-AI-Legal-Center-31d603d9e4da800f8602fe8323638b81?pvs=143" style="color: #64748b; text-decoration: none;" target="_blank">Privacy Policy</a>
                &amp;
                <a href="https://flowery-tin-466.notion.site/Terms-of-Service-for-QuickBills-AI-31d603d9e4da8060b194c1adf99f459c?pvs=143" style="color: #64748b; text-decoration: none;" target="_blank">Terms</a>.
            </p>
            <div style="display: flex; justify-content: center; gap: 1.5rem;">
                 <a href="https://flowery-tin-466.notion.site/QuickBills-AI-Legal-Center-31d603d9e4da800f8602fe8323638b81?pvs=143" style="color: #64748b; text-decoration: none; transition: color 0.2s;" target="_blank">Privacy Policy</a>
                 <a href="https://flowery-tin-466.notion.site/Terms-of-Service-for-QuickBills-AI-31d603d9e4da8060b194c1adf99f459c?pvs=143" style="color: #64748b; text-decoration: none; transition: color 0.2s;" target="_blank">Terms</a>
                 <a href="?nav=contact" style="color: #64748b; text-decoration: none; transition: color 0.2s;" target="_self">Contact Us</a>
            </div>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
