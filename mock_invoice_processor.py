import json
import os
from pathlib import Path
from datetime import datetime

class MockInvoiceProcessor:
    """Mock version that processes invoices without API calls."""

    def __init__(self):
        self.results = []
        self.stats = {"total": 0, "processed": 0, "registered": 0, "failed": 0}

    def process_directory(self, directory):
        """Process all invoices in a directory (mock)."""
        print("\n" + "="*60)
        print("📋 INVOICE PROCESSING DEMO (Mock Mode)")
        print("="*60)
        print("⚠️  Running in mock mode - no API calls made")
        print("✅ All invoices would be processed successfully")
        print("="*60)

        # Get all files
        files = list(Path(directory).glob("*.pdf")) + list(Path(directory).glob("*.jpg"))

        print(f"\n📄 Found {len(files)} invoice files")
        print("\n📋 Processing results (mock):")
        print("-"*40)

        # Simulate processing each file
        for i, file_path in enumerate(files, 1):
            result = {
                    "file": file_path.name,
                    "status": "success",
                    "mock_data": self._generate_mock_data(file_path.name)
                    }
            self.results.append(result)
            self.stats["total"] += 1
            self.stats["processed"] += 1
            self.stats["registered"] += 1

            print(f"✅ [{i}/{len(files)}] {file_path.name} -> Registered (mock)")

        # Print summary
        print("\n" + "="*60)
        print("📊 PROCESSING SUMMARY")
        print("="*60)
        print(f"Total files: {self.stats['total']}")
        print(f"✅ Processed: {self.stats['processed']}")
        print(f"💾 Registered: {self.stats['registered']}")
        print(f"❌ Failed: {self.stats['failed']}")
        print("="*60)
        print("\n💡 Demo completed successfully!")
        print("   Results are in the 'demo_results.json' file")

    def _generate_mock_data(self, filename):
        """Generate mock invoice data."""
        return {
                "invoice_number": f"INV-{datetime.now().strftime('%Y%m')}-{filename[:8]}",
                "supplier_name": "株式会社サンプル商事",
                "issue_date": "2026-01-15",
                "due_date": "2026-02-15",
                "subtotal": 150000,
                "tax_amount": 15000,
                "total_amount": 165000,
                "lines": [
                    {"description": "製品A-100", "quantity": 100, "unit": "pcs", "unit_price": 1000, "amount": 100000, "tax_code": "T10"},
                    {"description": "製品B-200", "quantity": 50, "unit": "pcs", "unit_price": 1000, "amount": 50000, "tax_code": "T10"}
                    ]
                }

    def save_results(self, output_file="demo_results.json"):
        """Save results to JSON file."""
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"💾 Results saved to {output_file}")

if __name__ == "__main__":
    processor = MockInvoiceProcessor()
    processor.process_directory("./invoices")
    processor.save_results()
