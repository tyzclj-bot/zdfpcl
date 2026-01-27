import pdfplumber
import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
import config

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
        # 使用 DeepSeek 配置初始化 OpenAI 客户端
        self.client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL
        )

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
        
        # 获取 Pydantic 模型的 JSON Schema，用于提示模型
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
            response = self.client.chat.completions.create(
                model="deepseek-chat", 
                messages=[
                    {"role": "system", "content": "你是一个只输出结构化 JSON 的财务助手。请直接输出 JSON，不要包含 markdown 格式标记 (如 ```json ... ```)。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            # 清理可能的 markdown 标记
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
        """使用多模态模型从图片中提取信息"""
        import base64
        logger.info("Processing image with vision model...")

        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        schema = InvoiceData.model_json_schema()

        prompt = f"""
        你是一个专业的财务审计助手。请从这张发票图片中提取关键信息，并严格按照以下 JSON Schema 格式返回。
        
        JSON Schema:
        {json.dumps(schema, indent=2)}
        """

        try:
            response = self.client.chat.completions.create(
                model="deepseek-vl-chat",
                messages=[
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
                ],
                max_tokens=3000,
                temperature=0.1,
            )
            content = response.choices[0].message.content
            # 模型返回的可能是包含 JSON 的 markdown 块，需要清理
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            
            invoice_dict = json.loads(content)
            validated_data = InvoiceData(**invoice_dict)
            return validated_data.model_dump()
        except Exception as e:
            logger.error(f"AI vision processing failed: {e}")
            raise
