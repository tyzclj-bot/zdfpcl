import os
import sys
import json
import logging
from invoice_extractor import AIInvoiceExtractor
from quickbooks_adapter import QuickBooksAdapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # Check arguments
    if len(sys.argv) < 2:
        # If no arguments, auto-generate a test PDF and run
        print("No PDF file path provided, entering auto-test mode...")
        test_pdf = "test_invoice_auto.pdf"
        
        # Try to import generator tool, if missing, prompt user
        try:
            from run_demo import create_mock_pdf
            if not os.path.exists(test_pdf):
                create_mock_pdf(test_pdf)
            pdf_path = test_pdf
            should_sync = True # Default test mode enables sync mock
        except ImportError:
            print("Usage: python main.py <invoice_pdf_path> [--sync]")
            return
    else:
        pdf_path = sys.argv[1]
        should_sync = "--sync" in sys.argv

    if not os.path.exists(pdf_path):
        logger.error(f"File not found: {pdf_path}")
        return

    try:
        # 1. Initialize extractor
        extractor = AIInvoiceExtractor()
        
        # 2. Extract and parse invoice
        print(f"\n[1/2] Extracting invoice info: {pdf_path}...")
        invoice_data = extractor.process_pdf(pdf_path)
        
        # 3. Output extraction results
        print("\n--- Extracted JSON Data ---")
        print(json.dumps(invoice_data, indent=4, ensure_ascii=False))
        
        # 4. (Optional) Sync to QuickBooks
        if should_sync:
            print(f"\n[2/2] Syncing to QuickBooks...")
            qb = QuickBooksAdapter()
            success = qb.sync_invoice(invoice_data)
            if success:
                print("Sync successful!")
            else:
                print("Sync failed, please check logs.")
        else:
            print("\nTip: Use --sync argument to attempt sync to QuickBooks.")

    except Exception as e:
        logger.error(f"Error occurred during processing: {e}")

if __name__ == "__main__":
    main()
