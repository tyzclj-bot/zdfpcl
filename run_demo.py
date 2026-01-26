import os
import subprocess
import sys
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def create_mock_pdf(file_path):
    """生成一个模拟的账单 PDF 用于测试"""
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
    print(f"已生成模拟账单: {file_path}")

def check_env():
    """检查并引导配置 .env"""
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            print("正在从 .env.example 创建 .env 文件...")
            with open(".env.example", "r", encoding="utf-8") as f:
                content = f.read()
            with open(".env", "w", encoding="utf-8") as f:
                f.write(content)
            print("!!! 请在 .env 文件中填入你的 DEEPSEEK_API_KEY 后再继续 !!!")
            return False
    return True

def run_test():
    # 1. 安装依赖
    print("正在检查/安装依赖库...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    # 2. 检查 .env
    if not check_env():
        return

    # 3. 准备测试文件
    test_pdf = "test_invoice.pdf"
    if not os.path.exists(test_pdf):
        create_mock_pdf(test_pdf)

    # 4. 运行主程序
    print("\n" + "="*40)
    print("开始运行 AI 账单提取测试...")
    print("="*40 + "\n")
    
    try:
        subprocess.run([sys.executable, "main.py", test_pdf, "--sync"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n运行失败: 请确保你的 DEEPSEEK_API_KEY 已正确配置在 .env 中。")

if __name__ == "__main__":
    run_test()
