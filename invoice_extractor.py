import pdfplumber
import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
import config
import os
import requests # 引入 requests 库

logger = logging.getLogger(__name__)

# 定义账单明细项的模型
class InvoiceItem(BaseModel):
    description: str = Field(..., description="商品或服务描述")
    quantity: Optional[float] = Field(None, description="数量")
    unit_price: Optional[float] = Field(None, description="单价")
    total_price: float = Field(..., description="总价")
    category: Optional[str] = Field(None, description="费用科目/类别 (例如: Office Supplies, Meals, Travel)")

# 定义完整账单的模型
class InvoiceData(BaseModel):
    vendor_name: str = Field(..., description="销售商/供应商名称")
    invoice_number: Optional[str] = Field(None, description="账单/发票编号")
    date: Optional[str] = Field(None, description="账单日期 (YYYY-MM-DD)")
    due_date: Optional[str] = Field(None, description="到期日 (YYYY-MM-DD)")
    items: List[InvoiceItem] = Field(default_factory=list, description="账单明细列表")
    total_amount: float = Field(..., description="账单总金额")
    currency: str = Field("USD", description="货币符号/代码")

class AIInvoiceExtractor:
    def __init__(self):
        # 保留一个空的初始化，因为我们将手动处理请求
        pass

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """从 PDF 中提取所有文字"""
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
            raise

    def parse_with_ai(self, text: str) -> InvoiceData:
        """使用 DeepSeek 将非结构化文本转换为结构化 JSON"""
        
        schema = InvoiceData.model_json_schema()
        
        prompt = f"""
        你是一个专业的财务审计助手。请从以下账单文本中提取关键信息，并按要求的 JSON 格式返回。
        
        必须严格遵守以下 JSON Schema:
        {json.dumps(schema, indent=2)}
        
        账单文本内容:
        ---
        {text}
        ---
        """

        try:
            # 手动构造请求
            headers = {
                "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是一个只输出结构化 JSON 的财务助手。请直接输出 JSON，不要包含 markdown 格式标记 (如 ```json ... ```)。"},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }
            
            response = requests.post(f"{config.DEEPSEEK_BASE_URL}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            response_json = response.json()
            
            content = response_json['choices'][0]['message']['content']
            content = content.replace("```json", "").replace("```", "").strip()
            
            invoice_dict = json.loads(content)
            return InvoiceData(**invoice_dict)
        except Exception as e:
            logger.error(f"AI parsing failed: {e}")
            raise

    def process_pdf(self, pdf_path: str) -> dict:
        """处理 PDF 的完整流程：提取文本 -> AI 解析 -> 返回 dict"""
        logger.info(f"Processing PDF: {pdf_path}")
        raw_text = self.extract_text_from_pdf(pdf_path)
        if not raw_text.strip():
            raise ValueError("PDF text extraction resulted in empty content.")
        
        structured_data = self.parse_with_ai(raw_text)
        return structured_data.model_dump()

    def extract_from_image(self, image_bytes: bytes) -> dict:
        """
        使用 EasyOCR 从图片中提取文字，然后发送给 DeepSeek 进行结构化处理。
        """
        logger.info("Starting OCR processing for image...")
        try:
            import easyocr
            import numpy as np
            import cv2
        except ImportError:
            return {
                "error": "缺少必要的 OCR 库。请在终端运行: pip install easyocr opencv-python-headless"
            }

        try:
            # 1. 将图片字节流转换为 OpenCV 格式
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return {"error": "无法解码图像文件"}

            # 2. 初始化 EasyOCR (支持中文和英文)
            # 注意：第一次运行会下载模型，可能需要一点时间
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=False) 
            
            # 3. 提取文字
            result = reader.readtext(img, detail=0)
            text = "\n".join(result)
            
            logger.info(f"OCR extracted {len(text)} characters.")
            
            if not text.strip():
                return {"error": "OCR 未能从图片中识别出任何文字。"}

            # 4. 发送给 DeepSeek 进行结构化
            return self.parse_with_ai(text)

        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return {"error": f"图片识别失败: {str(e)}"}
