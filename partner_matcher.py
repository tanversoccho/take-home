import re
from typing import Dict, List, Optional, Tuple
from difflib import get_close_matches

from logger import default_logger

logger = default_logger


class PartnerMatcher:
    """Match supplier names to partner codes."""

    def __init__(self, partners: List[Dict]):
        self.partners = partners
        self._build_index()

    def _build_index(self):
        """Build search index for partner names and aliases."""
        self.name_index = {}
        self.alias_index = {}

        for partner in self.partners:
            code = partner["partner_code"]
            name = partner["name"]

            # Index by full name
            self.name_index[name] = code

            # Index by aliases
            for alias in partner.get("aliases", []):
                self.alias_index[alias] = code

            # Also index cleaned versions
            cleaned = self._clean_name(name)
            if cleaned != name:
                self.name_index[cleaned] = code

    def _clean_name(self, name: str) -> str:
        """Clean a company name for better matching."""
        # Remove common suffixes
        suffixes = ["株式会社", "有限会社", "合名会社", "合資会社", "合同会社"]
        cleaned = name
        for suffix in suffixes:
            cleaned = cleaned.replace(suffix, "")

        # Remove whitespace
        cleaned = "".join(cleaned.split())

        # Remove common prefixes
        prefixes = ["㈱", "株", "有", "合名", "合資", "合同"]
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]

        return cleaned.strip()

    def match_partner(self, supplier_name: str, threshold: float = 0.7) -> Optional[str]:
        """
        Find the best matching partner code for a supplier name.

        Args:
            supplier_name: The supplier name from the invoice
            threshold: Minimum similarity threshold (0-1)

        Returns:
            Partner code if found, None otherwise
        """
        if not supplier_name:
            return None

        # Clean the supplier name
        cleaned_supplier = self._clean_name(supplier_name)

        # 1. Exact match on full name
        if supplier_name in self.name_index:
            return self.name_index[supplier_name]

        # 2. Exact match on cleaned name
        if cleaned_supplier in self.name_index:
            return self.name_index[cleaned_supplier]

        # 3. Exact match on aliases
        if supplier_name in self.alias_index:
            return self.alias_index[supplier_name]
        if cleaned_supplier in self.alias_index:
            return self.alias_index[cleaned_supplier]

        # 4. Fuzzy match on names
        all_names = list(self.name_index.keys())
        matches = get_close_matches(supplier_name, all_names, n=3, cutoff=threshold)
        if matches:
            return self.name_index[matches[0]]

        # 5. Fuzzy match on cleaned names
        cleaned_names = [self._clean_name(n) for n in all_names]
        matches = get_close_matches(cleaned_supplier, cleaned_names, n=3, cutoff=threshold)
        if matches:
            # Find the original name from cleaned match
            for original in all_names:
                if self._clean_name(original) == matches[0]:
                    return self.name_index[original]

        # 6. Try matching on aliases
        aliases = list(self.alias_index.keys())
        matches = get_close_matches(supplier_name, aliases, n=3, cutoff=threshold)
        if matches:
            return self.alias_index[matches[0]]

        # 7. Fallback: partial match on any name
        for partner in self.partners:
            # Check if supplier name is contained in partner name
            if supplier_name in partner["name"] or partner["name"] in supplier_name:
                return partner["partner_code"]

            # Check aliases
            for alias in partner.get("aliases", []):
                if supplier_name in alias or alias in supplier_name:
                    return partner["partner_code"]

        logger.warning(f"No partner found for supplier: {supplier_name}")
        return None

    def get_partner_info(self, partner_code: str) -> Optional[Dict]:
        """Get partner information by code."""
        for partner in self.partners:
            if partner["partner_code"] == partner_code:
                return partner
        return None

    def find_best_match_with_score(self, supplier_name: str) -> Tuple[Optional[str], float]:
        """
        Find the best matching partner with a confidence score.

        Returns:
            (partner_code, confidence) tuple
        """
        if not supplier_name:
            return None, 0.0

        cleaned_supplier = self._clean_name(supplier_name)

        # Exact matches get score 1.0
        if supplier_name in self.name_index or cleaned_supplier in self.name_index:
            code = self.name_index.get(supplier_name) or self.name_index.get(cleaned_supplier)
            return code, 1.0

        if supplier_name in self.alias_index or cleaned_supplier in self.alias_index:
            code = self.alias_index.get(supplier_name) or self.alias_index.get(cleaned_supplier)
            return code, 0.95

        # Try fuzzy matching with different thresholds
        all_names = list(self.name_index.keys())

        for cutoff in [0.8, 0.7, 0.6]:
            matches = get_close_matches(supplier_name, all_names, n=1, cutoff=cutoff)
            if matches:
                return self.name_index[matches[0]], cutoff

        # Try fuzzy on cleaned names
        cleaned_names = [self._clean_name(n) for n in all_names]
        for cutoff in [0.8, 0.7, 0.6]:
            matches = get_close_matches(cleaned_supplier, cleaned_names, n=1, cutoff=cutoff)
            if matches:
                for original in all_names:
                    if self._clean_name(original) == matches[0]:
                        return self.name_index[original], cutoff * 0.9

        return None, 0.0
