import os
import sys
import json
import logging
from invoice_extractor import AIInvoiceExtractor
from quickbooks_adapter import QuickBooksAdapter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # 检查参数
    if len(sys.argv) < 2:
        # 如果没有传参数，自动生成一个测试 PDF 并运行
        print("未提供 PDF 文件路径，正在进入自动测试模式...")
        test_pdf = "test_invoice_auto.pdf"
        
        # 尝试导入生成工具，如果不存在则提示
        try:
            from run_demo import create_mock_pdf
            if not os.path.exists(test_pdf):
                create_mock_pdf(test_pdf)
            pdf_path = test_pdf
            should_sync = True # 默认测试模式开启同步模拟
        except ImportError:
            print("用法: python main.py <invoice_pdf_path> [--sync]")
            return
    else:
        pdf_path = sys.argv[1]
        should_sync = "--sync" in sys.argv

    if not os.path.exists(pdf_path):
        logger.error(f"文件不存在: {pdf_path}")
        return

    try:
        # 1. 初始化提取器
        extractor = AIInvoiceExtractor()
        
        # 2. 提取并解析账单
        print(f"\n[1/2] 正在提取账单信息: {pdf_path}...")
        invoice_data = extractor.process_pdf(pdf_path)
        
        # 3. 输出提取结果
        print("\n--- 提取出的 JSON 数据 ---")
        print(json.dumps(invoice_data, indent=4, ensure_ascii=False))
        
        # 4. (可选) 同步到 QuickBooks
        if should_sync:
            print(f"\n[2/2] 正在同步到 QuickBooks...")
            qb = QuickBooksAdapter()
            success = qb.sync_invoice(invoice_data)
            if success:
                print("同步成功！")
            else:
                print("同步失败，请检查日志。")
        else:
            print("\n提示: 使用 --sync 参数可尝试同步到 QuickBooks。")

    except Exception as e:
        logger.error(f"处理过程中发生错误: {e}")

if __name__ == "__main__":
    main()
