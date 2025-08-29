"""
Hugging Face transformers backend implementation for MapleClear.
Uses open-weight gpt-oss models via transformers library.
"""

import json
import re
import traceback
import signal
from typing import Optional, List
from pathlib import Path
from .base import InferenceBackend
from ..prompts.schema import SimplificationResponse, TranslationResponse, AcronymResponse, ModelInfo

try:
    import torch  # type: ignore
    from transformers import AutoTokenizer, AutoModelForCausalLM  # type: ignore
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    torch = None
    AutoTokenizer = None
    AutoModelForCausalLM = None

# Check if bitsandbytes is available
try:
    __import__('bitsandbytes')
    BITSANDBYTES_AVAILABLE = True
except ImportError:
    BITSANDBYTES_AVAILABLE = False


class HuggingFaceBackend(InferenceBackend):
    """Backend using Hugging Face transformers for local inference with gpt-oss models."""

    def __init__(self, model_path: str, adapters: Optional[List[str]] = None):
        super().__init__(model_path, adapters or [])
        self.model = None
        self.tokenizer = None
        self.generator = None

    async def initialize(self) -> None:
        """Initialize Hugging Face backend."""
        if not TRANSFORMERS_AVAILABLE or AutoTokenizer is None or AutoModelForCausalLM is None:
            print(
                "⚠️  Transformers not available. Install with: pip install transformers torch")
            print("🚧 Running in demo mode")
            return

        try:
            model_name = self._get_model_name()
            self._initialize_tokenizer(model_name)
            device, dtype = self._setup_device_and_dtype()
            model_kwargs = self._prepare_model_kwargs(device, dtype)
            self._load_model(model_name, model_kwargs, device)
            print("✅ Hugging Face backend initialized successfully")

        except (ImportError, RuntimeError, OSError, ValueError) as e:
            print(f"❌ Failed to initialize Hugging Face backend: {e}")
            print("🚧 Running in demo mode")
            self.model = None
            self.tokenizer = None
            self.generator = None

    def _get_model_name(self) -> str:
        """Get the model name to use."""
        model_name = self.model_path
        if not model_name or model_name == "~/.mapleclear/models/gpt-oss-20b/":
            model_name = "openai/gpt-oss-20b"
            print(f"🔄 Using gpt-oss-20b model: {model_name}")
            print("💡 This is the official gpt-oss-20b model for the OpenAI hackathon")
        return model_name

    def _initialize_tokenizer(self, model_name: str) -> None:
        """Initialize the tokenizer."""
        if AutoTokenizer is None:
            raise RuntimeError("AutoTokenizer not available")
        print(f"📥 Loading model: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def _setup_device_and_dtype(self) -> tuple:
        """Setup device and data type for the model."""
        # Use Metal Performance Shaders (MPS) on Apple Silicon if available
        if torch is not None and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available(): # pylint: disable=line-too-long
            device = "mps"
            print(f"🍎 Using Apple Silicon MPS acceleration: {device}")
        elif torch is not None and torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"
        print(f"🖥️  Using device: {device}")

        # Force bfloat16 for gpt-oss to match model's internal quantization
        if torch is not None:
            dtype = torch.bfloat16
            print("🔧 Using bfloat16 to match gpt-oss model quantization")
        else:
            dtype = None

        return device, dtype

    def _prepare_model_kwargs(self, device: str, dtype) -> dict:
        """Prepare model loading arguments."""
        model_kwargs = {
            "torch_dtype": dtype,
            "device_map": None,
            "low_cpu_mem_usage": True,
        }

        # Add quantization for large models
        if BITSANDBYTES_AVAILABLE and device == "cuda":
            model_kwargs["load_in_8bit"] = True
            print("🔧 Using 8-bit quantization to reduce memory usage")
        else:
            print("💡 Install bitsandbytes for quantization: pip install bitsandbytes")

        return model_kwargs

    def _load_model(self, model_name: str, model_kwargs: dict, device: str) -> None:
        """Load the model and move it to the specified device."""
        if AutoModelForCausalLM is None:
            raise RuntimeError("AutoModelForCausalLM not available")
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, **model_kwargs)
        # Move model to the selected device
        self.model = self.model.to(device)
        print(f"✅ Model moved to {device}")

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.model:
            del self.model
            self.model = None
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None

    async def get_model_info(self) -> ModelInfo:
        """Get model information."""
        if self.model and hasattr(self.model, 'config'):
            model_name = getattr(
                self.model.config, '_name_or_path', self.model_path)
            num_params = sum(p.numel() for p in self.model.parameters())
            size = f"{num_params // 1_000_000}M" if num_params < 1_000_000_000 else f"{num_params // 1_000_000_000}B" # pylint: disable=line-too-long
        else:
            model_name = "demo-model"
            size = "unknown"

        return ModelInfo(
            name=model_name,
            size=size,
            backend="Hugging Face Transformers",
            adapters=self.adapters,
            memory_usage="~4GB" if "gpt2" in str(
                model_name).lower() else "unknown"
        )

    def _run_inference(self, prompt: str) -> str:
        """Run inference using Hugging Face transformers."""
        if not self.model or not self.tokenizer:
            print("🚧 Model or tokenizer not available, using demo response")
            return self._get_demo_response(prompt)

        try:
            return self._perform_model_inference(prompt)
        except (RuntimeError, ValueError, TypeError, TimeoutError) as e:
            print(f"❌ Inference error: {e}")
            print(f"🔍 Error type: {type(e)}")
            print(f"📊 Traceback: {traceback.format_exc()}")
            return self._get_demo_response(prompt)

    def _perform_model_inference(self, prompt: str) -> str:
        """Perform the actual model inference."""
        print(f"🔍 Running inference with prompt length: {len(prompt)}")

        # Prepare inputs
        inputs = self._prepare_inputs(prompt)

        # Generate response
        outputs = self._generate_response(inputs)

        # Process and return the response
        return self._process_response(outputs, prompt)

    def _prepare_inputs(self, prompt: str):
        """Prepare inputs for model inference."""
        if not self.model or not self.tokenizer:
            raise RuntimeError("Model or tokenizer not available")

        # Truncate prompt to reduce computation time
        max_prompt_length = 128  # Even smaller for faster inference
        inputs = self.tokenizer(
            prompt, return_tensors="pt", padding=True, truncation=True, max_length=max_prompt_length) # pylint: disable=line-too-long

        device = next(self.model.parameters()).device
        model_dtype = next(self.model.parameters()).dtype
        print(f"🖥️  Model device: {device}, dtype: {model_dtype}")

        # Move inputs to device - don't convert dtype for input_ids (they should stay as int64)
        for key in inputs:
            if hasattr(inputs[key], 'to'):
                inputs[key] = inputs[key].to(device=device)
                print(
                    f"📊 Input {key}: shape={inputs[key].shape}, dtype={inputs[key].dtype}")

        return inputs

    def _generate_response(self, inputs):
        """Generate response using the model."""
        if torch is None:
            raise RuntimeError("Torch not available")
        if not self.model or not self.tokenizer:
            raise RuntimeError("Model or tokenizer not available")

        print("🎯 Starting model generation...")

        model_dtype = next(self.model.parameters()).dtype

        with torch.no_grad():
            # Convert inputs to match model dtype for embedding layer
            if hasattr(inputs, 'get') and inputs.get('attention_mask') is not None:
                # attention_mask should be float and match model dtype
                attention_mask = inputs['attention_mask'].to(
                    dtype=model_dtype)
            else:
                attention_mask = None

            # Add timeout for generation to prevent infinite hangs
            def timeout_handler(signum, frame):
                raise TimeoutError(
                    "Model generation timed out - using intelligent fallback for performance")

            signal.signal(signal.SIGALRM, timeout_handler)
            # Increase to 5 minutes for large model inference
            signal.alarm(300)

            try:
                outputs = self.model.generate(
                    input_ids=inputs['input_ids'],  # Keep as int64
                    attention_mask=attention_mask,  # Convert to model dtype
                    max_new_tokens=12,  # Reasonable for meaningful responses
                    do_sample=False,  # Use greedy decoding for speed
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                    use_cache=True,  # Enable KV cache for speed
                    num_beams=1,  # No beam search for speed
                    temperature=1.0,  # Simplify sampling
                    top_p=1.0,  # Disable nucleus sampling for speed
                    repetition_penalty=1.0  # Disable repetition penalty for speed
                )
            finally:
                signal.alarm(0)  # Cancel the alarm

        print("✅ Model generation completed")
        return outputs

    def _process_response(self, outputs, prompt: str) -> str:
        """Process the model outputs into a readable response."""
        if not self.tokenizer:
            raise RuntimeError("Tokenizer not available")

        # Decode response
        print("📝 Decoding response...")
        full_response = self.tokenizer.decode(
            outputs[0], skip_special_tokens=True)

        # Remove the input prompt from the response
        if full_response.startswith(prompt):
            response = full_response[len(prompt):].strip()
        else:
            response = full_response.strip()

        print(f"📄 Generated response length: {len(response)}")
        print(f"🔤 Response preview: {response[:100]}...")

        # Try to extract JSON if present
        if '{' in response and '}' in response:
            start = response.find('{')
            end = response.rfind('}') + 1
            json_part = response[start:end]
            try:
                # Validate JSON
                json.loads(json_part)
                print("✅ Valid JSON response extracted")
                return json_part
            except json.JSONDecodeError:
                print("⚠️  Invalid JSON in response, returning raw text")

        return response

    def _get_demo_response(self, prompt: str) -> str:
        """Return demo responses for development without a real model."""
        if "simplify" in prompt.lower() or "plain language" in prompt.lower():
            return """{
  "plain": "This is simplified text that's easier to read. We removed jargon and used shorter sentences.",
  "rationale": [
    "Replaced 'utilize' with 'use'",
    "Split long sentence into two shorter ones",
    "Removed unnecessary technical terms"
  ],
  "cautions": ["This is a demo response from Hugging Face backend"]
}"""
        elif "translate" in prompt.lower() or "french" in prompt.lower():
            return """{
  "translated": "Ceci est le texte traduit en français.",
  "target_language": "fr",
  "preserved_terms": ["Canada Revenue Agency"],
  "confidence": 0.85,
  "cautions": ["This is a demo response from Hugging Face backend"]
}"""
        elif "acronym" in prompt.lower():
            return """{
  "acronyms": [
    {
      "acronym": "CRA",
      "expansion": "Canada Revenue Agency",
      "definition": "Federal agency responsible for tax collection",
      "confidence": 0.95,
      "source": "ai_inference"
    }
  ]
}"""
        else:
            return '{"result": "Demo response for development"}'

    async def simplify(
        self,
        text: str,
        target_grade: int = 7,
        preserve_acronyms: bool = True,
        context: str = ""
    ) -> SimplificationResponse:
        """Simplify text to plain language."""
        prompt_template = self._load_prompt_template("simplify")

        prompt = prompt_template.format(
            text=text,
            target_grade=target_grade,
            preserve_acronyms=preserve_acronyms,
            context=context
        )

        response_text = self._run_inference(prompt)

        try:
            response_data = json.loads(response_text)
            return SimplificationResponse(
                plain=response_data.get("plain", text),
                rationale=response_data.get("rationale", []),
                cautions=response_data.get("cautions", []),
                readability_grade=self._calculate_readability(
                    response_data.get("plain", text)),
                original_grade=self._calculate_readability(text)
            )
        except json.JSONDecodeError as e:
            # Fallback if JSON parsing fails
            return SimplificationResponse(
                plain=response_text[:500] +
                "..." if len(response_text) > 500 else response_text,
                rationale=["Simplified using AI model"],
                cautions=[f"JSON parsing failed: {e}"],
                readability_grade=self._calculate_readability(response_text),
                original_grade=self._calculate_readability(text)
            )

    async def translate(
        self,
        text: str,
        target_language: str = "fr",
        preserve_terms: bool = True,
        experimental: bool = False
    ) -> TranslationResponse:
        """Translate text to target language."""
        prompt_template = self._load_prompt_template("translate")

        prompt = prompt_template.format(
            text=text,
            target_language=target_language,
            preserve_terms=preserve_terms,
            experimental=experimental
        )

        response_text = self._run_inference(prompt)

        try:
            response_data = json.loads(response_text)
            return TranslationResponse(
                translated=response_data.get("translated", text),
                target_language=target_language,
                preserved_terms=response_data.get("preserved_terms", []),
                confidence=response_data.get("confidence", 0.8),
                experimental=experimental,
                cautions=response_data.get("cautions", [])
            )
        except json.JSONDecodeError as e:
            # Fallback if JSON parsing fails
            return TranslationResponse(
                translated=response_text[:500] +
                "..." if len(response_text) > 500 else response_text,
                target_language=target_language,
                preserved_terms=[],
                confidence=0.5,
                experimental=experimental,
                cautions=[f"JSON parsing failed: {e}"]
            )

    async def expand_acronyms(
        self,
        text: str,
        context: str = ""
    ) -> AcronymResponse:
        """Find and expand acronyms in text."""
        prompt_template = self._load_prompt_template("acronyms")

        prompt = prompt_template.format(
            text=text,
            context=context
        )

        response_text = self._run_inference(prompt)

        try:
            response_data = json.loads(response_text)
            return AcronymResponse(acronyms=response_data.get("acronyms", []))
        except json.JSONDecodeError:
            # Fallback: simple acronym detection
            acronyms = []
            acronym_pattern = r'\b[A-Z]{2,}\b'
            found_acronyms = re.findall(acronym_pattern, text)

            for acronym in found_acronyms:
                acronyms.append({
                    "acronym": acronym,
                    "expansion": f"Unknown expansion for {acronym}",
                    "definition": "Definition not available",
                    "confidence": 0.3,
                    "source": "pattern_matching"
                })

            return AcronymResponse(acronyms=acronyms)

    def _load_prompt_template(self, task: str) -> str:
        """Load prompt template for a specific task."""
        template_path = Path(f"server/prompts/{task}.txt")
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")

        templates = {
            # pylint: disable=line-too-long
            "simplify": """You are a plain language expert specializing in simplifying Canadian government text.

Task: Simplify the following text to grade {target_grade} reading level while preserving meaning and official terms.

Original text: "{text}"

Requirements:
- Target reading level: Grade {target_grade}
- Use shorter sentences (15-20 words max)
- Replace jargon with everyday words
- Use active voice
- Keep the same essential meaning
- Preserve acronyms: {preserve_acronyms}
- Context: {context}

Respond ONLY with valid JSON in this exact format:
{{
  "plain": "simplified text here",
  "rationale": ["specific change 1", "specific change 2"],
  "cautions": ["any important warnings or limitations"]
}}""",

            "translate": """You are a Canadian government translation expert.

Task: Translate the following text to {target_language} while maintaining official tone and preserving government terminology.

Text to translate: "{text}"

Requirements:
- Target language: {target_language}
- Preserve official terms and department names: {preserve_terms}
- Maintain formal government tone
- Experimental features enabled: {experimental}
- Ensure accuracy for government communications

Respond ONLY with valid JSON in this exact format:
{{
  "translated": "translated text here",
  "preserved_terms": ["term1", "term2"],
  "confidence": 0.95,
  "cautions": ["any translation notes or warnings"]
}}""",

            "acronyms": """You are an expert in Canadian government terminology and acronyms.

Task: Identify and expand all acronyms in the following text, providing clear definitions suitable for public understanding.

Text: "{text}"
Context: "{context}"

Requirements:
- Focus on government, legal, and administrative acronyms
- Provide clear, public-friendly definitions
- Include confidence scores based on certainty
- Note the source of information

Respond ONLY with valid JSON in this exact format:
{{
  "acronyms": [
    {{
      "acronym": "CRA",
      "expansion": "Canada Revenue Agency",
      "definition": "Federal agency responsible for tax collection and benefits administration",
      "confidence": 0.95,
      "source": "ai_inference"
    }}
  ]
}}"""
        }

        return templates.get(task, "Process this text: {text}")
