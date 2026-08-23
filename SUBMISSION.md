# Submission

- Name: MD.Tanver Rahman
- Submission date (YYYY-MM-DD):2026-08-27
- Hours actually spent: 8 hour
- Repository / how to run it:

## 1. Understanding the Request

**Client's stated problem**: Accounting staff manually type invoice data into the system, causing overtime and errors (like duplicate payments).

**The problem I set out to solve**: Build an automated pipeline that extracts structured invoice data from diverse file formats using AI, validates the extracted information against business rules and the target system's constraints, and registers it into the existing accounting system with a "human-in-the-loop" option for verification. The goal is to reduce manual data entry effort and eliminate typos while maintaining trust in the system.

I focused on **automation with verification**, not full autonomy, because:
1. The client wants to "see something working" – trust is key.
2. The accounting system has strict validation (amount mismatches are rejected).
3. 12 sample invoices are limited – I prioritize reliability over coverage.

---

## 2. What You Would Have Asked the Client

| What you wanted to ask | The assumption you made | Why |
|---|---|---|
| What is the expected volume of invoices per month? | ~1,000/month (based on "every month-end close turns into overtime"). | Reasonable for a mid-sized trading company; allows cost estimation. |
| Are there any other fields we should capture besides the ones in the API? | Only the API fields are needed for now. | The API spec is the source of truth; the client wants to "enter them automatically" into this system. |
| What is the tolerance for manual review vs. full automation? | Start with automated extraction + review for low-confidence cases. | The client mentioned "a typo nearly caused us to pay the same invoice twice" – they want accuracy over speed. |
| How should we handle supplier name variations? | Use the API's partner master and perform fuzzy matching. | The API only accepts `partner_code`; we must map invoice names to existing codes. |
| What is the expected accuracy threshold? | Aim for 90%+ extraction accuracy; human review catches the rest. | Realistic for an AI-first system with limited sample data. |
| Should we handle multi-page invoices? | No – samples are single-page; assume single-page for now. | None of the samples are multi-page; I'll note this as a future enhancement. |

---

## 3. Scoping Decisions

### What I Built (in order of priority)
1. **Core extraction pipeline** – reads all 12 sample invoices, extracts structured data with Gemini.
2. **Validation layer** – verifies extracted fields (schema, amounts, dates, supplier match).
3. **API integration** – registers validated invoices to the mock API.
4. **Cost & token tracking** – shows usage per run.
5. **Simple review mode** – prompts the user for low-confidence fields (`confidence < 0.8`).
6. **Logging & error handling** – detailed logs for debugging.

### What I Left Out (and why)
- **Web UI** – The assignment says "a screen for review" is optional. I chose a CLI review prompt instead to save time, as it fulfills the verification need without UI complexity.
- **Multi-threading/parallel processing** – Only 12 invoices; single-threaded is fine and simpler.
- **Persistent storage** – The API stores data in-memory; I assume the real system has persistence.
- **PDF OCR fallback** – For text-based PDFs, I use `pdfplumber`; for images, Gemini's vision handles OCR. I did not add a separate OCR layer like Tesseract, as Gemini does well on Japanese text.
- **Dockerization** – Not needed for this scale; a simple Python environment is sufficient.

**Why this order**: I prioritized getting the core automated pipeline working end-to-end over additional features. Without a working extraction+registration flow, there's nothing to demonstrate.

---

## 4. Design and Technology Choices

### End-to-End Flow
```
Invoice Files → File Detection → Text Extraction → LLM (Gemini) → JSON Validation → Partner Match → API Registration → Output Results
```

### Component Choices

| Component | Choice | Why |
|---|---|---|
| **Language** | Python 3.10+ | Fast to develop, excellent libraries for PDF/images, and matches the API's Python code. |
| **PDF Text Extraction** | `pdfplumber` | Handles both text-based and image-based PDFs gracefully (though text-based ones are best). |
| **Image Processing** | `PIL` (Pillow) | Lightweight and supported by Gemini's vision API. |
| **LLM** | Google Gemini 2.0 Flash | Free tier (60 requests/min), strong performance on Japanese text and images, JSON mode supported. |
| **LLM Prompting** | Structured JSON schema prompt | Ensures consistent, parseable output. Includes confidence scores per field. |
| **Partner Matching** | `difflib.get_close_matches` | Fuzzy matches the extracted supplier name against the API's partner list, using `aliases`. |
| **Date Parsing** | `datetime.strptime` | Enforces YYYY-MM-DD format for API compliance. |
| **Validation** | Custom rules (amount sums, tax calc) | Mimics the API's `AMOUNT_MISMATCH` validation to catch errors early. |

**What I decided against**:
- **GPT-4o**: More expensive; Gemini is sufficient and free.
- **LangChain/LlamaIndex**: Overkill for a simple extraction pipeline; direct API calls are simpler and more transparent.
- **FastAPI/Flask**: No web interface; this is a CLI tool.
- **Tesseract OCR**: Gemini's vision API is better at reading Japanese invoice layouts.

---

## 5. How You Used AI, and How You Checked It

### What You Delegated to AI
- **Text extraction from PDFs** (using Gemini for scanned images)
- **Structured data extraction** – invoice number, dates, line items, amounts, supplier name, tax registration number, bank details
- **Confidence scoring** – each field gets a confidence score (0.0–1.0)
- **Japanese language understanding** – parsing layout-specific terms

### How I Instructed It
I used a detailed system prompt that:
- Defines the expected JSON schema
- Maps Japanese field labels to English keys
- Explains the tax calculation logic (per-line tax code)
- Requires confidence scores for each field
- Handles "not found" cases gracefully

### How You Verified the Output
1. **Schema validation** – Ensures all required keys are present.
2. **Amount consistency** – Checks that `subtotal = sum(line amounts)`, `tax_amount = sum(floor(amount * rate))`.
3. **Date validity** – Ensures `issue_date <= due_date`.
4. **Supplier match** – Verifies the supplier name exists in the partner master (fuzzy fallback).
5. **Manual review** – If any confidence score < 0.8, or if validation fails, the user is prompted to review.

### A Case Where the AI Got It Wrong
**Invoice**: `invoice_05.jpg` (scanned image, Tokyo Foods Co., Ltd.)
**Issue**: The AI misread the supplier name as "東京フード株式会社" instead of "東京フーズ株式会社" (and the API partner is "東京フーズ株式会社").
**How I caught it**: The fuzzy matching failed (score < 0.8), triggering the manual review prompt.
**How I fixed it**: The user corrected it to the matching alias, and the invoice was registered successfully.

---

## 6. Integrating with the Accounting System

### How I Handled the API's Constraints
- **Date format**: Extracted dates are normalized to `YYYY-MM-DD`.
- **Tax codes**: The prompt forces the LLM to choose from `T10` (10%) or `T08` (8%).
- **Partner matching**: I pre-fetch the partner list and use fuzzy matching on the extracted supplier name against `name` and `aliases`.
- **Amount validation**: I pre-validate amounts using the same logic as the API to avoid rejection.
- **Duplicate detection**: Before posting, I check if an invoice with the same `partner_code` + `invoice_number` already exists.

### Results Table

| Invoice | Result | How You Handled It |
|---|---|---|
| invoice_01.pdf | Registered | Perfect extraction, no issues |
| invoice_02.pdf | Registered | Supplier matched via alias |
| invoice_03.pdf | Registered | All fields valid |
| invoice_04.jpg | Registered | Manual review passed |
| invoice_05.jpg | **Review required** | Supplier name misread; user corrected it |
| invoice_06.jpg | Registered | High confidence |
| invoice_07.jpg | Registered | Valid |
| invoice_08.jpg | **Failed** | Lines could not be parsed (layout too complex); flagged for manual entry |
| invoice_09.pdf | Registered | Scanned PDF handled by Gemini vision |
| invoice_10.jpg | Registered | Valid |
| invoice_11.jpg | Registered | Valid |
| invoice_12.jpg | **Review required** | Subtotal mismatch; user corrected the total amount |

---

## 7. Cost, Limits, and Risk in Production

| Metric | Estimate | Reasoning |
|---|---|---|
| **Cost per invoice** | ~$0.001–$0.005 | Gemini Flash: $0.000075 per input image (0.1¢) + $0.0003 per 1K output tokens. Each invoice uses ~1K input tokens + ~500 output tokens. |
| **Monthly cost (1,000 inv)** | ~$1–$5 | Very affordable; for larger volumes, use Gemini Flash or cheaper models. |
| **Processing time per invoice** | 3–5 seconds | API latency + LLM generation; could be parallelized. |
| **Where this breaks first** | Poor quality scans, handwritten notes, unusual layouts, or unsupported fields. | The model may hallucinate missing fields; human review catches this. |
| **How to find incorrect registrations** | Monitor the API's `AMOUNT_MISMATCH` errors and compare the daily registered total vs. expected totals. Also, log all extractions and review random samples weekly. | |

---

## 8. What You Would Do With Another 8 Hours

1. **Build a simple web dashboard** – For human review of all extractions, with edit-in-place and bulk approval/rejection. This would make the human-in-the-loop experience much smoother.
2. **Add retry logic and batching** – Handle network failures and process multiple invoices concurrently to reduce total time.
3. **Improve confidence scoring** – Train a simple classifier (or use the LLM) to identify fields where the model is unsure, and flag those automatically without user intervention.

---

## How to Run This Project

### 1. Clone the repository (or unzip the provided archive).

### 2. Install dependencies:
```bash
pip install pdfplumber google-generativeai pillow
```

### 3. Set up your Gemini API key:
```bash
export GEMINI_API_KEY="your-api-key-here"
```
Or set it in the `.env` file (I’ve included a template).

### 4. Start the mock accounting API:
```bash
python3 accounting_api.py
```
(Keep this running in a separate terminal.)

### 5. Run the invoice processor:
```bash
python3 invoice_processor.py --directory invoices --review
```
- `--directory` – Path to your invoices folder.
- `--review` – Enable manual review for low-confidence fields (optional).

### 6. View results:
- Registered invoices are logged to `output.log` and also displayed in the console.
- You can check the API: `curl http://localhost:8080/invoices -H 'X-API-Key: demo-key-1234'`

---

## File Structure

```
.
├── accounting_api.py       # Mock API (provided in assignment)
├── invoice_processor.py    # Main script
├── gemini_extractor.py     # Gemini integration and prompt logic
├── api_client.py           # API client with error handling
├── validation.py           # Validation rules
├── partner_matcher.py      # Fuzzy supplier matching
├── logger.py               # Logging setup
├── .env.template           # API key template
├── invoices/               # Sample invoices (12 files)
└── README.md               # This document
```

---

I've included everything needed to run the solution. The code is well-documented, and the README contains setup instructions. I'm happy to discuss any part of the design or trade-offs in more detail.
