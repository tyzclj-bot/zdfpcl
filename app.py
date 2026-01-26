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

# --- App Logic ---
def main():
    # Header Section
    st.title("🧾 Invoice Intelligence")
    st.markdown("<p style='color: #64748b; font-size: 1.1rem;'>AI-Powered Invoice Extraction & ERP Synchronization</p>", unsafe_allow_html=True)
    st.divider()

    # Sidebar / Settings
    with st.sidebar:
        st.header("Settings")
        st.info("Using DeepSeek-V3 Engine")
        if st.button("Clear Cache"):
            st.rerun()

    # Main Layout: Upload and Processing
    col1, col2 = st.columns([1, 2], gap="large")

    with col1:
        st.subheader("1. Upload Invoice")
        uploaded_file = st.file_uploader("Drop your PDF invoice here", type=["pdf"])
        
        if uploaded_file:
            st.success("File uploaded successfully!")
            if st.button("Process with AI"):
                with st.spinner("Analyzing document structure..."):
                    try:
                        # Save temp file
                        with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(uploaded_file.getvalue())
                            tmp_path = tmp.name
                        
                        # Process
                        extractor = AIInvoiceExtractor()
                        data = extractor.process_pdf(tmp_path)
                        st.session_state['invoice_data'] = data
                        st.session_state['processed'] = True
                        
                        # Cleanup
                        os.unlink(tmp_path)
                    except Exception as e:
                        st.error(f"Processing failed: {str(e)}")

    with col2:
        st.subheader("2. Extraction Results")
        
        if 'invoice_data' in st.session_state:
            data = st.session_state['invoice_data']
            
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

if __name__ == "__main__":
    main()
