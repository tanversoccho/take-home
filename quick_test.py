import sys
from pathlib import Path

from file_detector import FileDetector
from api_client import APIClient
from config import config
from logger import default_logger

logger = default_logger


def quick_test():
    """Run a quick system test."""
    print("🔍 Quick System Test")
    print("=" * 50)

    # 1. Test API
    print("\n1. Testing API connection...")
    api = APIClient()
    if api.health_check():
        print("✅ API is running")

        # Test partner fetch
        partners = api.get_partners()
        print(f"✅ Loaded {len(partners)} partners")

        # Test tax codes
        tax_codes = api.get_tax_codes()
        print(f"✅ Loaded {len(tax_codes)} tax codes")
    else:
        print("❌ API is not running. Start it with: python3 accounting_api.py")
        return False

    # 2. Test file detection
    print("\n2. Testing file detection...")
    detector = FileDetector()

    # Check if invoices exist
    invoice_dir = Path("invoices")
    if invoice_dir.exists() and any(invoice_dir.iterdir()):
        files = detector.detect_batch(str(invoice_dir))
        print(f"✅ Found {len(files)} invoice files")
        for f in files:
            print(f"   - {f.file_name} ({f.file_type.value})")
    else:
        print("⚠️  No invoices found in ./invoices/")
        print("   Generate test data: python3 test_data_generator.py")

    # 3. Check environment
    print("\n3. Checking environment...")
    if config.GEMINI_API_KEY:
        print("✅ GEMINI_API_KEY is set")
    else:
        print("❌ GEMINI_API_KEY is not set")
        print("   Add to .env file")
        return False

    print("\n✅ All systems ready!")
    print("\nTo process invoices:")
    print("  python3 invoice_processor.py --directory ./invoices")
    return True


if __name__ == "__main__":
    success = quick_test()
    sys.exit(0 if success else 1)
