# 🍁 MapleClear

> Simplifying Canadian government webpages into plain language with local AI

MapleClear is a browser extension that uses local AI inference to simplify complex government text and translate it into multiple languages, making Canadian government information more accessible to all citizens.

Submitted to the [OpenAI Open Model Hackathon](https://openai.devpost.com)
Categories: For Humanity (primary), Best Local Agent (secondary), Most Useful Fine-Tune (secondary)

## Features

- **Plain Language Simplification**: Convert complex government jargon into Grade 7 reading level
- **Multi-Language Translation**: Translate to French, Spanish, Chinese, Punjabi, Arabic, and more
- **Split-Screen View**: Compare original and simplified/translated content side-by-side
- **Acronym Detection**: Hover tooltips for government acronyms (CRA, EI, GST, etc.)
- **Local or Cloud AI**: Run fully on-device (llama.cpp, LM Studio, Hugging Face, vLLM) or use the Groq API for speed. The popup always says which one is active, because with Groq the page text is sent to Groq's servers
- **Government Site Integration**: Optimized for Canada.ca and gc.ca domains

## Architecture

### Browser Extension (`/extension/`)
- **Popup Interface** (`popup.html`, `popup.js`): Main extension UI with action selection
- **Split-Screen Mode** (`content-script.ts`): Side-by-side comparison of original vs processed content
- **Panel View** (`panel.html`, `panel.js`): Advanced processing options and results
- **Background Service** (`background.ts`): Extension lifecycle and server status monitoring
- **Manifest V3** (`manifest.json`): Modern extension configuration

### Local AI Server (`/server/`)
```
server/
├── app.py                 # FastAPI server with health checks and CORS
├── backends/              # Pluggable AI inference backends
│   ├── base.py           # Abstract backend interface
│   ├── groq_backend.py   # Groq API integration (default)
│   ├── huggingface_backend.py  # Local transformers
│   ├── lmstudio_backend.py     # LM Studio integration
│   ├── vllm_backend.py   # vLLM for production
│   └── llama_cpp.py      # llama.cpp integration
└── prompts/
    └── schema.py         # Response models and validation
```

### Key Components

#### Backend Abstraction
All AI backends implement the same interface:
- `simplify()` - Convert to plain language
- `translate()` - Multi-language translation  
- `expand_acronyms()` - Government acronym definitions
- `get_model_info()` - Backend status and capabilities

#### Model Support
- **Groq API**: Fast cloud inference (default for demos)
- **Local Models**: gpt-oss-20b, Llama 2/3, Mistral
- **Apple Silicon**: Optimized through LM Studio integration
- **Quantization**: 8-bit/16-bit for resource efficiency

## Quick Start

### 1. Install Dependencies

**Server:**
```bash
cd server
pip install -r requirements-minimal.txt
```

**Extension:**
```bash
cd extension
npm install
npm run build
```

### 2. Start the Server

**Using Groq:**
```bash
./setup.sh
make dev-server
```
OR
```bash
export GROQ=your_groq_api_key
python -m uvicorn server.app:app --host 127.0.0.1 --port 11434
```

**Using Local Models:**
```bash
export MAPLECLEAR_BACKEND=huggingface
export MAPLECLEAR_MODEL_PATH=openai/gpt-oss-20b
python -m uvicorn server.app:app --host 127.0.0.1 --port 11434
```

### 3. Load Extension

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked" and select the `extension/dist` folder
4. Visit a Canada.ca page and click the MapleClear icon

## Development

### Backend Switching
```bash
export MAPLECLEAR_BACKEND=groq        # Groq API (fast)
export MAPLECLEAR_BACKEND=lmstudio    # LM Studio (Apple Silicon optimized)
export MAPLECLEAR_BACKEND=huggingface # Local transformers
export MAPLECLEAR_BACKEND=vllm        # Production inference
```

### Extension Development
```bash
cd extension
npm run dev  # Watch mode for development
npm run build  # Production build
```

### Testing
```bash
# Test server
cd server && python -m pytest

# Test extension
cd extension && npm test

# Demo page
open demo/canada-benefits.html
```

## Project Structure

```
MapleClear/
├── README.md
├── LICENSE                       # Apache 2.0 license
├── Makefile                      # Build automation
├── setup.sh                      # Environment setup
├── .env                          # Environment variables
├── .gitignore                    # Git ignore patterns
│
├── server/                       # FastAPI backend
│   ├── app.py                    # Main server application
│   ├── requirements.txt          # Full dependencies
│   ├── requirements-minimal.txt  # Minimal setup
│   ├── backends/                 # AI inference backends
│   │   ├── __init__.py
│   │   ├── base.py                 # Abstract backend class
│   │   ├── groq_backend.py         # Groq API integration
│   │   ├── huggingface_backend.py  # Local transformers
│   │   ├── lmstudio_backend.py     # LM Studio integration
│   │   ├── vllm_backend.py         # vLLM inference
│   │   └── llama_cpp.py            # llama.cpp integration
│   └── prompts/
│       └── schema.py           # Pydantic models
│
├── extension/                  # Browser extension
│   ├── package.json            # Extension dependencies
│   ├── vite.config.ts          # Build configuration
│   ├── tsconfig.json           # TypeScript configuration
│   ├── src/
│   │   ├── manifest.json       # Extension manifest (MV3)
│   │   ├── popup.html          # Extension popup UI
│   │   ├── popup.js            # Popup functionality
│   │   ├── popup.css           # Popup styling
│   │   ├── panel.html          # Advanced panel UI
│   │   ├── panel.js            # Panel functionality  
│   │   ├── panel.css           # Panel styling
│   │   ├── content-script.ts   # Page interaction logic
│   │   ├── content-styles.css  # Content script styling
│   │   ├── background.ts       # Service worker
│   │   └── browser-polyfill.js # Cross-browser compatibility
│   └── dist/                   # Built extension files
│
├── tools/
│   └── seed_terms.py         # Government acronym database
│
└── demo/
    └── canada-benefits.html  # Test page with government content
```

## Configuration

### Environment Variables
```bash
# Server Configuration
MAPLECLEAR_BACKEND=groq                   # AI backend selection
MAPLECLEAR_MODEL_PATH=openai/gpt-oss-20b  # Model path
MAPLECLEAR_HOST=127.0.0.1                 # Server host
MAPLECLEAR_PORT=11434                     # Server port

# API Keys (if using cloud backends)
GROQ=your_groq_api_key                  # Groq API key

# Database
MAPLECLEAR_TERMS_DB=data/terms.sqlite   # Acronym database
```

### Backend Options

| Backend | Use Case | Requirements |
|---------|----------|-------------|
| `groq` | Fast demos, cloud inference | API key |
| `lmstudio` | Apple Silicon local inference | LM Studio app |
| `huggingface` | Local transformers | GPU/CPU, 8GB+ RAM |
| `vllm` | Production deployment | GPU, high memory |
| `llama.cpp` | CPU inference | Compiled llama.cpp |

## Use Cases

### For Citizens
- Understand tax documents and benefit applications
- Navigate government services in plain language
- Access information in your preferred language
- Learn government acronyms and terminology

### For Government
- Improve accessibility and comprehension
- Reduce support calls and clarification requests
- Meet plain language standards
- Support diverse linguistic communities

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenAI for the gpt-oss models used in development and hosting the Open Model Hackathon
- Hackathon sponsors HuggingFace, Ollama, vLLM, NVIDIA, LM Studio
- Groq for providing free API credits to hackathon participants (needed for my testing)
- Government of Canada for open data and plain language initiatives
- The open source AI community for tools and inspiration

---

**⚠️ Note**: This is experimental software. AI-generated results should be reviewed for accuracy before use in official contexts.
