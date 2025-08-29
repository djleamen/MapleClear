#!/bin/bash
# Quick setup script for MapleClear development

set -e

echo "🍁 MapleClear Quick Setup"
echo "========================"

# Check requirements
echo "📋 Checking requirements..."

if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 20+ from https://nodejs.org"
    exit 1
fi

if ! command -v /opt/homebrew/bin/python3.9 &> /dev/null; then
    echo "❌ Python 3.9 not found. Please install Python 3.9 with: brew install python@3.9"
    exit 1
fi

echo "✅ Node.js: $(node --version)"
# Find python3.9 in PATH or fallback to Homebrew path
if command -v python3.9 &> /dev/null; then
    PYTHON=$(command -v python3.9)
elif [ -x /opt/homebrew/bin/python3.9 ]; then
    PYTHON=/opt/homebrew/bin/python3.9
else
    echo "❌ Python 3.9 not found. Please install Python 3.9 (e.g., with: brew install python@3.9)"
    exit 1
fi

echo "✅ Node.js: $(node --version)"
echo "✅ Python: $($PYTHON --version)"

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
if command -v pnpm &> /dev/null; then
    pnpm install
    cd extension && pnpm install && cd ..
else
    npm install
    cd extension && npm install && cd ..
fi

# Set up Python virtual environment
echo "🐍 Setting up Python environment..."
$PYTHON -m venv .venv
source .venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r server/requirements.txt

# Create data directory
echo "📁 Creating data directory..."
mkdir -p data

# Setup environment file for Groq API
echo "🔧 Setting up environment configuration..."
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << 'EOF'
# Groq API Configuration
GROQ=your_groq_api_key_here

# MapleClear Backend Configuration
MAPLECLEAR_BACKEND=groq
MAPLECLEAR_MODEL_PATH=openai/gpt-oss-20b
MAPLECLEAR_HOST=127.0.0.1
MAPLECLEAR_PORT=11434
EOF
    echo "⚠️  Please edit .env file and add your Groq API key"
else
    echo "✅ .env file already exists"
fi

# Seed terminology database
echo "🌱 Seeding terminology database..."
python tools/seed_terms.py --out data/terms.sqlite

# Build extension
echo "🔨 Building browser extension..."
cd extension
if command -v pnpm &> /dev/null; then
    pnpm build
else
    npm run build:deps
fi
cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Next steps:"
echo "  1. Configure Groq API key in .env file (required for testing)"
echo "     - Edit .env and replace 'your_groq_api_key_here' with your actual key"
echo "  2. Start the server: make dev-server"
echo "  3. Load extension in browser:"
echo "     - Chrome: chrome://extensions -> Load unpacked -> extension/dist"
echo "     - Firefox: about:debugging -> Load Temporary Add-on"
echo "  4. Visit demo page: open demo/canada-benefits.html"
echo ""
echo "💡 Use 'make demo' for one-click demo setup"
echo "📖 See README.md for detailed instructions"
