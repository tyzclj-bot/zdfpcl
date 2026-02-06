import pdfplumber
import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
import config
import os
import requests


logger = logging.getLogger(__name__)

# Define invoice item model
class InvoiceItem(BaseModel):
    description: str = Field(..., description="Description of goods or services")
    quantity: Optional[float] = Field(None, description="Quantity")
    unit_price: Optional[float] = Field(None, description="Unit price")
    total_price: float = Field(..., description="Total price")
    category: Optional[str] = Field(None, description="Expense category (e.g., Office Supplies, Meals, Travel)")

# Define complete invoice model
class InvoiceData(BaseModel):
    vendor_name: str = Field(..., description="Vendor/Seller name")
    invoice_number: Optional[str] = Field(None, description="Invoice number")
    date: Optional[str] = Field(None, description="Invoice date (YYYY-MM-DD)")
    due_date: Optional[str] = Field(None, description="Due date (YYYY-MM-DD)")
    items: List[InvoiceItem] = Field(default_factory=list, description="List of invoice items")
    total_amount: float = Field(..., description="Total invoice amount")
    currency: str = Field("USD", description="Currency code")
    warning: Optional[str] = Field(None, description="Audit warning for suspected OCR or logic errors")

class AIInvoiceExtractor:
    def __init__(self):
        # Empty init as we handle requests manually
        pass

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract all text from PDF"""
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
        """Use DeepSeek to convert unstructured text to structured JSON"""
        
        schema = InvoiceData.model_json_schema()
        
        prompt = f"""
        You are a professional financial audit assistant. Please extract key information from the following invoice text and return it in the required JSON format.
        
        **CRITICAL EXTRACTION RULES (MUST FOLLOW):**
        1. **Exclude Keywords:** COMPLETELY IGNORE lines containing 'SUBTOTAL', 'TOTAL', 'CASH', 'CHANGE', 'BALANCE', 'TAX' when parsing line items. These are NOT product items.
        2. **Amount Extraction:** For each line item, the 'total_price' is usually the number on the FAR RIGHT of the line.
        3. **Quantity Logic:** Default 'quantity' to 1 unless you explicitly see an '@' symbol (e.g., "3 @ 1.50"). Do NOT guess quantity based on price.
        4. **Strict Validation:** Before outputting JSON, you MUST verify: Sum(items.total_price) + Tax ~= Total Amount. If they don't match, re-read the line items to ensure you didn't include a 'Subtotal' line as an item.
        5. **Date Format:** Convert all dates to 'MM/DD/YYYY' format.
        
        **EXTREME AUDIT LOGIC (FOR WALMART & RETAIL RECEIPTS):**
        1. **Decimal Restoration:** OCR often misses decimal points (e.g., reads '$4.03' as '03' or '403'). If you see an integer like '60', '03', '63' in a price column, it is highly likely '2.60', '4.03', '6.63'. Use context to restore the float value.
        2. **Walmart Barcodes:** In Walmart receipts, the first number under a product name is often a barcode, and the SECOND number is the price. The 'SUBTOTAL' line immediately follows the last item - do NOT include it as an item.
        3. **Realism Check:** Do NOT invent unit prices to make the math work. If a price seems impossible (e.g., $60 for a small grocery item), flag it in the 'warning' field: "OCR accuracy issue suspected near [Item Name]".
        4. **Sum over Accuracy:** It is better to have a Sum(Line Items) that slightly mismatches the Total than to hallucinate prices.

        You must strictly follow this JSON Schema:
        {json.dumps(schema, indent=2)}
        
        Invoice Text Content:
        ---
        {text}
        ---
        """

        try:
            # Manually construct request
            headers = {
                "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a financial assistant that only outputs structured JSON. Please output JSON directly, do not include markdown formatting markers (such as ```json ... ```)."},
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
        """Full PDF processing flow: Extract text -> AI Parse -> Return dict"""
        logger.info(f"Processing PDF: {pdf_path}")
        raw_text = self.extract_text_from_pdf(pdf_path)
        if not raw_text.strip():
            raise ValueError("PDF text extraction resulted in empty content.")
        
        structured_data = self.parse_with_ai(raw_text)
        # Return both structured data and raw text for debugging
        result = structured_data.model_dump()
        result["_raw_text"] = raw_text
        return result

    def extract_from_image(self, image_bytes: bytes) -> dict:
        """
        Use EasyOCR to extract text from images, then send to DeepSeek for structuring.
        """
        logger.info("Starting OCR processing for image...")
        try:
            import easyocr
            import numpy as np
            import cv2
        except ImportError:
            return {
                "error": "Missing necessary OCR libraries. Please run in terminal: pip install easyocr opencv-python-headless"
            }

        try:
            # 1. Convert image bytes to OpenCV format
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return {"error": "Unable to decode image file"}

            # 2. Pre-processing for Receipt OCR (Upscaling + Contrast)
            # Strategy: Upscale image to make decimal points larger and clearer.
            # Binarization is removed as it was causing data loss (garbled text).
            
            # Upscale (2x or 3x) to separate dots from numbers
            # Use Cubic interpolation for better text quality
            scale_factor = 2.0
            if img.shape[1] < 2000: # Only upscale if not already huge
                img = cv2.resize(img, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)

            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Contrast Enhancement (CLAHE)
            # Makes text darker and background lighter without the harshness of thresholding
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            processed_img = clahe.apply(gray)
            
            # 3. Initialize EasyOCR (Supports Chinese and English)
            # Note: First run will download model, may take some time
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=False) 
            
            # 4. Extract text from PROCESSED image
            result = reader.readtext(processed_img, detail=0)
            text = "\n".join(result)
            
            logger.info(f"OCR extracted {len(text)} characters.")
            
            if not text.strip():
                return {"error": "OCR failed to identify any text from the image."}

            # 4. Send to DeepSeek for structuring
            structured_data = self.parse_with_ai(text)
            
            # Return both structured data and raw text for debugging
            result_dict = structured_data.model_dump()
            result_dict["_raw_text"] = text
            return result_dict

        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return {"error": f"Image recognition failed: {str(e)}"}
