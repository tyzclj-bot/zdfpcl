import pdfplumber
import json
import logging
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
import config
import os
import requests
import easyocr # Moved import here for broader scope
import numpy as np
import cv2
import math # Added for floating point comparisons
import re # Added for regex operations


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

    def _find_text_bbox(self, text_to_find: str, ocr_results_with_boxes: List) -> Optional[Tuple[List[List[int]], str, float]]:
        """
        Finds the bounding box and other info for a given text string within the OCR results.
        Prioritizes exact match, then case-insensitive, then partial match.
        """
        if not text_to_find:
            return None

        # Try exact match first
        for bbox, text, prob in ocr_results_with_boxes:
            if text_to_find == text:
                return (bbox, text, prob)
        
        # Then try case-insensitive exact match
        for bbox, text, prob in ocr_results_with_boxes:
            if text_to_find.lower() == text.lower():
                return (bbox, text, prob)

        # Then try partial match (case-insensitive)
        for bbox, text, prob in ocr_results_with_boxes:
            if text_to_find.lower() in text.lower():
                return (bbox, text, prob)
                
        return None


    def _merge_weighted_item_lines(self, ocr_results_with_boxes: List) -> str:
        """
        Aggressively merges lines containing 'lb', '@', or '/' with adjacent lines
        to ensure complete item associations are seen by the LLM on a single line.
        """
        if not ocr_results_with_boxes:
            return ""

        # Sort results by top-left Y-coordinate
        ocr_results_with_boxes.sort(key=lambda x: x[0][1])

        num_ocr_lines = len(ocr_results_with_boxes)
        consumed_flags = [False] * num_ocr_lines
        final_processed_lines = []

        # Regex to detect weight/quantity features in a line
        # Added \b for word boundary to prevent partial matches like 'club' matching 'lb'
        # Added optional decimal part for numbers
        weight_qty_pattern = re.compile(r'\b\d+\.?\d*\s*(lb|@|/|kg|g|oz)\b', re.IGNORECASE)

        i = 0
        while i < num_ocr_lines:
            if consumed_flags[i]:
                i += 1
                continue

            current_text = ocr_results_with_boxes[i][1]
            
            # Check if this line is a merge candidate (contains weight/qty pattern)
            if weight_qty_pattern.search(current_text):
                merged_text_parts = []

                # Look for previous line to merge
                # Aggressively merge if previous line exists and is not consumed
                if i > 0 and not consumed_flags[i-1]:
                    merged_text_parts.append(ocr_results_with_boxes[i-1][1])
                    consumed_flags[i-1] = True 

                # Add current line
                merged_text_parts.append(current_text)
                consumed_flags[i] = True 

                # Look for next line to merge
                # Aggressively merge if next line exists and is not consumed
                if i + 1 < num_ocr_lines and not consumed_flags[i+1]:
                    merged_text_parts.append(ocr_results_with_boxes[i+1][1])
                    consumed_flags[i+1] = True
                    # No need to manually increment 'i' here, the outer while loop's 'i += 1' will eventually
                    # reach the consumed next line, which will then be skipped.

                final_processed_lines.append(" ".join(merged_text_parts))
            else: # If not a merge candidate and not consumed, add as-is
                final_processed_lines.append(current_text)
            
            i += 1
        
        return "\n".join(final_processed_lines)


    def parse_with_ai(self, text: str, ocr_results_with_boxes: List, retry_count: int = 0, feedback_message: Optional[str] = None) -> InvoiceData:
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

        **FEW-SHOT EXAMPLE (Walmart Weighted Items Correction):**
        This is a critical example to prevent previous errors in weighted item extraction.
        OCR Text Snippet (Hypothetical Multi-line, but pre-processed into one line for you):
        ---
        RED GRAPE 2.51 lb @ 1.44 /lb 3.61
        ---
        Bad Example of your previous extraction logic (AVOID THIS):
        ```json
        [
          {{
            "description": "RED GRAPE",
            "total_price": 2.48 // INCORRECT - This was another item's price, or part of the weight was taken as price
          }},
          {{
            "description": "1lb/1.44", // INCORRECT - This is part of the weight/unit info
            "total_price": 2.51 // INCORRECT - This is the weight, not the final price
          }}
        ]
        ```
        
        Correct Example of desired extraction logic (FOLLOW THIS):
        ```json
        [
          {{
            "description": "RED GRAPE",
            "quantity": 2.51,
            "unit_price": 1.44,
            "total_price": 3.61 // CORRECT - This is the final calculated price for the item
          }}
        ]
        ```
        
        **CRITICAL INSTRUCTION**: NEVER interpret a number immediately followed by "lb", "@", "per", or "/" as the `total_price` or `unit_price`. These are weight, quantity, or unit indicators. The `total_price` for weighted items MUST be the final monetary value, typically found at the far right of the consolidated line (e.g., '3.61' in the example above). When 'lb' or '@' is present, look for the 'quantity' and 'unit_price' explicitly.

        **EXTREME AUDIT LOGIC (FOR WALMART & RETAIL RECEIPTS):**
        1. **行合并处理 (Line Merging Applied):** The input text has already been pre-processed. Lines containing 'lb' or '@' have been merged with their associated product description. You MUST NOT treat these as separate line items. Focus on extracting the final, consolidated item.
        2. **强制配对校验 (Strict Row-Locking):** Each extracted Line Item MUST consist of a [Product Description] and its [Associated Total Price]. If a line appears to have only a description without a price, or only a price without a description, you MUST NOT attempt to match it across different lines. If an item is clearly missing a pair, mark the entire item with a 'warning' field: "Parsing error: Item or Price missing for this line."
        3. **针对性屏蔽 (The "lb" Trap):** You are STRICTLY FORBIDDEN from interpreting numbers immediately followed by "lb" (e.g., "2.51 lb") as a Unit Price or Total Price. These are weights. The monetary amount for an item MUST be a number in XX.XX format, typically located at the far right end of the line, representing the final item total.
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

            # --- NEW POST-PROCESSING LOGIC (优先级高于数学审计) ---
            post_processing_warnings = []
            Y_TOLERANCE = 5 # pixels

            # 1. 排除“非金额数字” (Exclude "Non-Monetary Numbers")
            # 遍历AI提取出的items，检查total_price是否可能被误认为是重量/数量
            for item in structured_data.items:
                # 检查描述中是否有重量/数量单位紧跟数字，且total_price与该数字接近
                desc_lower = item.description.lower()
                
                # Pattern: "X.XXlb", "X.XX @", "X.XX /" (where X.XX is the total_price)
                # This is a heuristic. We're looking for cases where the description *contains* a number
                # that looks like the price, but is actually a weight/quantity indicator.
                # Example: "Red Grapes 2.51lb" with total_price 2.51 (should be 3.61)
                
                # Check for "lb", "@", "/" patterns associated with a number in the description
                # If the item description itself is a number followed by lb/etc., it's suspicious
                if re.search(r'\b\d+\.\d+\s*(lb|@|/|kg|g|oz)\b', desc_lower) and \
                   math.isclose(item.total_price, float(re.search(r'(\d+\.\d+)', desc_lower).group(1)) if re.search(r'(\d+\.\d+)', desc_lower) else -1, rel_tol=1e-2):
                    
                    warning_msg = f"Item '{item.description}' with price {item.total_price} detected as potential non-monetary number (weight/qty confusion)."
                    post_processing_warnings.append(warning_msg)
                    item.warning = (item.warning or "") + warning_msg
                    # Optionally, reset total_price to 0 or None to force AI to re-evaluate
                    # For now, we'll just warn and let AI re-prompt handle the correction.
                    # item.total_price = 0.0 

            # 2. 坐标归一化（Spatial Awareness）
            for item in structured_data.items:
                desc_bbox_info = self._find_text_bbox(item.description, ocr_results_with_boxes)
                price_str = f"{item.total_price:.2f}" # Format to match how it might appear in OCR
                price_bbox_info = self._find_text_bbox(price_str, ocr_results_with_boxes)

                if desc_bbox_info and price_bbox_info:
                    # Calculate center Y-coordinate for description and price bounding boxes
                    desc_y_center = (desc_bbox_info[0][0][1] + desc_bbox_info[0][2][1]) / 2 
                    price_y_center = (price_bbox_info[0][0][1] + price_bbox_info[0][2][1]) / 2

                    if abs(desc_y_center - price_y_center) > Y_TOLERANCE:
                        warning_msg = (
                            f"Item '{item.description}' and its price '{item.total_price}' "
                            f"show a Y-axis misalignment (> {Y_TOLERANCE}px). "
                            f"Desc Y: {desc_y_center:.2f}, Price Y: {price_y_center:.2f}."
                        )
                        post_processing_warnings.append(warning_msg)
                        item.warning = (item.warning or "") + warning_msg
                elif not desc_bbox_info:
                    post_processing_warnings.append(f"Could not find bounding box for item description: '{item.description}'.")
                elif not price_bbox_info:
                    post_processing_warnings.append(f"Could not find bounding box for item price: '{price_str}'.")

            # 将后处理警告添加到结构化数据的总警告中
            if post_processing_warnings:
                structured_data.warning = (structured_data.warning or "") + "\nPost-processing warnings: " + "; ".join(post_processing_warnings)

            # --- END NEW POST-PROCESSING LOGIC ---

            # --- Post-processing: Internal Calculation Audit (数学强制对齐) ---
            calculated_items_total = sum(item.total_price for item in structured_data.items)
            calculated_grand_total = calculated_items_total + structured_data.tax_amount
            
            # Allow for small floating point discrepancies
            if not math.isclose(calculated_grand_total, structured_data.total_amount, rel_tol=1e-2):
                logger.warning(f"Math check failed for invoice {structured_data.invoice_number or 'N/A'}. "
                               f"Calculated Total: {calculated_grand_total:.2f}, Extracted Total: {structured_data.total_amount:.2f}")
                
                # NEW: Check for $5 error tolerance for the specific retry feedback
                error_difference = abs(calculated_grand_total - structured_data.total_amount)

                if retry_count < MAX_RETRIES:
                    # Construct detailed feedback for AI, incorporating new warnings
                    feedback_parts = [
                        f"Your previous extraction resulted in a mathematical mismatch: "
                        f"Sum(Line Items: {calculated_items_total:.2f}) + Tax ({structured_data.tax_amount:.2f}) "
                        f"does not equal the Grand Total ({structured_data.total_amount:.2f}). "
                        f"Calculated: {calculated_grand_total:.2f}. "
                    ]

                    if [w for w in post_processing_warnings if 'Y-axis misalignment' in w]: # Check for Y-axis specific warnings
                        feedback_parts.append(
                            "CRITICAL: Some item descriptions and their prices were found to be misaligned on the Y-axis. "
                            "This strongly suggests a parsing error where an item's price was matched with the wrong description "
                            "or vice-versa. Please re-evaluate spatial alignment and re-pair descriptions with their correct prices. "
                            "The Y-axis misalignment indicates a severe line-matching error."
                        )
                    
                    if [w for w in post_processing_warnings if 'potential non-monetary number' in w]: # Check for non-monetary specific warnings
                        feedback_parts.append(
                            "WARNING: Some extracted 'total_price' values might be non-monetary numbers (e.g., weights, quantities) "
                            "mistaken for prices. Please re-examine values that appeared near 'lb', '@', or '/' indicators "
                            "and ensure only actual monetary amounts (XX.XX format, usually at line end) are assigned to 'total_price'."
                        )

                    if error_difference <= 5.0: # Specific feedback for weighted items within tolerance
                         feedback_parts.append(
                            "Your previous extraction failed the math check. "
                            "This might be due to weighted items. "
                            "Specifically check for items like 'RED GRAPE' and ensure the final line price is correctly extracted. "
                            "Double-check that numbers with 'lb', '@', or '/' were not mistaken for prices."
                        )
                    else: # General feedback for larger discrepancies
                        # 针对沃尔玛的特殊补丁 - reinforce for AI
                        feedback_parts.append(
                            "REMINDER for Walmart-like receipts: When you see patterns like '[TEXT] [WEIGHT] [PRICE]' on a line, "
                            "ensure that the number at the end of the line (e.g., '3.61') is always the 'total_price', "
                            "and numbers like '2.51' (which might be a weight) are assigned to 'quantity' or ignored if not a price. "
                            "Specifically, if '2.51 lb' appears, '2.51' is a weight, not a price."
                        )
                        
                        feedback_parts.append(
                            f"Please re-examine ALL numerical values, especially for items where quantities, unit prices, "
                            f"or weights (like 'lb') might have been confused with monetary amounts. "
                            f"Focus on reconciling the Grand Total with the sum of items and tax."
                        )

                    feedback = "\n\n".join(feedback_parts) # Use double newline for better readability in prompt
                    logger.info(f"Retrying AI parse with detailed feedback. Retry count: {retry_count + 1}")
                    return self.parse_with_ai(text, ocr_results_with_boxes, retry_count=retry_count + 1, feedback_message=feedback)
                else:
                    # Only add warning to structured_data if all retries failed
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
            structured_data = self.parse_with_ai(preprocessed_text, ocr_results_with_boxes=ocr_results_with_boxes)
            
            # Return both structured data and raw text for debugging
            result_dict = structured_data.model_dump()
            result_dict["_raw_text"] = preprocessed_text
            return result_dict

        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            return {"error": f"Image recognition failed: {str(e)}"}
