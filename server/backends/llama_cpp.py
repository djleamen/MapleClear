"""
llama.cpp backend implementation for MapleClear.
This is just a sample implementation and should not be used in production
"""

import json
import subprocess
import asyncio
from typing import Optional, List
from pathlib import Path

from .base import InferenceBackend
from ..prompts.schema import SimplificationResponse, TranslationResponse, AcronymResponse, ModelInfo


class LlamaCppBackend(InferenceBackend):
    """Backend using llama.cpp for local inference."""

    def __init__(self, model_path: str, adapters: Optional[List[str]] = None):
        super().__init__(model_path, adapters)
        self.llama_cpp_path = None
        self.model_loaded = False

    async def initialize(self) -> None:
        """Initialize llama.cpp backend."""
        cpp_path = Path("server/backends/llama.cpp/main")
        if not cpp_path.exists():
            try:
                process = await asyncio.create_subprocess_exec(
                    "make", "-C", "server/backends/llama.cpp",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                _, stderr = await process.communicate()
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(
                        process.returncode or 1, ["make"], stderr)
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to build llama.cpp: {e}")
                raise

        self.llama_cpp_path = cpp_path

        model_path = Path(self.model_path).expanduser()
        if not model_path.exists():
            print(f"Model file not found: {model_path}")
            print("Please download a model or set MAPLECLEAR_MODEL_PATH")
            # For demo purposes: to be removed
            print("Running in demo mode without real model...")

        self.model_loaded = True
        print("✅ llama.cpp backend initialized")

    async def cleanup(self) -> None:
        """Clean up resources."""
        self.model_loaded = False

    async def get_model_info(self) -> ModelInfo:
        """Get model information."""
        model_path = Path(self.model_path).expanduser()
        return ModelInfo(
            name=model_path.name if model_path.exists() else "demo-model",
            size="20B" if "20b" in str(model_path).lower() else "unknown",
            quantization="Q5_K_M" if "q5_k_m" in str(
                model_path).lower() else None,
            backend="llama.cpp",
            adapters=self.adapters,
            memory_usage="~12GB" if "20b" in str(
                model_path).lower() else "unknown"
        )

    async def _run_inference(self, prompt: str, max_tokens: int = 512) -> str:
        """Run inference using llama.cpp."""
        if not self.model_loaded:
            raise RuntimeError("Model not loaded")

        model_path = Path(self.model_path).expanduser()
        if not model_path.exists():
            return self._get_demo_response(prompt)

        try:
            cmd = [
                str(self.llama_cpp_path),
                "-m", str(model_path),
                "-p", prompt,
                "-n", str(max_tokens),
                "--temp", "0.7",
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=60
                )
            except asyncio.TimeoutError as exc:
                process.kill()
                await process.wait()
                raise RuntimeError("Inference timeout") from exc

            if process.returncode != 0:
                raise RuntimeError(f"llama.cpp failed: {stderr.decode()}")
            return stdout.decode().strip()

        except Exception as e:
            raise RuntimeError(f"Inference failed: {e}") from e

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
  "cautions": ["This is a demo response"]
}"""
        if "translate" in prompt.lower() or "french" in prompt.lower():
            return """{
  "translated": "Ceci est le texte traduit en français.",
  "target_language": "French",
  "preserved_terms": ["Canada Revenue Agency"],
  "confidence": 0.85,
  "cautions": ["This is a demo response"]
}"""
        if "acronym" in prompt.lower():
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

        response_text = await self._run_inference(prompt)

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
        target_language: str = "French",
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

        response_text = await self._run_inference(prompt)

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

        response_text = await self._run_inference(prompt)

        try:
            response_data = json.loads(response_text)
            return AcronymResponse(acronyms=response_data["acronyms"])
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse response: {e}") from e

    def _load_prompt_template(self, task: str) -> str:
        """Load prompt template for a specific task."""
        template_path = Path(f"server/prompts/{task}.txt")
        if template_path.exists():
            return template_path.read_text(encoding='utf-8')

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
