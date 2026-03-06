import streamlit as st
import logging

# Configure logging to a file
logging.basicConfig(filename='streamlit_app.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("Streamlit app (simplified) started.")

st.title("Simplified Streamlit App")
st.write("If you see this, Streamlit is running!")

if __name__ == "__main__":
    logger.info("Running simplified app in __main__ block.")