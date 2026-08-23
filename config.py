import os
from pathlib import Path
from typing import Optional, Dict, Any


class Config:
    """Configuration singleton."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Load .env file if it exists
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path)
            except ImportError:
                pass  # dotenv not installed, use os.environ

        # API Configuration
        self.API_URL = os.getenv("API_URL", "http://localhost:8080")
        self.API_KEY = os.getenv("API_KEY", "demo-key-1234")

        # Gemini Configuration - Use models that are actually available
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
        # self.GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # Updated to available model
        self.GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        self.GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.1"))

        # Processing Configuration
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.ENABLE_REVIEW = os.getenv("ENABLE_REVIEW", "true").lower() == "true"
        self.CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.8"))

        # Paths
        self.INVOICE_DIR = Path(os.getenv("INVOICE_DIR", "./invoices"))
        self.OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
        self.OUTPUT_DIR.mkdir(exist_ok=True)

        self._initialized = True

    def get_gemini_config(self) -> Dict[str, Any]:
        """Get Gemini configuration."""
        return {
                "api_key": self.GEMINI_API_KEY,
                "model": self.GEMINI_MODEL,
                "temperature": self.GEMINI_TEMPERATURE,
                }

    def validate(self) -> bool:
        """Validate configuration."""
        if not self.GEMINI_API_KEY:
            print("⚠️  Warning: GEMINI_API_KEY not set")
            return False
        return True


# Create a global config instance
config = Config()
