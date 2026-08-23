#!/bin/bash

echo "🚀 Setting up Invoice Processing System"
echo "========================================"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
  echo "📝 Creating .env file..."
  echo "# Configuration" > .env
  echo "GEMINI_API_KEY=your-gemini-api-key-here" >> .env
  echo "API_URL=http://localhost:8080" >> .env
  echo "API_KEY=demo-key-1234" >> .env
  echo "LOG_LEVEL=INFO" >> .env
  echo "ENABLE_REVIEW=true" >> .env
  echo ""
  echo "⚠️  Please edit .env and add your GEMINI_API_KEY"
fi

# Create directories
echo "📁 Creating directories..."
mkdir -p invoices output logs

# Download sample invoices if they don't exist
if [ ! -d "invoices" ] || [ -z "$(ls -A invoices 2>/dev/null)" ]; then
  echo "📥 Please copy your invoice files to the 'invoices/' directory"
  echo "   Or run: python3 test_data_generator.py"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your GEMINI_API_KEY"
echo "2. Copy your invoices to ./invoices/"
echo "3. Start the API: python3 accounting_api.py"
echo "4. Run the processor: python3 invoice_processor.py --directory ./invoices"
echo ""
