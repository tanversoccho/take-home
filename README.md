# Invoice Processing System - Automated Invoice Intake

A complete, runnable implementation of an automated invoice intake system that extracts structured data from PDF and image invoices using AI and integrates with a mock accounting system API.

## 🚀 Overview

This system automates the process of reading invoices, extracting structured data, validating it, and registering it into an accounting system. It's designed to reduce manual data entry and eliminate errors like duplicate payments.

### Key Features

- **Multi-format Support**: Handles text-based PDFs, scanned image PDFs, and JPG images
- **AI-Powered Extraction**: Uses Google's Gemini models for robust extraction from Japanese invoices with structured JSON output
- **Smart File Detection**: Automatically detects file type and chooses the best extraction method
- **Validation & Verification**: Multiple verification layers including schema validation, amount consistency checks, and fuzzy partner matching
- **Human-in-the-Loop**: Manual review for low-confidence extractions or validation failures
- **Rate Limit Handling**: Exponential backoff and retry logic for API quotas
- **Mock Mode**: Run without API calls for demonstration purposes
- **Accounting API Integration**: Handles all API constraints (date format, tax codes, duplicate prevention)
- **Detailed Logging**: Comprehensive logging for debugging and audit trails

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Running the System](#running-the-system)
- [Demo Mode (No API Key Required)](#demo-mode-no-api-key-required)
- [Production Mode](#production-mode)
- [Project Structure](#project-structure)
- [API Integration](#api-integration)
- [Cost & Performance](#cost--performance)
- [Limitations & Risks](#limitations--risks)
- [Testing & Transparency](#testing--transparency)
- [License](#license)

---

## Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd take-home

# Install dependencies
pip install -r requirements.txt

# Run in demo mode (no API key needed)
python mock_invoice_processor.py

# OR run in production mode (needs Gemini API key)
# 1. Set up your API key in .env
# 2. Start the accounting API
python accounting_api.py
# 3. Run the processor
python invoice_processor.py --directory ./invoices --review
```

---

## Installation

### Prerequisites
- Python 3.9 or newer
- Gemini API key (free tier available at https://aistudio.google.com/)

### Setup

1. **Clone the repository**:
```bash
git clone <repository-url>
cd take-home
```

2. **Create and activate a virtual environment**:

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Configure API key**:
```bash
cp .env.template .env
# Edit .env and add your GEMINI_API_KEY
```

5. **Place your invoices** in the `invoices/` directory:
```bash
# Copy your invoice files
cp /path/to/invoices/*.pdf invoices/
cp /path/to/invoices/*.jpg invoices/
```

---

## Running the System

### Demo Mode (No API Key Required)

Perfect for demonstration or when you've hit API limits:

```bash
python mock_invoice_processor.py
```

**Output example:**
```
============================================================
📋 INVOICE PROCESSING DEMO (Mock Mode)
============================================================
⚠️  Running in mock mode - no API calls made
✅ All invoices would be processed successfully
============================================================

📄 Found 12 invoice files

📋 Processing results (mock):
----------------------------------------
✅ [1/12] invoice_01.pdf -> Registered (mock)
✅ [2/12] invoice_02.pdf -> Registered (mock)
✅ [3/12] invoice_03.pdf -> Registered (mock)
...

============================================================
📊 PROCESSING SUMMARY
============================================================
Total files: 12
✅ Processed: 12
💾 Registered: 12
❌ Failed: 0
============================================================

💡 Demo completed successfully!
   Results are in the 'demo_results.json' file
```

### Production Mode

**Step 1: Start the accounting API** (in a separate terminal):
```bash
python accounting_api.py
```
Expected output:
```
Mock Accounting API listening on http://localhost:8080
  API key: demo-key-1234
  Press Ctrl+C to stop.
```

**Step 2: Run the invoice processor**:
```bash
python invoice_processor.py --directory ./invoices --review
```

**Options**:
| Option | Description |
|--------|-------------|
| `--directory`, `-d` | Path to invoices folder (default: ./invoices) |
| `--review`, `-r` | Enable manual review for low-confidence fields |
| `--no-review` | Disable manual review mode |
| `--verbose`, `-v` | Enable verbose logging for debugging |

**Step 3: View results**:
```bash
# Check registered invoices via API
curl http://localhost:8080/invoices -H 'X-API-Key: demo-key-1234'

# View logs
tail -f logs/invoice_processor_*.log
```

---

## Project Structure

```
.
├── accounting_api.py          # Mock accounting system API
├── invoice_processor.py       # Main invoice processing pipeline
├── mock_invoice_processor.py  # Demo mode (no API calls)
├── gemini_extractor.py        # Gemini AI integration
├── api_client.py              # API client with error handling
├── validation.py              # Validation rules
├── partner_matcher.py         # Fuzzy supplier name matching
├── file_detector.py           # File type detection
├── logger.py                  # Logging setup
├── config.py                  # Configuration management
├── .env.template              # API key template
├── requirements.txt           # Python dependencies
├── invoices/                  # Sample invoice files (12)
├── logs/                      # Application logs
└── output/                    # Generated output files
```

---

## API Integration

### Accounting System API

The system integrates with the accounting API using these endpoints:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Liveness check |
| GET | `/partners` | Supplier master list |
| GET | `/tax-codes` | Tax code list |
| POST | `/invoices` | Register an invoice |
| GET | `/invoices` | List registered invoices |
| DELETE | `/invoices` | Delete all (reset) |

### Error Handling

The system handles these API error codes:
- `PARTNER_NOT_FOUND` - Supplier not in master → triggers manual review
- `DUPLICATE_INVOICE` - Already registered → prevents duplicates
- `AMOUNT_MISMATCH` - Invalid amounts → corrects before retry
- `VALIDATION_ERROR` - Malformed data → reviews and fixes
- `429` - Rate limit → exponential backoff retry

---

## Cost & Performance

| Metric | Estimate | Notes |
|--------|----------|-------|
| **Cost per invoice** | ~$0.001–$0.005 | Gemini Flash pricing |
| **Monthly cost (1,000 inv)** | ~$1–$5 | Very affordable |
| **Processing time** | 3-5 seconds | Including AI processing |
| **API rate limits** | 20 req/day (free) | 60 req/min (paid) |

### Free Tier Limits
- **Daily quota**: 20 requests/day
- **Per-minute quota**: 5 requests/minute
- **Models**: Multiple models available with separate quotas

---

## Limitations & Risks

### Known Limitations
1. **API Rate Limits**: Free tier limits can cause delays
2. **Invoice Quality**: Poor quality scans may reduce accuracy
3. **Layout Variations**: Unusual layouts may require manual review
4. **Japanese Language**: Optimized for Japanese; other languages may need adjustments

### Risk Mitigation
- ✅ Human review for low-confidence extractions
- ✅ Comprehensive logging for audit trails
- ✅ Automatic retry with exponential backoff
- ✅ Mock mode for testing without API calls
- ✅ Duplicate detection prevents double payments
- ✅ Amount validation catches calculation errors

---

## Testing & Transparency

### Real-World Testing Constraints

**Challenge**: The Gemini API free tier has strict quotas (20 requests/day, 5 requests/minute). During testing, the daily quota was exhausted before completing all 12 sample invoices.

**What I tested successfully**:
- ✅ File detection on all 12 invoices
- ✅ Extraction pipeline on multiple invoices
- ✅ API integration with mock system
- ✅ Validation logic
- ✅ Error handling and retry logic
- ✅ Human review workflow

**How I worked around it**:
1. **Mock Mode**: Created `mock_invoice_processor.py` to demonstrate full workflow without API calls
2. **Rate Limit Handling**: Implemented exponential backoff with retry logic
3. **Model Fallback**: System automatically tries alternative models
4. **Batch Processing**: Can process smaller batches to avoid hitting limits

### Verifying Correctness

The system includes multiple verification layers:
1. **Schema validation** - All required fields present
2. **Amount consistency** - Subtotal = sum of line items
3. **Date validation** - Valid format and logic
4. **Partner matching** - Supplier exists in master list
5. **Manual review** - Human oversight for confidence < 0.8
6. **Duplicate detection** - Prevents double registration

---

## Contributing

### Adding Support for New File Types
1. Add extension to `file_detector.py`
2. Add extraction method in `gemini_extractor.py`
3. Update validation rules if needed

### Customizing the AI Prompt
Edit `_get_system_prompt()` in `gemini_extractor.py` to:
- Support different languages
- Extract additional fields
- Change output format

### Adding New Validators
Add custom validation rules in `validation.py`:
```python
def validate_custom_field(data):
    # Your validation logic
    return True/False
```

---

## Troubleshooting

### Common Issues

**API Key Not Found**
```
❌ GEMINI_API_KEY is required
```
**Solution**: Add your API key to `.env` file

**Rate Limit Exceeded**
```
429 You exceeded your current quota
```
**Solution**: 
- Wait for quota reset (midnight PT)
- Use mock mode for testing
- Try a different model with separate quota

**API Not Running**
```
❌ Accounting API is not running!
```
**Solution**: Start the API with `python accounting_api.py`

**Missing Dependencies**
```
ModuleNotFoundError: No module named 'pdfplumber'
```
**Solution**: Install dependencies `pip install -r requirements.txt`

### Debug Mode
```bash
# Enable verbose logging
python invoice_processor.py --directory ./invoices --review --verbose

# Check logs
tail -f logs/invoice_processor_*.log
```



## Acknowledgments

- Google Gemini API for AI-powered extraction
- The assignment authors for the detailed requirements
- Sample invoices provided for testing

