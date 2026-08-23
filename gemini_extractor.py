import os
import json
import base64
import time
import random
import threading
import queue
import re
import traceback
from typing import Dict, Optional, Any, List
from pathlib import Path

# Suppress the deprecation warning
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai
from PIL import Image

from config import config
from logger import default_logger

logger = default_logger


class GeminiExtractor:
    """Extract invoice data using Google Gemini."""

    # List of known working models from the actual API response
    WORKING_MODELS = [
            "gemini-flash-latest",
            "gemini-pro-latest",
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-3.7-flash",
            "gemini-2.5-flash-lite",
            "gemini-flash-lite-latest"
            ]

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required")

        # Configure Gemini
        genai.configure(api_key=self.api_key)

        # Get the model name from config or use default
        self.model_name = config.GEMINI_MODEL
        self.temperature = config.GEMINI_TEMPERATURE

        # Rate limiting configuration
        self.max_retries = 3
        self.base_delay = 2
        self.max_delay = 60
        self._last_request_time = 0

        # Initialize the model
        self.model = self._initialize_model()

        # Log the model being used
        logger.info(f"Using Gemini model: {self.model_name}")

        # Load system prompt
        self.system_prompt = self._get_system_prompt()

    def _initialize_model(self):
        """Initialize the Gemini model with fallback options."""
        try:
            # Try the configured model first
            return genai.GenerativeModel(self.model_name)
        except Exception as e:
            logger.warning(f"Failed to initialize model {self.model_name}: {e}")

            # Try fallback models
            for fallback_model in self.WORKING_MODELS:
                if fallback_model != self.model_name:
                    try:
                        logger.info(f"Trying fallback model: {fallback_model}")
                        model = genai.GenerativeModel(fallback_model)
                        # Test the model with a simple prompt
                        test_response = model.generate_content("Say 'OK'")
                        if test_response and test_response.text:
                            logger.info(f"Successfully initialized {fallback_model}")
                            # Update config to use this model
                            self.model_name = fallback_model
                            return model
                    except Exception as e2:
                        logger.debug(f"Model {fallback_model} failed: {e2}")
                        continue

            # If all models fail, raise an error
            raise ValueError("No working Gemini model found. Please check your API key and internet connection.")

    def _calculate_delay(self, attempt: int, error: Exception = None) -> float:
        """Calculate delay with exponential backoff and jitter."""
        # Base delay with exponential backoff
        delay = self.base_delay * (2 ** attempt)

        # Add jitter to avoid thundering herd
        jitter = random.uniform(0.5, 1.5)
        delay = delay * jitter

        # Cap at max delay
        delay = min(delay, self.max_delay)

        # If it's a rate limit error, check if the API gave a retry delay
        if error and "429" in str(error):
            retry_match = re.search(r'retry in (\d+\.?\d*)s', str(error), re.IGNORECASE)
            if retry_match:
                api_delay = float(retry_match.group(1))
                if api_delay > delay:
                    delay = api_delay + random.uniform(0.5, 1.0)

        return delay

    def _wait_for_rate_limit(self):
        """Wait if needed to avoid rate limits."""
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        if elapsed < 2.0:  # Minimum 2 seconds between requests
            wait_time = 2.0 - elapsed + random.uniform(0, 0.5)
            logger.debug(f"Rate limit wait: {wait_time:.2f}s")
            time.sleep(wait_time)
        self._last_request_time = time.time()

    def _get_system_prompt(self) -> str:
        """Get the system prompt for invoice extraction."""
        return """You are an expert in extracting structured data from Japanese invoices.

CRITICAL INSTRUCTIONS:
1. Look for the SUPPLIER NAME at the top of the invoice (look for 御中, 株式会社, or company names)
2. Look for the INVOICE TABLE with line items - it usually contains columns like:
   - 品名・摘要 (Description)
   - 数量 (Quantity) 
   - 単位 (Unit)
   - 単価 (Unit price)
   - 金額 (Amount)

For EACH ROW in the invoice table, extract a line item with ALL fields.

Return ONLY valid JSON in this exact format:
{
    "supplier_name": "Company name from the invoice (look for 御中 or company name at top)",
    "supplier_registration_no": "Tax registration number (if available, look for 登録番号)",
    "invoice_number": "Invoice number (look for 請求書番号)",
    "issue_date": "YYYY-MM-DD (look for 発行日)",
    "due_date": "YYYY-MM-DD (look for お支払期日, if available otherwise null)",
    "currency": "JPY",
    "lines": [
        {
            "description": "Item description from the table",
            "quantity": number or null,
            "unit": "Unit (pcs, lot, etc.)",
            "unit_price": number or null,
            "amount": number,
            "tax_code": "T10" or "T08"
        }
    ],
    "subtotal": number (sum of all line amounts),
    "tax_amount": number (tax amount, usually 10% of subtotal),
    "total_amount": number (subtotal + tax),
    "bank_details": "Bank transfer details (if available, look for お振込先)"
}

Field Mapping Guide:
- 請求書番号 → invoice_number
- 発行日 → issue_date
- お支払期日 → due_date
- 品名・摘要 → description
- 数量 → quantity
- 単位 → unit
- 単価 → unit_price
- 金額 → amount
- 小計 → subtotal
- 消費税 → tax_amount
- 合計 → total_amount
- 登録番号 → supplier_registration_no
- 御中 → supplier_name
- お振込先 → bank_details

IMPORTANT RULES:
1. Extract EVERY line item from the invoice table - don't skip any rows
2. If there are multiple items, include ALL of them in the "lines" array
3. Calculate subtotal by summing ALL line amounts
4. Tax is typically 10% (T10) - use T10 unless you see 8% mentioned
5. All amounts must be integers (remove commas and decimals)
6. Dates must be in YYYY-MM-DD format
7. If a field is not found, set to null (not omit it)

EXAMPLE of what a good response looks like:
{
    "supplier_name": "株式会社山田製作所",
    "supplier_registration_no": "T1010001000101",
    "invoice_number": "YM-2026-0107",
    "issue_date": "2026-01-07",
    "due_date": "2026-02-28",
    "currency": "JPY",
    "lines": [
        {
            "description": "精密部品A-100",
            "quantity": 120,
            "unit": "pcs",
            "unit_price": 1250,
            "amount": 150000,
            "tax_code": "T10"
        },
        {
            "description": "梱包・運賃",
            "quantity": null,
            "unit": "lot",
            "unit_price": null,
            "amount": 18000,
            "tax_code": "T10"
        }
    ],
    "subtotal": 168000,
    "tax_amount": 16800,
    "total_amount": 184800,
    "bank_details": null
}

Remember: Extract ALL line items from the invoice table. This is the most important part of the extraction.
"""

    def extract_from_image(self, image_path: str) -> Optional[Dict]:
        """Extract invoice data from an image file with timeout."""
        try:
            # For PDF files, we need to handle them differently
            if image_path.lower().endswith('.pdf'):
                logger.warning(f"PDF files should use text extraction, not image: {image_path}")
                return None

            # Check if file exists
            if not Path(image_path).exists():
                logger.error(f"Image file not found: {image_path}")
                return None

            # Open and resize image
            try:
                img = Image.open(image_path)
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Resize if too large to reduce processing time
                max_size = 1024
                if img.width > max_size or img.height > max_size:
                    ratio = min(max_size / img.width, max_size / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    logger.info(f"Resized image to {new_size}")

            except Exception as e:
                logger.error(f"Failed to open image {image_path}: {e}")
                return None

            # Prepare the prompt
            prompt = f"""
Extract invoice data from this image.
This is a Japanese business invoice.
Return ONLY the JSON structure as specified.

File: {Path(image_path).name}
"""

            # Wait for rate limit
            self._wait_for_rate_limit()

            # Generate response with timeout using threading
            result_queue = queue.Queue()
            error_queue = queue.Queue()

            def generate_with_timeout():
                try:
                    response = self.model.generate_content(
                            [prompt, img],
                            generation_config=genai.types.GenerationConfig(
                                temperature=self.temperature,
                                response_mime_type="application/json",
                                max_output_tokens=1024
                                )
                            )
                    result_queue.put(response)
                except Exception as e:
                    error_queue.put(e)

            # Start the generation in a separate thread
            thread = threading.Thread(target=generate_with_timeout)
            thread.daemon = True
            thread.start()
            thread.join(timeout=60)  # 60 second timeout for images

            # Check if we got a response
            if thread.is_alive():
                logger.error(f"Request timed out after 60 seconds for {Path(image_path).name}")
                return None

            # Check for errors
            if not error_queue.empty():
                raise error_queue.get_nowait()

            # Get the response
            if result_queue.empty():
                logger.error("No response received")
                return None

            response = result_queue.get_nowait()

            if response and response.text:
                parsed = self._parse_response(response.text)
                if parsed:
                    return parsed
                else:
                    logger.warning(f"Failed to parse response for {Path(image_path).name}")
                    return None
            else:
                logger.warning(f"Empty response from Gemini for {Path(image_path).name}")
                return None

        except Exception as e:
            logger.error(f"Error extracting from image {image_path}: {e}")
            return None

    def extract_from_text(self, text: str, filename: str = None) -> Optional[Dict]:
        """Extract invoice data from text content with timeout."""
        try:
            if not text or len(text.strip()) < 10:
                logger.warning(f"Text content is too short for {filename or 'unknown file'}")
                return None

            # Truncate text if too long
            text_content = text[:3000]  # Reduced from 5000 to speed up
            if len(text) > 3000:
                logger.info(f"Truncated text from {len(text)} to 3000 characters")

            prompt = f"""
Extract invoice data from the following text.
This is from a Japanese business invoice.

Text content:
    {text_content}

File: {filename or "unknown"}

Return ONLY the JSON structure as specified in the system prompt.
"""

            # Wait for rate limit
            self._wait_for_rate_limit()

            # Generate response with timeout using threading
            result_queue = queue.Queue()
            error_queue = queue.Queue()

            def generate_with_timeout():
                try:
                    response = self.model.generate_content(
                            prompt,
                            generation_config=genai.types.GenerationConfig(
                                temperature=self.temperature,
                                response_mime_type="application/json",
                                max_output_tokens=1024
                                )
                            )
                    result_queue.put(response)
                except Exception as e:
                    error_queue.put(e)

            # Start the generation in a separate thread
            thread = threading.Thread(target=generate_with_timeout)
            thread.daemon = True
            thread.start()
            thread.join(timeout=45)  # 45 second timeout for text

            # Check if we got a response
            if thread.is_alive():
                logger.error(f"Request timed out after 45 seconds for {filename}")
                return None

            # Check for errors
            if not error_queue.empty():
                raise error_queue.get_nowait()

            # Get the response
            if result_queue.empty():
                logger.error("No response received")
                return None

            response = result_queue.get_nowait()

            if response and response.text:
                parsed = self._parse_response(response.text)
                if parsed:
                    return parsed
                else:
                    logger.warning(f"Failed to parse response for {filename}")
                    return None
            else:
                logger.warning(f"Empty response from Gemini for {filename}")
                return None

        except Exception as e:
            logger.error(f"Error extracting from text for {filename}: {e}")
            return None

    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """Parse the AI response and extract JSON."""
        try:
            if not response_text:
                logger.error("Empty response text")
                return None

            # Clean the response
            response_text = response_text.strip()

            # Log first 200 chars for debugging
            logger.debug(f"Response preview: {response_text[:200]}...")

            # Try multiple strategies to extract JSON

            # Strategy 1: Look for code block with JSON
            code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if code_block_match:
                try:
                    data = json.loads(code_block_match.group(1))
                    if data and isinstance(data, dict):
                        logger.info("Found JSON in code block")
                        return data
                except:
                    pass

            # Strategy 2: Find JSON between curly braces (nested)
            json_match = re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    if data and isinstance(data, dict):
                        logger.info("Found nested JSON")
                        return data
                except:
                    pass

            # Strategy 3: Find the outermost JSON object
            start = response_text.find('{')
            if start == -1:
                logger.error("No JSON found in response")
                logger.debug(f"Response was: {response_text[:500]}")
                return None

            # Find the matching closing brace
            brace_count = 0
            end = start
            for i, char in enumerate(response_text[start:], start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break

            if brace_count != 0:
                logger.warning("Unbalanced braces in response")
                # Try to find the last brace
                end = response_text.rfind('}') + 1
                if end == 0:
                    # Try to extract JSON with regex
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group()
                        try:
                            data = json.loads(json_str)
                            return data
                        except:
                            pass
                    return None

            json_str = response_text[start:end]

            # Remove any markdown formatting
            json_str = re.sub(r'^```json\s*', '', json_str)
            json_str = re.sub(r'\s*```$', '', json_str)

            # Try to parse
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                # Strategy 4: Try to fix common JSON issues
                logger.warning(f"JSON parse error: {e}")

                # Remove trailing commas
                json_str = re.sub(r',\s*}', '}', json_str)
                json_str = re.sub(r',\s*]', ']', json_str)

                # Fix missing quotes around keys
                json_str = re.sub(r'(\w+):', r'"\1":', json_str)

                # Remove control characters
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)

                # Try to parse again
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError as e2:
                    logger.error(f"Failed to parse JSON after cleanup: {e2}")
                    logger.debug(f"Cleaned JSON: {json_str[:500]}")
                    return None

            # Ensure required fields
            if not data.get('supplier_name'):
                logger.warning("Supplier name missing")

            # Ensure lines is a list
            if 'lines' not in data or not isinstance(data['lines'], list):
                data['lines'] = []

            # Set default confidence scores if missing
            if 'confidence' not in data:
                data['confidence'] = {
                        "supplier_name": 0.8,
                        "invoice_number": 0.8,
                        "issue_date": 0.8,
                        "lines": 0.7,
                        "amounts": 0.7
                        }

            # Validate line items have required fields
            for line in data['lines']:
                if 'description' not in line or not line['description']:
                    logger.warning("Line item missing description")
                if 'amount' not in line or not line['amount']:
                    logger.warning("Line item missing amount")

            logger.info(f"Successfully parsed invoice data for {data.get('invoice_number', 'unknown')} with {len(data['lines'])} line items")
            return data

        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            traceback.print_exc()
            return None

    def test_connection(self) -> bool:
        """Test the Gemini API connection."""
        try:
            test_prompt = "Respond with a simple 'OK' to confirm connection."
            response = self.model.generate_content(test_prompt)
            if response and response.text:
                logger.info("✅ Gemini API connection successful")
                return True
            else:
                logger.error("❌ Gemini API connection test failed - no response")
                return False
        except Exception as e:
            logger.error(f"❌ Gemini API connection test failed: {e}")
            return False
