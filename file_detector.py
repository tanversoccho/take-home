import os
import re
import mimetypes
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum

import pdfplumber
from PIL import Image


class FileType(Enum):
    """Supported file types for invoice processing."""
    PDF_TEXT = "pdf_text"      # PDF with selectable text
    PDF_SCANNED = "pdf_scanned" # PDF with only images
    IMAGE = "image"            # JPG, PNG, etc.
    UNSUPPORTED = "unsupported"


@dataclass
class FileMetadata:
    """Metadata about a detected file."""
    file_path: str
    file_name: str
    file_type: FileType
    extension: str
    size_bytes: int
    mime_type: str
    is_scanned: bool
    page_count: Optional[int] = None
    has_text_layer: Optional[bool] = None
    detection_method: str = ""


class FileDetector:
    """
    Detects and classifies invoice files based on their content.
    Uses multiple strategies to determine the best extraction method.
    """

    # Common image extensions
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
    PDF_EXTENSIONS = {'.pdf'}

    # Japanese invoice keywords for text detection
    INVOICE_KEYWORDS = [
            '請求書', '御請求書', 'INVOICE', 'invoice',
            '請求書番号', '発行日', 'お支払期日'
            ]

    def __init__(self):
        """Initialize the file detector."""
        mimetypes.init()

    def detect_file(self, file_path: str) -> Optional[FileMetadata]:
        """
        Detect the file type and return metadata.

        Args:
            file_path: Path to the file

        Returns:
            FileMetadata if supported, None otherwise
        """
        path = Path(file_path)

        if not path.exists():
            print(f"❌ File not found: {file_path}")
            return None

        # Get basic info
        extension = path.suffix.lower()
        file_name = path.name
        size_bytes = path.stat().st_size

        # Determine mime type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = self._guess_mime_from_extension(extension)

        # Classify by extension first
        file_type = self._classify_by_extension(extension)

        if file_type == FileType.UNSUPPORTED:
            print(f"⚠️  Unsupported file type: {extension} for {file_name}")
            return None

        # For PDFs, determine if text layer exists
        is_scanned = False
        has_text_layer = None
        page_count = None
        detection_method = "extension"

        if file_type == FileType.PDF_TEXT or file_type == FileType.PDF_SCANNED:
            # Analyze PDF content
            try:
                with pdfplumber.open(file_path) as pdf:
                    page_count = len(pdf.pages)
                    has_text_layer = self._has_text_layer(pdf)
                    is_scanned = not has_text_layer

                    # If we found text, verify it contains invoice content
                    if has_text_layer:
                        has_invoice_content = self._check_invoice_content(pdf)
                        if not has_invoice_content:
                            # Might be a scanned PDF misclassified
                            is_scanned = True
                            has_text_layer = False
                            file_type = FileType.PDF_SCANNED
                            detection_method = "content_check"
                    else:
                        file_type = FileType.PDF_SCANNED
                        detection_method = "scanned_detected"

            except Exception as e:
                print(f"⚠️  Error analyzing PDF {file_name}: {e}")
                # Fallback: treat as scanned
                is_scanned = True
                has_text_layer = False
                file_type = FileType.PDF_SCANNED
                detection_method = "fallback"

        elif file_type == FileType.IMAGE:
            # Verify it's a valid image
            try:
                with Image.open(file_path) as img:
                    # Image is valid
                    is_scanned = True  # Images are always "scanned" for our purposes
                    detection_method = "image_verified"
            except Exception as e:
                print(f"⚠️  Invalid image file {file_name}: {e}")
                return None

        return FileMetadata(
                file_path=str(path.absolute()),
                file_name=file_name,
                file_type=file_type,
                extension=extension,
                size_bytes=size_bytes,
                mime_type=mime_type,
                is_scanned=is_scanned,
                page_count=page_count,
                has_text_layer=has_text_layer,
                detection_method=detection_method
                )

    def _classify_by_extension(self, extension: str) -> FileType:
        """Classify file by its extension."""
        if extension in self.PDF_EXTENSIONS:
            return FileType.PDF_TEXT  # Will be refined later
        elif extension in self.IMAGE_EXTENSIONS:
            return FileType.IMAGE
        else:
            return FileType.UNSUPPORTED

    def _guess_mime_from_extension(self, extension: str) -> str:
        """Guess MIME type from extension."""
        mime_map = {
                '.pdf': 'application/pdf',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.bmp': 'image/bmp',
                '.tiff': 'image/tiff',
                '.tif': 'image/tiff',
                }
        return mime_map.get(extension, 'application/octet-stream')

    def _has_text_layer(self, pdf) -> bool:
        """
        Check if the PDF has a text layer by examining page content.

        Returns:
            True if text was found, False otherwise
        """
        try:
            # Check first few pages
            pages_to_check = min(3, len(pdf.pages))
            for page in pdf.pages[:pages_to_check]:
                text = page.extract_text()
                if text and len(text.strip()) > 20:  # At least some text
                    return True
            return False
        except Exception:
            return False

    def _check_invoice_content(self, pdf) -> bool:
        """
        Check if the PDF text contains invoice-related keywords.

        Returns:
            True if invoice content is detected
        """
        try:
            # Check first page
            if pdf.pages:
                text = pdf.pages[0].extract_text()
                if text:
                    # Check for Japanese invoice keywords
                    for keyword in self.INVOICE_KEYWORDS:
                        if keyword in text:
                            return True

                    # Check for numbers that look like invoice numbers
                    # Common format: YM-2026-0107, INV-2026-001, etc.
                    invoice_patterns = [
                            r'[A-Z]{2,}[-]\d{4}[-]\d{4}',  # YM-2026-0107
                            r'[A-Z]{2,}[-]\d{4}[-]\d{3}',  # INV-2026-001
                            r'請求書番号[:]?\s*[A-Z0-9-]+',  # Japanese format
                            ]
                    for pattern in invoice_patterns:
                        if re.search(pattern, text, re.IGNORECASE):
                            return True
            return False
        except Exception:
            return False

    def detect_batch(self, directory: str, extensions: Optional[List[str]] = None) -> List[FileMetadata]:
        """
        Detect all invoice files in a directory.

        Args:
            directory: Directory path to scan
            extensions: Optional list of extensions to filter

        Returns:
            List of FileMetadata for supported files
        """
        result = []
        path = Path(directory)

        if not path.exists():
            print(f"❌ Directory not found: {directory}")
            return result

        # Get all files
        all_files = [f for f in path.iterdir() if f.is_file()]

        # Filter by extension if specified
        if extensions:
            extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' 
                          for ext in extensions]
            all_files = [f for f in all_files if f.suffix.lower() in extensions]

        # Detect each file
        for file_path in all_files:
            metadata = self.detect_file(str(file_path))
            if metadata:
                result.append(metadata)

        # Sort by file name
        result.sort(key=lambda x: x.file_name)

        return result

    def get_extraction_method(self, metadata: FileMetadata) -> str:
        """
        Determine the appropriate extraction method based on file type.

        Returns:
            Method name: 'pdf_text', 'pdf_scanned', 'image', or 'fallback'
        """
        if metadata.file_type == FileType.PDF_TEXT:
            return 'pdf_text'
        elif metadata.file_type == FileType.PDF_SCANNED:
            return 'pdf_scanned'
        elif metadata.file_type == FileType.IMAGE:
            return 'image'
        else:
            return 'fallback'

    def get_file_summary(self, metadata: FileMetadata) -> str:
        """Generate a human-readable summary of the file."""
        type_str = {
                FileType.PDF_TEXT: "📄 PDF (text)",
                FileType.PDF_SCANNED: "📄 PDF (scanned)",
                FileType.IMAGE: "🖼️ Image",
                FileType.UNSUPPORTED: "❌ Unsupported"
                }.get(metadata.file_type, "Unknown")

        details = []
        if metadata.page_count:
            details.append(f"{metadata.page_count} pages")
        if metadata.has_text_layer is not None:
            details.append("has text" if metadata.has_text_layer else "scanned only")
        if metadata.detection_method:
            details.append(f"detected: {metadata.detection_method}")

        detail_str = f" ({', '.join(details)})" if details else ""

        size_kb = metadata.size_bytes / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"

        return f"{type_str} {metadata.file_name} - {size_str}{detail_str}"

    def print_detection_report(self, metadata_list: List[FileMetadata]):
        """Print a formatted detection report."""
        if not metadata_list:
            print("❌ No valid invoice files found")
            return

        print("\n" + "="*60)
        print("📋 FILE DETECTION REPORT")
        print("="*60)

        for i, metadata in enumerate(metadata_list, 1):
            print(f"{i:2}. {self.get_file_summary(metadata)}")
            print(f"    Method: {self.get_extraction_method(metadata)}")
            print()

        # Summary statistics
        type_counts = {}
        total_size = 0
        for m in metadata_list:
            type_counts[m.file_type] = type_counts.get(m.file_type, 0) + 1
            total_size += m.size_bytes

        print("-"*60)
        print("📊 Summary:")
        print(f"  Total files: {len(metadata_list)}")
        for file_type, count in type_counts.items():
            label = file_type.value.replace('_', ' ').title()
            print(f"  {label}: {count}")
        print(f"  Total size: {total_size / (1024*1024):.2f} MB")
        print("="*60)


# ============================================
# Integration with invoice_processor.py
# ============================================

class SmartInvoiceProcessor:
    """
    Enhanced invoice processor that uses file detection to choose
    the best extraction method automatically.
    """

    def __init__(self, gemini_client, api_client):
        self.detector = FileDetector()
        self.gemini_client = gemini_client
        self.api_client = api_client

    def process_invoice(self, file_path: str) -> Dict:
        """Process a single invoice with automatic method selection."""
        # Detect file type
        metadata = self.detector.detect_file(file_path)
        if not metadata:
            return {"status": "error", "message": "Unsupported file type"}

        print(f"\n📄 Processing: {metadata.file_name}")
        print(f"   Type: {metadata.file_type.value}")
        print(f"   Method: {self.detector.get_extraction_method(metadata)}")

        # Extract based on file type
        if metadata.file_type == FileType.PDF_TEXT:
            extracted = self._extract_pdf_text(metadata)
        elif metadata.file_type == FileType.PDF_SCANNED:
            extracted = self._extract_pdf_scanned(metadata)
        elif metadata.file_type == FileType.IMAGE:
            extracted = self._extract_image(metadata)
        else:
            return {"status": "error", "message": "No extraction method available"}

        # Validate and register
        if extracted:
            return self._validate_and_register(extracted)
        else:
            return {"status": "error", "message": "Extraction failed"}

    def _extract_pdf_text(self, metadata: FileMetadata) -> Dict:
        """Extract using pdfplumber for text-based PDFs."""
        try:
            import pdfplumber
            with pdfplumber.open(metadata.file_path) as pdf:
                text = ""
                for page in pdf.pages[:2]:  # First 2 pages
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

            if text.strip():
                return self.gemini_client.extract_from_text(text, metadata.file_name)
            else:
                # Fallback to vision
                return self.gemini_client.extract_from_image(metadata.file_path)
        except Exception as e:
            print(f"❌ PDF extraction error: {e}")
            return None

    def _extract_pdf_scanned(self, metadata: FileMetadata) -> Dict:
        """Extract using Gemini vision for scanned PDFs."""
        return self.gemini_client.extract_from_image(metadata.file_path)

    def _extract_image(self, metadata: FileMetadata) -> Dict:
        """Extract using Gemini vision for images."""
        return self.gemini_client.extract_from_image(metadata.file_path)

    def _validate_and_register(self, extracted: Dict) -> Dict:
        """Validate extracted data and register via API."""
        # Validation logic here (imported from validation.py)
        # ...
        pass


# ============================================
# Usage Example
# ============================================

def main():
    """Demonstrate file detection functionality."""
    # Create detector
    detector = FileDetector()

    # Detect all files in the invoices directory
    invoices_dir = "./invoices"
    files = detector.detect_batch(invoices_dir)

    # Print report
    detector.print_detection_report(files)

    # Show detailed info for each file
    print("\n📌 Detailed File Information:")
    print("-"*60)
    for file in files:
        print(f"\n{file.file_name}:")
        print(f"  Path: {file.file_path}")
        print(f"  Type: {file.file_type.value}")
        print(f"  Scanned: {file.is_scanned}")
        print(f"  Pages: {file.page_count or 'N/A'}")
        print(f"  Has Text: {file.has_text_layer or 'N/A'}")
        print(f"  MIME: {file.mime_type}")
        print(f"  Size: {file.size_bytes:,} bytes")
        print(f"  Method: {detector.get_extraction_method(file)}")


if __name__ == "__main__":
    main()
