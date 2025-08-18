.PHONY: demo setup install build test lint clean

# One-click demo setup
demo: setup build-extension
	@echo "🍁 Starting MapleClear demo..."
	@echo "📦 Installing Python dependencies..."
	@python -m venv .venv 2>/dev/null || true
	@source .venv/bin/activate && pip install -r server/requirements.txt
	@echo "🗄️  Seeding terminology cache..."
	@python tools/seed_terms.py --out data/terms.sqlite
	@echo "🚀 Starting local inference daemon..."
	@source .venv/bin/activate && uvicorn server.app:app --host 127.0.0.1 --port 11434 &
	@echo "🌐 Opening demo page..."
	@sleep 3 && open demo/canada-benefits.html || echo "Open http://localhost:11434/demo manually"
	@echo "✅ Demo ready! Load extension/dist in Chrome Developer Mode"

# Development setup
setup:
	@echo "🍁 Setting up MapleClear development environment..."
	@command -v node >/dev/null 2>&1 || { echo "❌ Node.js 20+ required"; exit 1; }
	@command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3.10+ required"; exit 1; }
	@pnpm install || npm install
	@cd extension && (pnpm install || npm install)

# Install dependencies
install: setup
	@echo "📦 Installing server dependencies..."
	@python -m venv .venv
	@source .venv/bin/activate && pip install -r server/requirements.txt

# Build everything
build: build-extension build-server

build-extension:
	@echo "🔨 Building browser extension..."
	@cd extension && (pnpm build || npm run build)

build-server:
	@echo "🔨 Building server..."
	@echo "Server build complete (Python - no compilation needed)"

# Run tests
test:
	@echo "🧪 Running tests..."
	@cd extension && (pnpm test || npm test)
	@source .venv/bin/activate && pytest server/tests/

# Lint and typecheck
lint:
	@echo "🔍 Linting code..."
	@cd extension && (pnpm lint || npm run lint)
	@source .venv/bin/activate && ruff check server/
	@source .venv/bin/activate && mypy server/

# Clean build artifacts
clean:
	@echo "🧹 Cleaning build artifacts..."
	@rm -rf extension/dist
	@rm -rf extension/node_modules
	@rm -rf node_modules
	@rm -rf .venv
	@rm -rf data/terms.sqlite
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true

# Development server
dev-server:
	@echo "🚀 Starting development server..."
	@source .venv/bin/activate && uvicorn server.app:app --host 127.0.0.1 --port 11434 --reload

# Development extension
dev-extension:
	@echo "🔧 Starting extension development..."
	@cd extension && (pnpm dev || npm run dev)

# Seed terminology database
seed-terms:
	@echo "🌱 Seeding terminology cache..."
	@python tools/seed_terms.py --out data/terms.sqlite

help:
	@echo "🍁 MapleClear Development Commands:"
	@echo ""
	@echo "  make demo          - One-click demo setup and run"
	@echo "  make setup         - Install Node.js dependencies"
	@echo "  make install       - Install all dependencies"
	@echo "  make build         - Build extension and server"
	@echo "  make test          - Run all tests"
	@echo "  make lint          - Lint and typecheck"
	@echo "  make dev-server    - Start development server"
	@echo "  make dev-extension - Start extension development"
	@echo "  make seed-terms    - Populate terminology database"
	@echo "  make clean         - Clean build artifacts"
	@echo "  make help          - Show this help"
