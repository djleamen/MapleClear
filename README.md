# MapleClear

A privacy-first browser extension for the [OpenAI Open Model Hackathon](https://openai.devpost.com) that rewrites Canadian government webpages into plain language, expands acronyms, and provides one-click translation. MapleClear runs locally by default using open-weight `gpt-oss` models, so newcomers and ESL readers can understand benefits, immigration, taxes, and public health information without sending sensitive data to the cloud. Optional experimental support is included for Indigenous language features with a strong focus on community consent and clear labeling.

> Categories: **For Humanity** (primary), **Best Local Agent** (secondary), **Most Useful Fine-Tune** (secondary)

---

## Table of contents

* [Why MapleClear](#why-mapleclear)
* [Features](#features)
* [Screenshots and Demo](#screenshots-and-demo)
* [Architecture](#architecture)
* [Local Setup](#local-setup)
* [Usage](#usage)
* [Fine-tuning](#fine-tuning)
* [Data Sources and Attribution](#data-sources-and-attribution)
* [Safety and Ethics](#safety-and-ethics)
* [Limitations](#limitations)
* [Repo Structure](#repo-structure)
* [Development](#development)
* [License](#license)
* [Devpost Notes](#devpost-notes)

---

## Why MapleClear

Government information is essential, but it can be dense and full of jargon or acronyms. MapleClear simplifies and translates Canada.ca content so newcomers and ESL speakers can act with confidence. The tool is local-first, so it still works with limited connectivity and keeps private data on the device. Judges can run it in minutes and verify that it meets the “For Humanity” and “Local Agent” goals.

---

## Features

* **Simplify to plain language**

  * Select text or simplify the whole page.
  * Targets grade 6 to 8 readability, shows a short rationale list for each change.
  * Never hides the original. A split view compares original and simplified results.

* **Translate**

  * One click toggle.
  * Preserves official names and acronyms through a built-in terminology cache.
  * Never hides the original. A split view compares original and simplified results.

* **Explain acronyms and jargon**

  * Hover to expand acronyms. See a short definition and an optional link to a public record.

* **Local-first**

  * Runs against a local `gpt-oss` model by default. No internet required.
  * Optional “cloud assist” toggle for users who want faster or larger models.

* **Accessibility**

  * Keyboard navigation, readable fonts, screen reader friendly ARIA in the panel.
  * Prints a clean, simplified version on demand.

* **Indigenous language path (opt-in, experimental)**

  * Start with dictionary-powered glosses and phrase-level helpers.
  * Translation features are built using public Indigenous community resources
  * All features are clearly labeled experimental.
  * English remains side by side.

---

## Screenshots and Demo

[MapleClear Demo](https://youtu.be/l6j8aqHNVWY)

![gallery](https://github.com/user-attachments/assets/fa8e979a-421c-4bac-96e7-af1e38d1363d)
![gallery-2](https://github.com/user-attachments/assets/665410f9-6c36-470c-84c4-860df146bf6d)

---

## Architecture

```
+-------------------+          HTTP (localhost)          +------------------------------+
|  Browser Extension|  <--------------------------------> |  Local Inference Daemon      |
|  (Manifest V3)    |                                      |  (FastAPI + vLLM/llama.cpp)  |
+---------+---------+                                      +-----+------------------------+
          |                                                      |
   Content script injects                                        | Loads an open-weight gpt-oss model
   UI panel, extracts text                                       | Applies prompts and JSON schema
   and selection ranges                                          | Uses terminology cache (SQLite/JSON)
          |                                                      |
          v                                                      v
    Page DOM, ARIA safe                        Prompted outputs: { plain, rationale[], cautions[] }
```

* **Extension**: MV3 service worker, content script, React panel.
* **Daemon**: FastAPI on `http://127.0.0.1:11434` by default. Pluggable backends:
  * **Option A**: `llama.cpp` with GGUF quantized `gpt-oss-20B` on CPU or Metal.
  * **Option B**: `vLLM` with `gpt-oss-20B` or `gpt-oss-120B` on a local GPU.
* **Terminology**: local SQLite cache of public terms and acronyms. The extension queries this first, then falls back to optional online lookups if enabled.

---

## Local Setup

### Prerequisites

* Node 20+, pnpm or npm
* Python 3.9
* One of:

  * `llama.cpp` build with CPU or Metal
  * `vLLM` with a compatible GPU and CUDA or ROCm
* Model weights for `gpt-oss-20B` (quantized or full precision), stored locally

### 1) Clone and install

```bash
git clone https://github.com/<your-username>/mapleclear.git
cd mapleclear
pnpm install   # or npm install
python -m venv .venv && source .venv/bin/activate
pip install -r server/requirements.txt
```

### 2) Download or point to a local model

Place weights in `~/.mapleclear/models/gpt-oss-20b/` or set `MAPLECLEAR_MODEL_PATH`.

Example with `llama.cpp` GGUF:

```bash
mkdir -p ~/.mapleclear/models/gpt-oss-20b
# Copy or download your GGUF file into the folder above
export MAPLECLEAR_MODEL_PATH="$HOME/.mapleclear/models/gpt-oss-20b/gpt-oss-20b-q5_k_m.gguf"
```

### 3) Start the local daemon

**llama.cpp backend**

```bash
# One-time build if needed
make -C server/backends/llama.cpp

# Run the FastAPI server that wraps llama.cpp
uvicorn server.app:app --host 127.0.0.1 --port 11434 --reload
```

**vLLM backend**

```bash
export MAPLECLEAR_BACKEND=vllm
export MAPLECLEAR_MODEL_ID="gpt-oss-20b-fp16"
python server/backends/vllm_runner.py --port 11434
```

You should see: `MapleClear server ready on http://127.0.0.1:11434`.

### 4) Build and load the extension

```bash
pnpm build        # or npm run build
```

* Chrome: open `chrome://extensions`, enable Developer mode, **Load unpacked**, choose `extension/dist`.
* Firefox: use `about:debugging` and **Load Temporary Add-on**.

### 5) Seed the terminology cache (optional but recommended)

```bash
python tools/seed_terms.py --out data/terms.sqlite
```

### One-click demo

```bash
make demo
# launches the daemon, builds the extension, opens a local demo page, and preloads sample terms
```

---

## Usage

* Click the MapleClear icon to open the panel.
* **Simplify selection** rewrites only highlighted text. **Simplify page** rewrites the full main content region.
* **Translate** toggles English and French. You can copy or print the result.
* **Explain** appears on hover for acronyms and flagged jargon.
* **System** shows model info, local mode, and the path to the terminology cache.

Settings of note:

* **Local only**: blocks all network calls from the extension.
* **Cloud assist**: allowed only if the user enables it. Clear banner displays the mode.
* **Readability target**: choose grade 6, 7, or 8.
* **Experimental Indigenous features**: off by default, per language toggle with info links.

---

## Fine-tuning

Two small adapters are provided using PEFT LoRA:

1. **Plain-Language Style Adapter**

   * Trains on public, plain-language pairs you generate from government communication guidelines and your synthetic rewrites.
   * Target: shorter sentences, active voice, front-loaded key information, minimum jargon.

2. **Inuktitut MT Adapter (experimental)**

   * Phrase-level translation fine-tune using permitted parallel data, with strict data cards and evaluation.
   * Post-edits with the base model to keep clarity. Always labeled experimental. English side by side remains visible.

**Train locally**

```bash
cd finetune
python train_plain_lora.py --base gpt-oss-20b --output runs/plain_lora
python train_inuktitut_lora.py --base gpt-oss-20b --output runs/iu_lora
```

**Use at runtime**

```bash
export MAPLECLEAR_ADAPTERS="runs/plain_lora"
# optional: add iu adapter when the user enables the feature
```

---

## Data Sources and Attribution

* Public terminology and acronym lists, where permitted, cached locally for offline use.
* Plain-language guidance summarized into machine-readable rules inside the prompts.
* Indigenous language resources are referenced only with explicit permission and clear attribution in `/data-cards/`. Community ownership is respected. The extension links to community portals where appropriate.

Add your specific sources and licenses to:

* `/data-cards/terms.md`
* `/data-cards/plain-style.md`
* `/data-cards/indigenous.md`

---

## Safety and Ethics

* MapleClear provides assistance, not official translation or legal advice.
* Local mode is on by default, which keeps content on the device.
* Indigenous language features are opt-in, clearly labeled experimental, and built with community guidance. Features will not ship for a language unless redistribution and use are permitted by the community or rights holder.
* The original text is always available side by side.

---

## Limitations

* Quality depends on the local model size and quantization.
* French terminology coverage is strong for federal vocabulary, but gaps can appear for niche programs. The cache helps, but it is not complete.
* Other language terminology is more likely to have gaps for federal vocabulary and niche programs. 
* Indigenous language support is early and should be used as a learning aid, not a substitute for community-provided translations.
* Complex tables and PDFs embedded as images are harder to simplify accurately.

---

## Repo Structure

```
mapleclear/
├── LICENSE                    # Apache 2.0 license
├── README.md                  # This file
├── Makefile                   # Build and demo commands
├── package.json               # Root package configuration
├── .gitignore                 # Git ignore patterns
│
├── extension/                 # Browser extension (MV3)
│   ├── package.json           # Extension dependencies
│   ├── vite.config.ts         # Build configuration
│   ├── tsconfig.json          # TypeScript configuration
│   ├── src/
│   │   ├── manifest.json      # Extension manifest
│   │   ├── background.ts      # Service worker
│   │   ├── content-script.ts  # Page injection script
│   │   ├── popup.html         # Extension popup
│   │   ├── popup.ts           # Popup functionality
│   │   ├── panel.html         # Injected panel template
│   │   └── content-styles.css # Panel styling
│   └── dist/                  # Built extension (generated)
│
├── server/                    # Local inference daemon
│   ├── requirements.txt       # Python dependencies
│   ├── __init__.py            # Package init
│   ├── app.py                 # FastAPI main application
│   ├── prompts/
│   │   ├── __init__.py
│   │   └── schema.py          # Request/response models
│   └── backends/
│       ├── __init__.py
│       ├── base.py            # Abstract backend interface
│       ├── llama_cpp.py       # llama.cpp implementation
│       ├── vllm_backend.py    # vLLM implementation
│       ├── llama.cpp/         # llama.cpp build directory
│       └── vllm/              # vLLM configuration
│
├── data/                      # Local data storage
│   └── terms.sqlite           # Terminology cache (generated)
│
├── data-cards/                # Data source documentation
│   ├── terms.md               # Terminology attribution
│   ├── plain-style.md         # Style guide sources
│   └── indigenous.md          # Indigenous language ethics
│
├── finetune/                  # Model fine-tuning scripts
│   ├── train_plain_lora.py    # Plain language adapter
│   └── train_inuktitut_lora.py # Indigenous language adapter
│
├── tools/                     # Development utilities
│   ├── seed_terms.py          # Database population
│   └── readability.py         # Text analysis tools
│
├── demo/                      # Demo and testing
│   ├── pages/                 # Sample government pages
│   │   └── canada-benefits.html
│   └── script.sh              # Demo automation
│
└── tests/                     # Test suite
    └── test_basic.py          # Basic functionality tests
```

### Key Components

- **Extension**: Manifest V3 browser extension with React UI
- **Server**: FastAPI daemon with pluggable AI backends
- **Data**: SQLite terminology cache for offline operation
- **Fine-tuning**: LoRA adapters for specialized models
- **Tools**: Database seeding and text analysis utilities
- **Demo**: Sample content for testing and demonstration

---

## Development

**Run tests**

```bash
pnpm test
pytest
```

**Lint and typecheck**

```bash
pnpm lint
pnpm typecheck
ruff check server
mypy server
```

**Prompts and schema**

* All rewrite calls return JSON:

```json
{
  "plain": "text...",
  "rationale": ["short bullet on change 1", "change 2"],
  "cautions": ["any warning or uncertainty to show the user"]
}
```

**Contributing**

* Please open an issue to discuss major changes.
* For Indigenous language features, include confirmation of permission for any resource.

---

## License

**Apache 2.0**. See: [LICENSE](LICENSE)

---

## Devpost Notes

* **Submitted to [OpenAI Open Model Hackathon](https://openai.devpost.com)**
* **Categories chosen**: For Humanity (primary), Best Local Agent and Most Useful Fine-Tune (secondary).
* **Model use**: open-weight `gpt-oss` models run locally by default.
* **Ethics**: MapleClear assists reading and understanding, it is **not an official translation or a replacement for legal advice.**
