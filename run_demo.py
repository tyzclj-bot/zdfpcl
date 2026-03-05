import os
import subprocess
import sys
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def create_mock_pdf(file_path):
    """Generate a mock invoice PDF for testing"""
    c = canvas.Canvas(file_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "MOCK INVOICE")
    
    c.setFont("Helvetica", 12)
    c.drawString(100, 720, "Vendor: DeepSeek Tech Solutions")
    c.drawString(100, 705, "Invoice #: INV-2024-001")
    c.drawString(100, 690, "Date: 2024-01-26")
    
    c.drawString(100, 650, "Items:")
    c.drawString(120, 630, "1. AI API Service (DeepSeek-V3) - $50.00")
    c.drawString(120, 615, "2. Cloud Storage (50GB) - $10.00")
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, 580, "Total Amount: $60.00")
    c.drawString(100, 565, "Currency: USD")
    
    c.save()
    print(f"Mock invoice generated: {file_path}")

def check_env():
    """Check and guide .env configuration"""
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            print("Creating .env file from .env.example...")
            with open(".env.example", "r", encoding="utf-8") as f:
                content = f.read()
            with open(".env", "w", encoding="utf-8") as f:
                f.write(content)
            print("!!! Please enter your DEEPSEEK_API_KEY in the .env file before continuing !!!")
            return False
    return True

def run_test():
    # 1. Install dependencies
    print("Checking/Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    # 2. Check .env
    if not check_env():
        return

    # 3. Prepare test file
    test_pdf = "test_invoice.pdf"
    if not os.path.exists(test_pdf):
        create_mock_pdf(test_pdf)

    # 4. Run main program
    print("\n" + "="*40)
    print("Starting AI Invoice Extraction Test...")
    print("="*40 + "\n")
    
    try:
        subprocess.run([sys.executable, "main.py", test_pdf, "--sync"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\nRun failed: Please ensure your DEEPSEEK_API_KEY is correctly configured in .env.")

if __name__ == "__main__":
    run_test()
