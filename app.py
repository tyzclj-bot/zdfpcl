
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
    page_title="AI Invoice Intelligence",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    """使用 Streamlit 缓存来创建并复用 AI 提取器实例"""
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

# --- App Logic ---
def main():
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
            if st.button("Save Configuration"):
                st.rerun()
        else:
            # If User is Logged In
            if st.session_state.user:
                st.success(f"Welcome, {st.session_state.user.email}")
                
                # Fetch fresh credits and plan
                profile = supabase.get_user_profile(st.session_state.user.id, st.session_state.access_token)
                st.session_state.credits = profile.get("credits", 0)
                plan_status = profile.get("plan", "free")
                
                st.metric("Credits Remaining", st.session_state.credits)
                
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

                if st.button("Logout"):
                    supabase.sign_out(st.session_state.access_token)
                    st.session_state.user = None
                    st.session_state.access_token = None
                    st.session_state.credits = 0
                    st.rerun()
            else:
                # Login / Register Tabs
                tab_login, tab_signup = st.tabs(["Login", "Register"])
                
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
                    if st.button("Sign Up"):
                        try:
                            res = supabase.sign_up(s_email, s_password)
                            if res and res.user:
                                st.success("Signup successful! Please check your email for confirmation (if enabled) or login.")
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

        st.info("System Status: Online")

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

    if st.session_state.user:
        # Check Credits Logic
        if st.session_state.credits <= 0:
            st.warning("⚠️ You have 0 credits remaining. Please upgrade your plan to continue parsing invoices.")
            st.info("New users get 5 free credits.")
            return

        # Main Layout: Upload and Processing
        col1, col2 = st.columns([1, 2], gap="large")

        with col1:
            st.subheader("1. Upload Invoice")
            uploaded_file = st.file_uploader("Drop your invoice here (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"])
            
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

                    extractor = get_extractor() # 获取缓存的实例
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

                            # 检查返回数据的类型
                            if isinstance(data, dict) and data.get("error"):
                                st.error(f"AI Processing Error: {data['error']}")
                                # 清除旧数据（如有）
                                if 'invoice_data' in st.session_state:
                                    del st.session_state['invoice_data']
                            else:
                                # 如果是 Pydantic 对象，转换为字典以便存储和显示
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
            st.subheader("2. Extraction Results")
            
            if 'invoice_data' in st.session_state:
                data = st.session_state['invoice_data']

                # 如果是诊断模式的结果，则特殊显示
                if "diagnostic_description" in data:
                    st.subheader("AI Vision Diagnostic Report")
                    st.markdown(data["diagnostic_description"])
                    st.info("This is a diagnostic run. We are checking the connection to the vision model.")
                    return # 结束渲染，不显示下面的常规结果

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
                    csv = df_export.to_csv(index=False).encode('utf-8')
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
    else:
        # Not logged in
        st.markdown("""
        <div style="text-align: center; padding: 50px;">
            <h2>👋 Welcome to Invoice Intelligence</h2>
            <p>Please log in or register via the sidebar to start processing invoices.</p>
            <p>New users get <b>5 free credits</b>!</p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
