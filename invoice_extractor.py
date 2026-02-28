import pdfplumber
import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
import config
import os
import requests
import easyocr # Moved import here for broader scope
import numpy as np
import cv2
import math # Added for floating point comparisons


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
    tax_amount: Optional[float] = Field(0.0, description="Total tax amount")
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

    def _merge_weighted_item_lines(self, ocr_results_with_boxes: List) -> str:
        """
        Merges lines containing 'lb' or '@' with their vertically closest preceding line.
        This function aims to consolidate multi-line item descriptions where weight/unit price
        information is on a separate line but belongs to the main item.
        ocr_results_with_boxes: List of EasyOCR results, where each result is
                                (bbox, text, prob).
        """
        if not ocr_results_with_boxes:
            return ""

        merged_lines = []
        # Sort results by top-left Y-coordinate to process them roughly top-to-bottom
        ocr_results_with_boxes.sort(key=lambda x: x[0][1]) # Sort by y-coordinate of bbox top-left

        i = 0
        while i < len(ocr_results_with_boxes):
            current_line_bbox, current_line_text, _ = ocr_results_with_boxes[i]
            
            # Check if current line contains weight/unit price indicators
            if "lb" in current_line_text.lower() or "@" in current_line_text:
                # Try to merge with the previous line if available
                if merged_lines:
                    # Get the last added line, which could be a merged one or an original
                    last_merged_line = merged_lines[-1]
                    # Simple heuristic: if the current line is close vertically to the last merged line
                    # and it contains a weight/unit indicator, append it.
                    # This heuristic needs refinement for real-world robustness.
                    # For now, a simple vertical proximity check and line content check.
                    
                    # Assuming last_merged_line is a string, we need to consider how it was constructed.
                    # A more robust solution would track original OCR results' bboxes even after merging.
                    # For simplicity here, we assume if it's "lb" or "@", it's an attribute.
                    # This will be a starting point and can be refined if needed.
                    merged_lines[-1] += " " + current_line_text
                else:
                    # If it's the very first line and contains 'lb' or '@', treat it as a standalone
                    # (this might indicate a poorly recognized item, or a leading weight line)
                    merged_lines.append(current_line_text)
            else:
                merged_lines.append(current_line_text)
            i += 1
        
        return "\n".join(merged_lines)


    def parse_with_ai(self, text: str, retry_count: int = 0, feedback_message: Optional[str] = None) -> InvoiceData:
        """Use DeepSeek to convert unstructured text to structured JSON, with retry mechanism and feedback."""
        
        MAX_RETRIES = 2 # Allow up to 2 retries
        
        schema = InvoiceData.model_json_schema()
        
        # Initial prompt
        prompt_base = f"""
        You are a professional financial audit assistant. Please extract key information from the following invoice text and return it in the required JSON format.
        
        **CRITICAL EXTRACTION RULES (MUST FOLLOW):**
        1. **Exclude Keywords:** COMPLETELY IGNORE lines containing 'SUBTOTAL', 'TOTAL', 'CASH', 'CHANGE', 'BALANCE' when parsing line items. 'TAX' lines should be extracted to 'tax_amount', not line items.
        2. **Amount Extraction:** For each line item, the 'total_price' is usually the number on the FAR RIGHT of the line.
        3. **Quantity Logic:** Default 'quantity' to 1 unless you explicitly see an '@' symbol (e.g., "3 @ 1.50"). Do NOT guess quantity based on price.
        4. **Strict Validation:** Before outputting JSON, you MUST verify: Sum(items.total_price) + tax_amount ~= Total Amount.
        5. **Date Format:** Convert all dates to 'MM/DD/YYYY' format.
        
        **EXTREME AUDIT LOGIC (FOR WALMART & RETAIL RECEIPTS):**
        1. **行合并处理 (Line Merging Applied):** The input text has already been pre-processed. Lines containing 'lb' or '@' have been merged with their associated product description. You MUST NOT treat these as separate line items. Focus on extracting the final, consolidated item.
        2. **强制配对校验 (Strict Row-Locking):** Each extracted Line Item MUST consist of a [Product Description] and its [Associated Total Price]. If a line appears to have only a description without a price, or only a price without a description, you MUST NOT attempt to match it across different lines. If an item is clearly missing a pair, mark the entire item with a 'warning' field: "Parsing error: Item or Price missing for this line."
        3. **针对性屏蔽 (The \"lb\" Trap):** You are STRICTLY FORBIDDEN from interpreting numbers immediately followed by "lb" (e.g., "2.51 lb") as a Unit Price or Total Price. These are weights. The monetary amount for an item MUST be a number in XX.XX format, typically located at the far right end of the line, representing the final item total.
        4. **Decimal Restoration:** OCR often misses decimal points (e.g., reads '$4.03' as '03' or '403'). If you see an integer like '60', '03', '63' in a price column, it is highly likely '2.60', '4.03', '6.63'. Use context to restore the float value.
        5. **Walmart Barcodes:** In Walmart receipts, the first number under a product name is often a barcode, and the SECOND number is the price. The 'SUBTOTAL' line immediately follows the last item - do NOT include it as an item.
        6. **Realism Check:** Do NOT invent unit prices to make the math work. If a price seems impossible (e.g., $60 for a small grocery item), flag it in the 'warning' field: "OCR accuracy issue suspected near [Item Name]".
        7. **Sum over Accuracy:** It is better to have a Sum(Line Items) that slightly mismatches the Total than to hallucinate prices.
        8. **数学校验 (Mathematical Validation):** After initial extraction, internally perform a self-check: Quantity * Unit Price == Item Total. If there is a mismatch (e.g., 2.51 * 1.44 != 2.51), you MUST re-examine the parsing of that specific line to correct the values. If unit price is not explicitly available, infer it from total_price / quantity, then re-verify.
        9. **强制对账 (Forced Reconciliation):** If Sum(items.total_price) + tax_amount != total_amount (Grand Total), you MUST re-audit all extracted numerical values to ensure no weight (lb), quantity (Qty), or UPC codes have been mistakenly interpreted as monetary amounts. Correct any such misinterpretations.

        You must strictly follow this JSON Schema:
        {json.dumps(schema, indent=2)}

        Invoice Text Content:
        ---
        {text}
        ---
        """
        
        # Append feedback message if provided (for retries)
        if feedback_message:
            prompt = f"{feedback_message}\n\n{prompt_base}"
        else:
            prompt = prompt_base

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
            structured_data = InvoiceData(**invoice_dict)

            # --- Post-processing: Internal Calculation Audit --- (New Logic Starts Here)
            calculated_items_total = sum(item.total_price for item in structured_data.items)
            calculated_grand_total = calculated_items_total + structured_data.tax_amount
            
            # Allow for small floating point discrepancies
            if not math.isclose(calculated_grand_total, structured_data.total_amount, rel_tol=1e-2):
                logger.warning(f"Math check failed for invoice {structured_data.invoice_number or 'N/A'}. "
                               f"Calculated Total: {calculated_grand_total:.2f}, Extracted Total: {structured_data.total_amount:.2f}")
                
                if retry_count < MAX_RETRIES:
                    # Construct detailed feedback for AI
                    feedback = (f"Your previous extraction resulted in a mathematical mismatch: "
                                f"Sum(Line Items: {calculated_items_total:.2f}) + Tax ({structured_data.tax_amount:.2f}) "
                                f"does not equal the Grand Total ({structured_data.total_amount:.2f}). "
                                f"Calculated: {calculated_grand_total:.2f}. "
                                f"Please re-examine ALL numerical values, especially for items where quantities, unit prices, "
                                f"or weights (like 'lb') might have been confused with monetary amounts. "
                                f"Focus on reconciling the Grand Total with the sum of items and tax.")
                    logger.info(f"Retrying AI parse with feedback. Retry count: {retry_count + 1}")
                    return self.parse_with_ai(text, retry_count=retry_count + 1, feedback_message=feedback)
                else:
                    structured_data.warning = structured_data.warning or ""
                    structured_data.warning += (f" Mathematical discrepancy detected after {MAX_RETRIES} retries. "
                                                 f"Calculated Total: {calculated_grand_total:.2f}, Extracted Total: {structured_data.total_amount:.2f}.")
                    logger.error(f"Mathematical discrepancy persists after max retries for invoice {structured_data.invoice_number or 'N/A'}.")
            
            return structured_data
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
            # Imports are now at the top of the file.
            # import easyocr
            # import numpy as np
            # import cv2
            pass
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
            
            # 4. Extract text from PROCESSED image with detail=1 for bounding boxes
            ocr_results_with_boxes = reader.readtext(processed_img, detail=1)
            
            # New Step: Pre-process OCR text to merge weighted item lines
            preprocessed_text = self._merge_weighted_item_lines(ocr_results_with_boxes)
            
            logger.info(f"OCR extracted and preprocessed {len(preprocessed_text)} characters.")
            
            if not preprocessed_text.strip():
                return {"error": "OCR failed to identify any text from the image, or pre-processing resulted in empty content."}

            # 5. Send to DeepSeek for structuring
            structured_data = self.parse_with_ai(preprocessed_text)
            
            # Return both structured data and raw text for debugging
            result_dict = structured_data.model_dump()
            result_dict["_raw_text"] = preprocessed_text
            return result_dict

        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return {"error": f"Image recognition failed: {str(e)}"}
