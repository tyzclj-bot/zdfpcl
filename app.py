import streamlit as st
import pandas as pd
import json
import os
from invoice_extractor import AIInvoiceExtractor
from quickbooks_adapter import QuickBooksAdapter
from tempfile import NamedTemporaryFile

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Invoice Intelligence",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed"
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

# --- App Logic ---
def main():
    # Header Section
    st.title("🧾 Invoice Intelligence")
    st.markdown("<p style='color: #64748b; font-size: 1.1rem;'>AI-Powered Invoice Extraction & ERP Synchronization</p>", unsafe_allow_html=True)
    st.divider()

    # --- Authorization Logic ---
    auth_code = "tang888"
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    with st.sidebar:
        st.header("Authorization")
        user_code = st.text_input("请输入授权码", type="password")
        
        if user_code == auth_code:
            st.session_state.authenticated = True
            st.toast("授权成功！", icon="✅")
        elif user_code:
            st.error("授权码错误")

        st.divider()
        st.header("Settings")
        st.info("Using DeepSeek-V3 Engine")
        if st.button("Clear Cache"):
            st.session_state.clear()
            st.rerun()

    # --- Main App Display ---
    if st.session_state.authenticated:
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

                            # 检查是否有错误从提取器返回
                            if data.get("error"):
                                st.error(f"AI Processing Error: {data['error']}")
                                # 清除旧数据（如有）
                                if 'invoice_data' in st.session_state:
                                    del st.session_state['invoice_data']
                            else:
                                st.session_state['invoice_data'] = data
                                st.session_state['processed'] = True
                            
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
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🚀 Sync to QuickBooks"):
                        with st.spinner("Connecting to QuickBooks Online..."):
                            qb = QuickBooksAdapter()
                            if qb.sync_invoice(data):
                                st.toast("Successfully synced to QuickBooks!", icon="✅")
                                st.success("Synchronized with ERP system.")
                with c2:
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
        st.warning("请在左侧侧边栏输入授权码以解锁应用。")
        st.info("如无授权码，请联系管理员获取。")

if __name__ == "__main__":
    main()
