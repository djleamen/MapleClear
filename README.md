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
./setup.sh
```

### 2) Build and load the extension

```bash
cd server
npm run build
```

* Chrome: open `chrome://extensions`, enable Developer mode, **Load unpacked**, choose `extension/dist`.
* Firefox: use `about:debugging` and **Load Temporary Add-on**.

### 3) Start the local daemon

```bash
make dev-server
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

### Key Components

- **Extension**: Manifest V3 browser extension with React UI
- **Server**: FastAPI daemon with pluggable AI backends
- **Data**: SQLite terminology cache for offline operation
- **Fine-tuning**: LoRA adapters for specialized models
- **Tools**: Database seeding and text analysis utilities
- **Demo**: Sample content for testing and demonstration

---

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
