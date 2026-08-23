import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from file_detector import FileDetector, FileType
from gemini_extractor import GeminiExtractor
from api_client import APIClient
from partner_matcher import PartnerMatcher
from validation import InvoiceValidator
from config import config
from logger import default_logger, setup_logger

logger = default_logger


class InvoiceProcessor:
    """Process invoices with automatic file detection."""

    def __init__(self, enable_review: bool = True):
        self.enable_review = enable_review
        self.detector = FileDetector()
        self.api_client = APIClient()
        self.gemini = None
        self.validator = InvoiceValidator(self.api_client)
        self.partner_matcher = None

        # Statistics
        self.stats = {
                "total": 0,
                "processed": 0,
                "registered": 0,
                "failed": 0,
                "reviewed": 0
                }

        self._initialize_components()

    def _initialize_components(self):
        """Initialize AI and partner matcher."""
        try:
            self.gemini = GeminiExtractor()
        except ValueError as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            print("\n❌ Please set GEMINI_API_KEY in .env file")
            sys.exit(1)

        # Get partners from API
        partners = self.api_client.get_partners()
        if partners:
            self.partner_matcher = PartnerMatcher(partners)
            logger.info(f"Loaded {len(partners)} partners")
        else:
            logger.warning("No partners loaded from API")

    def process_directory(self, directory: str) -> Dict:
        """Process all invoices in a directory."""
        logger.info(f"Processing invoices from: {directory}")

        # Detect files
        files = self.detector.detect_batch(directory)

        if not files:
            print("❌ No invoice files found")
            return self.stats

        # Print detection report
        self.detector.print_detection_report(files)

        # Process each file
        results = []
        for file_metadata in files:
            result = self.process_file(file_metadata)
            results.append(result)

            # Update stats
            self.stats["total"] += 1
            if result["status"] == "success":
                self.stats["processed"] += 1
                if result.get("registered"):
                    self.stats["registered"] += 1
            else:
                self.stats["failed"] += 1

            if result.get("reviewed"):
                self.stats["reviewed"] += 1

        # Print summary
        self._print_summary()

        return self.stats

    def process_file(self, file_metadata) -> Dict:
        """Process a single invoice file."""
        result = {
                "file": file_metadata.file_name,
                "file_type": file_metadata.file_type.value,
                "status": "failed",
                "registered": False,
                "reviewed": False
                }

        print(f"\n📄 Processing: {file_metadata.file_name}")
        print(f"   Type: {file_metadata.file_type.value}")
        print(f"   Method: {self.detector.get_extraction_method(file_metadata)}")

        try:
            # Extract data
            extracted = self._extract_data(file_metadata)
            if not extracted:
                result["error"] = "Extraction failed"
                return result

            # Validate
            is_valid, errors, corrected = self.validator.validate_all(extracted)

            if not is_valid and self.enable_review:
                # Manual review
                print(f"\n⚠️  Validation issues found:")
                for error in errors:
                    print(f"   • {error}")

                if self._prompt_review(corrected):
                    result["reviewed"] = True
                    # Use corrected data for registration
                    invoice_data = self._prepare_invoice_data(corrected)
                else:
                    result["error"] = "Skipped by user"
                    return result
            else:
                invoice_data = self._prepare_invoice_data(corrected)

            # Register with API
            if invoice_data:
                api_result = self.api_client.register_invoice(invoice_data)
                if api_result.get("success"):
                    result["status"] = "success"
                    result["registered"] = True
                    result["api_response"] = api_result
                    print(f"✅ Invoice registered successfully!")
                    print(f"   Accounting ID: {api_result['data']['accounting_id']}")
                else:
                    error = api_result.get("error", {})
                    result["error"] = f"Registration failed: {error.get('message', 'Unknown error')}"
                    print(f"❌ {result['error']}")
            else:
                result["error"] = "Failed to prepare invoice data"

        except Exception as e:
            logger.error(f"Error processing {file_metadata.file_name}: {e}")
            result["error"] = str(e)
            print(f"❌ Error: {e}")

        return result

    def _extract_data(self, file_metadata) -> Optional[Dict]:
        """Extract data using the appropriate method."""
        method = self.detector.get_extraction_method(file_metadata)

        if method == "pdf_text":
            # Extract text with pdfplumber
            import pdfplumber
            try:
                with pdfplumber.open(file_metadata.file_path) as pdf:
                    text = ""
                    for page in pdf.pages[:2]:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"

                if text.strip():
                    return self.gemini.extract_from_text(text, file_metadata.file_name)
                else:
                    # Fallback to vision
                    return self.gemini.extract_from_image(file_metadata.file_path)
            except Exception as e:
                logger.error(f"PDF text extraction failed: {e}")
                return None

        elif method in ["pdf_scanned", "image"]:
            return self.gemini.extract_from_image(file_metadata.file_path)

        else:
            logger.error(f"No extraction method for: {method}")
            return None

    def _prepare_invoice_data(self, data: Dict) -> Optional[Dict]:
        """Prepare invoice data for API registration."""
        if not data:
            return None

        # Match supplier
        supplier_name = data.get("supplier_name")
        if supplier_name:
            partner_code = self.partner_matcher.match_partner(supplier_name)
            if not partner_code:
                logger.warning(f"Could not match supplier: {supplier_name}")
                if self.enable_review:
                    # Show available partners
                    print("\n📋 Available partners:")
                    for partner in self.partner_matcher.partners:
                        print(f"   {partner['partner_code']}: {partner['name']}")

                    # Ask user to select
                    code = input("\nEnter partner code (or press Enter to skip): ").strip()
                    if code:
                        partner_code = code
                    else:
                        return None
                else:
                    return None
        else:
            return None

        # Build invoice payload
        lines = []
        for line in data.get("lines", []):
            line_data = {
                    "description": line.get("description", ""),
                    "quantity": line.get("quantity"),
                    "unit": line.get("unit", "pcs"),
                    "unit_price": line.get("unit_price"),
                    "amount": line.get("amount", 0),
                    "tax_code": line.get("tax_code", "T10")
                    }
            lines.append(line_data)

        return {
                "partner_code": partner_code,
                "invoice_number": data.get("invoice_number", ""),
                "issue_date": data.get("issue_date", ""),
                "due_date": data.get("due_date") or data.get("issue_date"),
                "currency": "JPY",
                "lines": lines,
                "subtotal": data.get("subtotal", 0),
                "tax_amount": data.get("tax_amount", 0),
                "total_amount": data.get("total_amount", 0)
                }

    def _prompt_review(self, data: Dict) -> bool:
        """Prompt user to review and correct data."""
        print("\n📝 Review extracted data:")
        print("-" * 50)
        print(f"Supplier: {data.get('supplier_name', 'N/A')}")
        print(f"Invoice #: {data.get('invoice_number', 'N/A')}")
        print(f"Issue Date: {data.get('issue_date', 'N/A')}")
        print(f"Due Date: {data.get('due_date', 'N/A')}")
        print(f"Subtotal: {data.get('subtotal', 0):,}")
        print(f"Tax: {data.get('tax_amount', 0):,}")
        print(f"Total: {data.get('total_amount', 0):,}")

        print(f"\nLine Items ({len(data.get('lines', []))}):")
        for i, line in enumerate(data.get("lines", []), 1):
            print(f"  {i}. {line.get('description', 'N/A')} x {line.get('quantity', 'N/A')} "
                  f"{line.get('unit', 'N/A')} @ {line.get('unit_price', 'N/A')} = {line.get('amount', 0):,}")

        print("-" * 50)

        while True:
            choice = input("\nUse this data? (y/n/edit/skip): ").lower().strip()
            if choice == 'y':
                return True
            elif choice == 'n':
                return False
            elif choice == 'skip':
                return False
            elif choice == 'edit':
                # Simple edit mode
                print("\n📝 Edit mode - press Enter to keep current value")
                data['supplier_name'] = input(f"Supplier [{data.get('supplier_name', 'N/A')}]: ") or data.get('supplier_name')
                data['invoice_number'] = input(f"Invoice # [{data.get('invoice_number', 'N/A')}]: ") or data.get('invoice_number')

                # Continue editing...
                return self._prompt_review(data)

    def _print_summary(self):
        """Print processing summary."""
        print("\n" + "="*60)
        print("📊 PROCESSING SUMMARY")
        print("="*60)
        print(f"Total files: {self.stats['total']}")
        print(f"✅ Processed: {self.stats['processed']}")
        print(f"💾 Registered: {self.stats['registered']}")
        print(f"❌ Failed: {self.stats['failed']}")
        print(f"👁️  Reviewed: {self.stats['reviewed']}")
        print("="*60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Process invoices with AI")
    parser.add_argument("--directory", "-d", default="./invoices",
                        help="Directory containing invoice files")
    parser.add_argument("--review", "-r", action="store_true",
                        help="Enable manual review mode")
    parser.add_argument("--no-review", action="store_true",
                        help="Disable manual review mode")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        import logging
        logging.getLogger("invoice_processor").setLevel(logging.DEBUG)

    # Determine review mode
    enable_review = not args.no_review and (args.review or config.ENABLE_REVIEW)

    # Check API health
    api_client = APIClient()
    if not api_client.health_check():
        print("❌ Accounting API is not running!")
        print("   Please start it with: python3 accounting_api.py")
        sys.exit(1)

    # Create processor
    processor = InvoiceProcessor(enable_review=enable_review)

    # Process invoices
    processor.process_directory(args.directory)


if __name__ == "__main__":
    main()
