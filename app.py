
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
    
    .main {
        background-color: #f8fafc;
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
    
    .result-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        margin-bottom: 1rem;
    }
    
    .status-badge {
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 500;
    }
    
    h1, h2, h3 {
        color: #1e293b;
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
    Headers: 供应商, 账单编号, 账单日期, 到期日, 总金额, 单项金额, 单项科目, 单项描述
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

    headers = ["供应商", "账单编号", "账单日期", "到期日", "总金额", "单项金额", "单项科目", "单项描述"]
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
                "供应商": vendor,
                "账单编号": inv_num,
                "账单日期": inv_date,
                "到期日": due_date,
                "总金额": total_str,
                "单项金额": line_amount_str,
                "单项科目": category,
                "单项描述": description
            }
            rows.append(row)
    else:
        # Fallback if no items found
        row = {
            "供应商": vendor,
            "账单编号": inv_num,
            "账单日期": inv_date,
            "到期日": due_date,
            "总金额": total_str,
            "单项金额": total_str, # Assume single line item equal to total
            "单项科目": "Uncategorized Expense",
            "单项描述": "Invoice Total"
        }
        rows.append(row)
        
    df = pd.DataFrame(rows, columns=headers)
    return df.to_csv(index=False).encode('utf-8-sig')

# --- App Logic ---
FIXED_VERIFIER = "v1_persistent_verifier_fix_zdfpcl_2025"

def main():
    # --- Promotional Banner ---
    st.markdown("""
        <div style="
            background-color: #4f46e5; 
            color: white; 
            padding: 0.75rem; 
            text-align: center; 
            font-weight: 600; 
            font-size: 1rem;
            margin-bottom: 1rem;
            border-radius: 8px;
        ">
            The fastest way to convert invoices to QuickBooks CSV.
        </div>
    """, unsafe_allow_html=True)

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
                
                if avatar_url:
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        # Use st.image with a mask if possible, or just simple
                        st.image(avatar_url, width=60)
                    with c2:
                        st.write(f"**{full_name}**")
                        st.caption(st.session_state.user.email)
                else:
                    st.success(f"Welcome, {full_name}")
                
                # Fetch fresh credits and plan
                profile = supabase.get_user_profile(st.session_state.user.id, st.session_state.access_token)
                st.session_state.credits = profile.get("credits", 0)
                plan_status = profile.get("plan", "free")
                
                st.metric("Credits Remaining", st.session_state.credits, help="New users start with 5 credits. 1 credit is deducted only after a successful extraction.")
                
                # Show Plan Badge
                if plan_status == 'pro':
                    st.success("💎 Pro Plan Active")
                else:
                    st.info("Free Plan")
                
                if st.session_state.credits <= 0:
                    st.error("Please Upgrade Plan")
                
                # Upgrade Button (Only show if not pro)
                if plan_status != 'pro':
                    # PayPal Invoice Link
                    # Note: Automatic tracking is not available with this static link. 
                    # You will need to manually verify payments.
                    checkout_url = "https://www.paypal.com/invoice/p/#FNC8963Z27RBSCZ5"
                    st.link_button("💎 Upgrade to Pro", checkout_url, type="primary")

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
                if st.session_state.user.email == "tyzclj@gmail.com":
                    st.markdown("---")
                    st.markdown("### 👑 Admin Stats")
                    
                    if hasattr(supabase, 'get_admin_stats'):
                        admin_stats = supabase.get_admin_stats(st.session_state.access_token)
                        if admin_stats:
                            st.metric("Users", admin_stats.get('total_users', 0))
                            st.metric("Invoices", admin_stats.get('total_invoices', 0))
                        else:
                            st.error("无法获取数据，请确保已运行 admin_setup.sql")
                    else:
                        st.warning("管理员功能代码未加载，请在后台 Reboot App")
            else:
                # Login / Register Tabs
                
                # --- Google OAuth Button ---
                # Determine Redirect URL (Prioritize Secrets, then Env, then Default to Prod)
                redirect_url = "https://quickbills-ai.streamlit.app/"
                
                if "APP_URL" in st.secrets:
                    redirect_url = st.secrets["APP_URL"]
                elif os.getenv("APP_URL"):
                    redirect_url = os.getenv("APP_URL")
                
                # Generate URL and Verifier
                # We save verifier to session_state so we can use it when user returns
                # Use FIXED_VERIFIER to ensure session loss doesn't break the flow
                google_url, verifier = supabase.get_oauth_url("google", redirect_url, fixed_verifier=FIXED_VERIFIER)
                st.session_state.oauth_verifier = verifier
                
                # Use link_button to open the Google Auth URL
                # st.link_button("Continue with Google", google_url, type="primary", use_container_width=True)
                
                # Use Markdown with target="_self" to open in the SAME tab
                st.markdown(
                    f'''
                    <a href="{google_url}" target="_self" style="text-decoration:none;">
                        <button style="
                            width: 100%;
                            background-color: #FF4B4B;
                            color: white;
                            padding: 10px;
                            border: none;
                            border-radius: 5px;
                            font-weight: bold;
                            cursor: pointer;
                        ">
                            Continue with Google
                        </button>
                    </a>
                    ''', 
                    unsafe_allow_html=True
                )
                
                st.divider()

                tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])
                
                with tab_login:
                    email = st.text_input("Email", key="login_email")
                    password = st.text_input("Password", type="password", key="login_pass")
                    if st.button("Sign In"):
                        try:
                            res = supabase.sign_in(email, password)
                            if res and res.user:
                                st.session_state.user = res.user
                                st.session_state.access_token = res.session.access_token
                                st.success("Logged in successfully!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Login failed: {str(e)}")
                
                with tab_signup:
                    s_email = st.text_input("Email", key="signup_email")
                    s_password = st.text_input("Password", type="password", key="signup_pass")
                    if st.button("Create Account"):
                        try:
                            res = supabase.sign_up(s_email, s_password)
                            if res and res.user:
                                st.success("Account created! Please check your email for confirmation (if enabled) or sign in.")
                                # Auto login if session provided
                                if res.session:
                                    st.session_state.user = res.user
                                    st.session_state.access_token = res.session.access_token
                                    st.rerun()
                        except Exception as e:
                            st.error(f"Signup failed: {str(e)}")

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
        st.markdown("Need help? Contact us at:")
        st.code("tyzclj@gmail.com", language=None)

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
        # LANDING PAGE VIEW
        st.markdown("""
            <div style="text-align: center; margin-bottom: 2rem;">
                <h1 style="font-size: 3rem; font-weight: 800; color: #1e293b; margin-bottom: 0.5rem;">
                    AI Invoice Intelligence
                </h1>
                <p style="font-size: 1.5rem; color: #475569; font-weight: 500;">
                    Save 90% of your bookkeeping time with AI
                </p>
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
                box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
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

        st.markdown("""
        <div style="text-align: center; padding: 20px;">
            <h3>👋 Ready to get started?</h3>
            <p>Please log in or register via the sidebar to start processing invoices.</p>
            <p>New users get <b>5 free credits</b>!</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # --- FAQ Section ---
        st.subheader("Frequently Asked Questions")
        
        faq1, faq2, faq3 = st.columns(3)
        with faq1:
            st.markdown("**Is it secure?**")
            st.caption("Yes, we use AES encryption to protect your data.")
        with faq2:
            st.markdown("**Does it support PDFs?**")
            st.caption("Yes, we support both image files (PNG, JPG) and PDFs.")
        with faq3:
            st.markdown("**How do I import to QuickBooks?**")
            st.caption("Simply download our CSV export and use the standard QuickBooks Import feature.")
        
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
        uploaded_file = st.file_uploader("Drop your invoice here (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"])
        
        # Trust Signals
        st.info("🛡️ **7-Day Money Back Guarantee**  \n🔒 **Secure Payment by Lemon Squeezy**")

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
                    with st.spinner("🤖 AI is analyzing your document..."):
                        try:
                            file_bytes = uploaded_file.getvalue()
                            
                            if "image" in uploaded_file.type:
                                data = extractor.extract_from_image(file_bytes)
                            else: # It's a PDF
                                with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                                    tmp.write(file_bytes)
                                    tmp_path = tmp.name
                                
                                data = extractor.process_pdf(tmp_path)
                                os.unlink(tmp_path)

                            # Check return data type
                            if isinstance(data, dict) and data.get("error"):
                                st.error(f"AI Processing Error: {data['error']}")
                                # Clear old data (if any)
                                if 'invoice_data' in st.session_state:
                                    del st.session_state['invoice_data']
                            else:
                                # If Pydantic object, convert to dict for storage and display
                                if not isinstance(data, dict):
                                    data = data.model_dump()
                                
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
                            
                            st.rerun()
                        except Exception as e:
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
                        return # Stop rendering, do not display regular results below

                    # Key Metrics Row
                    m1, m2, m3 = st.columns(3)
                    with m1:
                        st.metric("Vendor", data.get('vendor_name'))
                    with m2:
                        st.metric("Total Amount", f"{data.get('currency')} {data.get('total_amount')}")
                    with m3:
                        st.metric("Invoice #", data.get('invoice_number'))

                    # Details Tab
                    tab1, tab2 = st.tabs(["Line Items", "Raw JSON"])
                    
                    with tab1:
                        if data.get('items'):
                            df = pd.DataFrame(data['items'])
                            # Modern styling for dataframe
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.write("No line items detected.")

                    with tab2:
                        st.json(data)

                    st.divider()
                    
                    # Action Section
                    st.subheader("3. Export & Sync")
                    
                    # Prepare data for export
                    items_data = data.get('items', [])
                    df_export = pd.DataFrame(items_data) if items_data else pd.DataFrame()

                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        if st.button("🚀 Sync to QuickBooks"):
                            with st.spinner("Connecting to QuickBooks Online..."):
                                qb = QuickBooksAdapter()
                                if qb.sync_invoice(data):
                                    st.toast("Successfully synced to QuickBooks!", icon="✅")
                                    st.success("Synchronized with ERP system.")
                    
                    with c2:
                        csv = generate_quickbooks_csv(data)
                        st.download_button(
                            label="📄 Download CSV",
                            data=csv,
                            file_name=f"invoice_{data.get('invoice_number', 'export')}.csv",
                            mime="text/csv"
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

                    with c4:
                        json_str = json.dumps(data, indent=4, ensure_ascii=False)
                        st.download_button(
                            label="📥 Download JSON",
                            data=json_str,
                            file_name=f"invoice_{data.get('invoice_number', 'export')}.json",
                            mime="application/json"
                        )
                else:
                    st.info("Upload and process an invoice to see results here.")
                    # Placeholder image or illustration could go here

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

    # --- Footer ---
    st.markdown("""
        <div style="text-align: center; margin-top: 5rem; padding-bottom: 2rem; color: #94a3b8; font-size: 0.875rem;">
            <p>AI Invoice Intelligence &copy; 2025</p>
            <a href="#" style="color: #64748b; text-decoration: none; margin: 0 10px;">Privacy Policy</a>
            <a href="#" style="color: #64748b; text-decoration: none; margin: 0 10px;">Terms of Service</a>
            <a href="#" style="color: #4f46e5; text-decoration: none; font-weight: 600; margin: 0 10px;">Become an Affiliate</a>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
