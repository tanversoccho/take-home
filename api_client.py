import json
import requests
from typing import Dict, List, Optional, Any
from config import config
from logger import default_logger

logger = default_logger


class APIClient:
    """Client for the accounting system API."""

    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or config.API_URL
        self.api_key = api_key or config.API_KEY
        self.headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
                }
        self.partners_cache = None
        self.tax_codes_cache = None

    def _request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make an API request."""
        url = f"{self.base_url}{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError:
            logger.error(f"Could not connect to API at {self.base_url}")
            raise Exception(f"API connection failed: {self.base_url}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            if response.text:
                try:
                    return response.json()
                except:
                    pass
            raise
        except Exception as e:
            logger.error(f"API request failed: {e}")
            raise

    def health_check(self) -> bool:
        """Check if the API is healthy."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False

    def get_partners(self, force_refresh: bool = False) -> List[Dict]:
        """Get the partner master list."""
        if self.partners_cache is not None and not force_refresh:
            return self.partners_cache

        try:
            result = self._request("GET", "/partners")
            if result.get("success"):
                self.partners_cache = result["data"]["partners"]
                return self.partners_cache
            else:
                logger.error(f"Failed to fetch partners: {result.get('error')}")
                return []
        except Exception as e:
            logger.error(f"Error fetching partners: {e}")
            return []

    def get_tax_codes(self, force_refresh: bool = False) -> List[Dict]:
        """Get the tax codes."""
        if self.tax_codes_cache is not None and not force_refresh:
            return self.tax_codes_cache

        try:
            result = self._request("GET", "/tax-codes")
            if result.get("success"):
                self.tax_codes_cache = result["data"]["tax_codes"]
                return self.tax_codes_cache
            else:
                logger.error(f"Failed to fetch tax codes: {result.get('error')}")
                return []
        except Exception as e:
            logger.error(f"Error fetching tax codes: {e}")
            return []

    def register_invoice(self, invoice_data: Dict) -> Dict:
        """
        Register an invoice in the accounting system.

        Returns:
            Dict with 'success', 'data', and 'error' fields
        """
        try:
            result = self._request("POST", "/invoices", invoice_data)
            return result
        except Exception as e:
            return {
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "API_ERROR",
                        "message": str(e)
                        }
                    }

    def get_invoices(self) -> List[Dict]:
        """Get all registered invoices."""
        try:
            result = self._request("GET", "/invoices")
            if result.get("success"):
                return result["data"]["invoices"]
            else:
                logger.error(f"Failed to fetch invoices: {result.get('error')}")
                return []
        except Exception as e:
            logger.error(f"Error fetching invoices: {e}")
            return []

    def delete_invoices(self) -> int:
        """Delete all registered invoices."""
        try:
            result = self._request("DELETE", "/invoices")
            if result.get("success"):
                return result["data"]["removed"]
            else:
                logger.error(f"Failed to delete invoices: {result.get('error')}")
                return 0
        except Exception as e:
            logger.error(f"Error deleting invoices: {e}")
            return 0
