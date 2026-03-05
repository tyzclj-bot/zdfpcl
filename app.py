import streamlit as st
import json
import base64
import requests
import io
from invoice_extractor import InvoiceData, InvoiceItem, AIInvoiceExtractor
from datetime import datetime
from typing import Any
from supabase_manager import SupabaseManager
import time

# Lemon Squeezy checkout URL for the Pro Plan
checkout_url = "https://quickbills-ai.lemonsqueezy.com"

# Initialize Supabase
@st.cache_resource
def init_supabase():
    try:
        supabase_manager = SupabaseManager()
        # st.success("Supabase initialized successfully!") # For debugging
        return supabase_manager
    except Exception as e:
        st.error(f"Failed to initialize Supabase: {e}")
        return None

supabase_manager = init_supabase()

# Function to encode image to base64
def get_image_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# Set Streamlit page configuration
st.set_page_config(layout="centered", page_title="QuickBills AI - Invoice Extractor")

# Custom CSS for styling
st.markdown("""
<style>
.stButton>button {
    width: 100%;
}
.stDownloadButton>button {
    background-color: #FF4B4B; /* Red background */
    color: white; /* White text */
    font-size: 1.2em; /* Larger font */
    padding: 10px 20px; /* More padding */
    border-radius: 5px; /* Rounded corners */
    border: none; /* No border */
    width: 100%; /* Full width */
}
.pricing-card {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    text-align: center;
    background-color: #f9f9f9;
}
.pricing-card h3 {
    color: #4CAF50;
    font-size: 1.8em;
}
.pricing-card .price {
    font-size: 2.5em;
    font-weight: bold;
    margin: 10px 0;
}
.pricing-card .features {
    list-style: none;
    padding: 0;
    margin: 20px 0;
}
.pricing-card .features li {
    margin-bottom: 10px;
    font-size: 1.1em;
}
.pricing-card .subscribe-button button {
    background-color: #4CAF50;
    color: white;
    padding: 10px 20px;
    border-radius: 5px;
    text-decoration: none;
    font-size: 1.2em;
    border: none;
    cursor: pointer;
}
</style>
""", unsafe_allow_html=True)

# Initialize session state for user and authentication manager if not already present
if "user" not in st.session_state:
    st.session_state.user = None
if "auth_manager" not in st.session_state:
    st.session_state.auth_manager = None

# Sidebar for login/logout and navigation
with st.sidebar:
    st.image("logo.png", use_column_width=True)
    st.title("QuickBills AI")

    if supabase_manager:
        if st.session_state.user:
            st.write(f"Welcome, {st.session_state.user.email}!")
            if st.button("Logout"):
                supabase_manager.sign_out()
                st.session_state.user = None
                st.session_state.auth_manager = None
                st.success("Logged out successfully!")
                st.rerun()
        else:
            st.subheader("Login / Sign Up")
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                login_submit = st.form_submit_button("Login")
                if login_submit:
                    user, session = supabase_manager.sign_in(email, password)
                    if user:
                        st.session_state.user = user
                        st.session_state.auth_manager = supabase_manager # Assign the manager
                        st.success("Logged in successfully!")
                        st.rerun()
                    else:
                        st.error("Login failed. Check your email and password.")

            if st.button("Sign Up"):
                with st.form("signup_form"):
                    new_email = st.text_input("New Email")
                    new_password = st.text_input("New Password", type="password")
                    signup_submit = st.form_submit_button("Create Account")
                    if signup_submit:
                        user, session = supabase_manager.sign_up(new_email, new_password)
                        if user:
                            st.success("Account created! Please check your email to confirm.")
                        else:
                            st.error("Sign up failed.")
    else:
        st.warning("Supabase is not initialized. Functionality is limited.")
        st.markdown("**Auto-Sync (Pro Plan Coming Soon)**", help="Sync your invoices to QuickBooks automatically (Pro Plan feature).")
        st.button("Auto-Sync (Pro Plan Coming Soon)", disabled=True)
        st.markdown(f'<a href="{checkout_url}" target="_blank" style="text-decoration: none;"><button style="background-color: #007bff; color: white; padding: 10px 20px; border-radius: 5px; border: none; cursor: pointer; width: 100%; margin-top: 10px;">Subscribe to Pro Plan ($19.9/month)</button></a>', unsafe_allow_html=True)
        st.markdown("---")
        st.subheader("Guest User Features")
        st.info("Log in to unlock full features, including credit management and history.")
        # Guest user payment button
        st.markdown(f'<a href="{checkout_url}" target="_blank" style="text-decoration: none;"><button style="background-color: #28a745; color: white; padding: 10px 20px; border-radius: 5px; border: none; cursor: pointer; width: 100%;">Buy Credits (Pro Plan $19.9)</button></a>', unsafe_allow_html=True)


    st.markdown("---")
    st.subheader("About")
    st.write("QuickBills AI uses advanced AI to extract data from your invoices quickly and accurately.")
    st.write("Powered by Streamlit.")

    st.markdown("---")
    st.write("Contact Us: support@quickbills.ai")
    st.write("Team Location: Hong Kong / Taiwan") # Changed from Mainland China

# Main content area
st.header("Invoice Data Extractor")

# Demo Video Area
st.subheader("Demo Video")
st.markdown('<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%;"><iframe src="https://www.loom.com/embed/8c9a8a8ff70a4b2b977fdb64d9c5ba38" frameborder="0" webkitallowfullscreen mozallowfullscreen allowfullscreen style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"></iframe></div>', unsafe_allow_html=True)
st.markdown("---")

# Display pricing card for non-logged-in users
if not st.session_state.user:
    st.subheader("Unlock Full Potential with Our Pro Plan!")
    st.markdown("""
    <div class="pricing-card">
        <h3>Standard Plan</h3>
        <div class="price">$19.99<span style="font-size: 0.5em;">/month</span></div>
        <ul class="features">
            <li>✅ Unlimited Invoice Extractions</li>
            <li>✅ QuickBooks Auto-Sync</li>
            <li>✅ Priority Support</li>
            <li>✅ Access to Advanced Features</li>
        </ul>
        <div class="subscribe-button">
            <a href="https://quickbills-ai.lemonsqueezy.com" target="_blank">
                <button>Subscribe Now</button>
            </a>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

# File uploader
uploaded_file = st.file_uploader("Upload an invoice image or PDF", type=["jpg", "jpeg", "png", "pdf"])

# Initialize AI extractor
extractor = AIInvoiceExtractor()

if uploaded_file is not None:
    file_details = {"filename": uploaded_file.name, "filetype": uploaded_file.type, "filesize": uploaded_file.size}
    st.write(file_details)

    file_bytes = uploaded_file.getvalue()

    # Determine file type and process
    try:
        if file_details["filetype"] in ["image/jpeg", "image/png"]:
            st.image(uploaded_file, caption="Uploaded Invoice", use_column_width=True)
            # Process image
            with st.spinner("Extracting data from image..."):
                extracted_data = extractor.process_image(file_bytes)
        elif file_details["filetype"] == "application/pdf":
            # Process PDF
            with st.spinner("Extracting data from PDF..."):
                extracted_data = extractor.process_pdf(io.BytesIO(file_bytes))
        else:
            st.error("Unsupported file type.")
            extracted_data = None

        if extracted_data:
            st.success("Data extracted successfully!")
            st.subheader("Extracted Invoice Data")
            st.json(extracted_data.model_dump_json(indent=2))

            # Display structured data
            st.subheader("Structured Data")
            st.write(f"**Vendor Name:** {extracted_data.vendor_name}")
            st.write(f"**Invoice Date:** {extracted_data.invoice_date}")
            st.write(f"**Total Amount:** {extracted_data.total_amount}")
            st.write(f"**Tax Amount:** {extracted_data.tax_amount}")
            st.write(f"**Currency:** {extracted_data.currency}")
            st.write(f"**Payment Due Date:** {extracted_data.payment_due_date}")

            if extracted_data.items:
                st.subheader("Items")
                items_df = st.dataframe([item.model_dump() for item in extracted_data.items])
            else:
                st.info("No items extracted.")

            # Provide option to download as CSV
            csv_data = extracted_data.to_csv()
            st.download_button(
                label="Download CSV File",
                data=csv_data,
                file_name=f"{extracted_data.vendor_name}_invoice_{extracted_data.invoice_date}.csv",
                mime="text/csv",
                key="download_csv_button"
            )

            # QuickBooks Sync (disabled for now)
            st.markdown("---")
            st.markdown("**Auto-Sync (Pro Plan Coming Soon)**", help="Sync your invoices to QuickBooks automatically (Pro Plan feature).")
            st.button("Auto-Sync (Pro Plan Coming Soon)", disabled=True)
            st.markdown(f'<a href="{checkout_url}" target="_blank" style="text-decoration: none;"><button style="background-color: #007bff; color: white; padding: 10px 20px; border-radius: 5px; border: none; cursor: pointer; width: 100%; margin-top: 10px;">Subscribe to Pro Plan ($19.9/month)</button></a>', unsafe_allow_html=True)


        else:
            st.error("AI processing failed or returned no data.")

    except Exception as e:
        st.error(f"An error occurred during processing: {e}")
        st.error("AI Processing Error: Image recognition failed. Please try again with a clearer image or a different file.")

# Footer
st.markdown("---")
st.markdown("© 2024 QuickBills AI. All rights reserved.")
st.markdown("Trust and Security: Your data is processed securely.")
st.markdown("Team Location: Hong Kong / Taiwan") # Changed from Mainland China
