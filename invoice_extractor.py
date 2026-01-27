import pdfplumber
import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
import httpx
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

# 定义完整账单的模型
class InvoiceData(BaseModel):
    vendor_name: str = Field(..., description="销售商/供应商名称")
    invoice_number: Optional[str] = Field(None, description="账单/发票编号")
    date: Optional[str] = Field(None, description="账单日期 (YYYY-MM-DD)")
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
        """使用多模态模型从图片中提取信息（诊断模式）"""
        import base64
        logger.info("Processing image with vision model in diagnostic mode...")

        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        prompt = "Describe the image in as much detail as possible."

        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]

            # 手动构造请求
            headers = {
                "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "deepseek-vl-chat",
                "messages": messages,
                "max_tokens": 2000,
                "temperature": 0.1
            }

            response = requests.post(f"{config.DEEPSEEK_BASE_URL}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            response_json = response.json()

            content = response_json['choices'][0]['message']['content']
            
            return {"diagnostic_description": content}
        except Exception as e:
            logger.error(f"AI vision processing failed: {e}")
            return {"error": str(e)}
