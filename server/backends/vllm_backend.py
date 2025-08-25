"""
vLLM backend implementation for MapleClear.
"""

import json
from typing import Optional, List
from pathlib import Path

try:
    from vllm import LLM, SamplingParams # type: ignore # pylint: disable=import-error
    VLLM_AVAILABLE = True
except ImportError:
    VLLM_AVAILABLE = False
    LLM = None
    SamplingParams = None

from .base import InferenceBackend
from ..prompts.schema import SimplificationResponse, TranslationResponse, AcronymResponse, ModelInfo

DEMO_MODE_MESSAGE = "🚧 Running in demo mode"


class VLLMBackend(InferenceBackend):
    """Backend using vLLM for local inference."""

    def __init__(self, model_path: str, adapters: Optional[List[str]] = None):
        super().__init__(model_path, adapters or [])
        self.llm = None
        self.sampling_params = None

    async def initialize(self) -> None:
        """Initialize vLLM backend."""
        if not VLLM_AVAILABLE:
            print("⚠️  vLLM not available. Install with: pip install vllm")
            print(DEMO_MODE_MESSAGE)
            return

        try:
            if SamplingParams is None:
                print("⚠️  vLLM components not available")
                print(DEMO_MODE_MESSAGE)
                return

            self.sampling_params = SamplingParams(
                temperature=0.7,
                top_p=0.9,
                max_tokens=512,
                stop=["</s>", "<|endoftext|>"]
            )
            model_path = Path(self.model_path).expanduser()
            if not model_path.exists():
                print(f"⚠️  Model not found: {model_path}")
                print(DEMO_MODE_MESSAGE)
                return

            if LLM is None:
                print("⚠️  vLLM LLM class not available")
                print(DEMO_MODE_MESSAGE)
                return

            self.llm = LLM(
                model=str(model_path),
                tensor_parallel_size=1,
                gpu_memory_utilization=0.9
            )
        except ImportError:
            print("❌ vLLM not installed. Install with: pip install vllm")
            print(DEMO_MODE_MESSAGE)
        except (RuntimeError, OSError, ValueError) as e:
            print(f"❌ Failed to initialize vLLM: {e}")
            print("🚧 Running in demo mode")

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.llm:
            del self.llm
            self.llm = None

    async def get_model_info(self) -> ModelInfo:
        """Get model information."""
        model_path = Path(self.model_path).expanduser()
        return ModelInfo(
            name=model_path.name if model_path.exists() else "demo-model",
            size="20B" if "20b" in str(model_path).lower() else "unknown",
            backend="vLLM",
            adapters=self.adapters,
            memory_usage="~16GB" if "20b" in str(
                model_path).lower() else "unknown"
        )

    def _run_inference(self, prompt: str) -> str:
        """Run inference using vLLM."""
        if not self.llm:
            # Return demo response for development
            return self._get_demo_response(prompt)

        try:
            outputs = self.llm.generate([prompt], self.sampling_params)
            return outputs[0].outputs[0].text.strip()
        except Exception as e:
            raise RuntimeError(f"vLLM inference failed: {e}") from e

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
  "cautions": ["This is a demo response from vLLM backend"]
}"""
        elif "translate" in prompt.lower() or "french" in prompt.lower():
            return """{
  "translated": "Ceci est le texte traduit en français.",
  "target_language": "fr",
  "preserved_terms": ["Canada Revenue Agency"],
  "confidence": 0.85,
  "cautions": ["This is a demo response from vLLM backend"]
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

        # For demo mode, return immediately without trying to run inference
        response_text = self._get_demo_response(prompt)

        try:
            response_data = json.loads(response_text)
            return SimplificationResponse(
                plain=response_data["plain"],
                rationale=response_data.get("rationale", []),
                cautions=response_data.get("cautions", []),
                readability_grade=self._calculate_readability(
                    response_data["plain"]),
                original_grade=self._calculate_readability(text)
            )
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse response: {e}") from e

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

        # For demo mode, return immediately without trying to run inference  
        response_text = self._get_demo_response(prompt)

        try:
            response_data = json.loads(response_text)
            return TranslationResponse(
                translated=response_data["translated"],
                target_language=target_language,
                preserved_terms=response_data.get("preserved_terms", []),
                confidence=response_data.get("confidence", 0.8),
                experimental=experimental,
                cautions=response_data.get("cautions", [])
            )
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse response: {e}") from e

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

        # For demo mode, return immediately without trying to run inference
        response_text = self._get_demo_response(prompt)

        try:
            response_data = json.loads(response_text)
            return AcronymResponse(acronyms=response_data["acronyms"])
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse response: {e}") from e

    def _load_prompt_template(self, task: str) -> str:
        """Load prompt template for a specific task."""
        template_path = Path(f"server/prompts/{task}.txt")
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")

        templates = {
            "simplify": """You are a plain language expert. 
            Simplify the following text to grade {target_grade} reading level.

Original text: {text}

Instructions:
- Use shorter sentences
- Replace jargon with simple words
- Keep the same meaning
- Preserve acronyms if {preserve_acronyms}
- Context: {context}

Return JSON format:
{{
  "plain": "simplified text here",
  "rationale": ["change 1", "change 2"],
  "cautions": ["any warnings"]
}}""",

            "translate": """Translate the following text to {target_language}.

Text: {text}

Instructions:
- Preserve official terms if {preserve_terms}
- Maintain formal government tone
- Experimental features: {experimental}

Return JSON format:
{{
  "translated": "translated text",
  "preserved_terms": ["term1", "term2"],
  "confidence": 0.85,
  "cautions": ["warnings"]
}}""",

            "acronyms": """Find and expand acronyms in the following text.

Text: {text}
Context: {context}

Return JSON format:
{{
  "acronyms": [
    {{
      "acronym": "CRA",
      "expansion": "Canada Revenue Agency",
      "definition": "Federal tax agency",
      "confidence": 0.95,
      "source": "ai_inference"
    }}
  ]
}}"""
        }

        return templates.get(task, "Process this text: {text}")
