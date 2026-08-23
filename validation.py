import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import math

from logger import default_logger

logger = default_logger


class InvoiceValidator:
    """Validate extracted invoice data."""

    def __init__(self, api_client=None):
        self.api_client = api_client
        self.tax_rates = {"T10": 0.10, "T08": 0.08}

    def validate_all(self, data: Dict) -> Tuple[bool, List[str], Dict]:
        """
        Validate all fields in the extracted data.

        Returns:
            (is_valid, errors, corrected_data)
        """
        errors = []
        corrected = data.copy()

        # Validate supplier name
        if not data.get("supplier_name"):
            errors.append("Supplier name is missing")

        # Validate invoice number
        invoice_num = data.get("invoice_number")
        if not invoice_num:
            errors.append("Invoice number is missing")
        elif not self._validate_invoice_number(invoice_num):
            errors.append(f"Invalid invoice number format: {invoice_num}")

        # Validate dates
        issue_date = data.get("issue_date")
        if issue_date:
            valid, error = self._validate_date(issue_date, "issue_date")
            if not valid:
                errors.append(error)
        else:
            errors.append("Issue date is missing")

        due_date = data.get("due_date")
        if due_date:
            valid, error = self._validate_date(due_date, "due_date")
            if not valid:
                errors.append(error)

        # Validate lines
        lines = data.get("lines", [])
        if not lines:
            errors.append("No line items found")
        else:
            for i, line in enumerate(lines):
                line_errors = self._validate_line(line, i)
                errors.extend(line_errors)

        # Validate amounts
        amount_errors, corrected = self._validate_amounts(corrected)
        errors.extend(amount_errors)

        return len(errors) == 0, errors, corrected

    def _validate_date(self, date_str: str, field_name: str) -> Tuple[bool, Optional[str]]:
        """Validate date format."""
        if not date_str:
            return True, None

        # Check format YYYY-MM-DD
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return False, f"{field_name} must be in YYYY-MM-DD format"

        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True, None
        except ValueError:
            return False, f"{field_name} is not a valid date"

    def _validate_invoice_number(self, invoice_num: str) -> bool:
        """Validate invoice number format."""
        # Accept various formats
        patterns = [
                r'^[A-Z0-9-]+$',  # Alphanumeric with hyphens
                r'^[A-Z]{2,}-\d{4}-\d{3,4}$',  # INV-2026-001
                r'^[A-Z]{2,}-\d{4}-\d{4}$',  # YM-2026-0107
                ]
        return any(re.match(p, invoice_num) for p in patterns)

    def _validate_line(self, line: Dict, index: int) -> List[str]:
        """Validate a single line item."""
        errors = []

        if not line.get("description"):
            errors.append(f"Line {index + 1}: Description is missing")

        if not line.get("unit"):
            errors.append(f"Line {index + 1}: Unit is missing")

        amount = line.get("amount")
        if not isinstance(amount, int) or amount <= 0:
            errors.append(f"Line {index + 1}: Amount must be a positive integer")

        quantity = line.get("quantity")
        if quantity is not None and not isinstance(quantity, int):
            errors.append(f"Line {index + 1}: Quantity must be an integer or null")

        unit_price = line.get("unit_price")
        if unit_price is not None and not isinstance(unit_price, int):
            errors.append(f"Line {index + 1}: Unit price must be an integer or null")

        tax_code = line.get("tax_code")
        if tax_code not in self.tax_rates:
            errors.append(f"Line {index + 1}: Invalid tax code '{tax_code}'. Must be T10 or T08")

        return errors

    def _validate_amounts(self, data: Dict) -> Tuple[List[str], Dict]:
        """Validate amount calculations."""
        errors = []
        corrected = data.copy()
        lines = data.get("lines", [])

        if not lines:
            return ["No lines to calculate amounts"], corrected

        # Calculate subtotal
        expected_subtotal = sum(line.get("amount", 0) for line in lines)
        received_subtotal = data.get("subtotal")

        if received_subtotal is not None and received_subtotal != expected_subtotal:
            errors.append(f"Subtotal mismatch: expected {expected_subtotal}, got {received_subtotal}")
            corrected["subtotal"] = expected_subtotal

        # Calculate tax
        subtotal_by_code = {}
        for line in lines:
            tax_code = line.get("tax_code", "T10")
            amount = line.get("amount", 0)
            subtotal_by_code[tax_code] = subtotal_by_code.get(tax_code, 0) + amount

        expected_tax = sum(
                math.floor(amount * self.tax_rates.get(code, 0.10))
                for code, amount in subtotal_by_code.items()
                )
        received_tax = data.get("tax_amount")

        if received_tax is not None and received_tax != expected_tax:
            errors.append(f"Tax amount mismatch: expected {expected_tax}, got {received_tax}")
            corrected["tax_amount"] = expected_tax

        # Calculate total
        expected_total = expected_subtotal + expected_tax
        received_total = data.get("total_amount")

        if received_total is not None and received_total != expected_total:
            errors.append(f"Total amount mismatch: expected {expected_total}, got {received_total}")
            corrected["total_amount"] = expected_total

        return errors, corrected
