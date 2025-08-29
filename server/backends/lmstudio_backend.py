"""
LM Studio backend implementation for MapleClear.
Communicates with LM Studio's local API server for optimized Apple Silicon inference.
"""

import json
import re
import asyncio
from typing import Optional, List
from pathlib import Path
from .base import InferenceBackend
from ..prompts.schema import SimplificationResponse, TranslationResponse, AcronymResponse, ModelInfo

try:
    import aiohttp  # type: ignore
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None


class LMStudioError(Exception):
    """Custom exception for LM Studio backend errors."""


class LMStudioConnectionError(LMStudioError):
    """Exception for LM Studio connection issues."""


class LMStudioAPIError(LMStudioError):
    """Exception for LM Studio API errors."""


# Constants
DEMO_MODE_MESSAGE = "🚧 Running in demo mode"


class LMStudioBackend(InferenceBackend):
    """Backend using LM Studio's local API server for optimized inference."""

    def __init__(self, model_path: str = "", adapters: Optional[List[str]] = None):
        super().__init__(model_path, adapters or [])
        self.base_url = "http://localhost:1234/v1"  # LM Studio's default API endpoint
        self.model_name = None
        self.session = None

    async def initialize(self) -> None:
        """Initialize LM Studio backend."""
        if not AIOHTTP_AVAILABLE:
            print("⚠️  aiohttp not available. Install with: pip install aiohttp")
            print(DEMO_MODE_MESSAGE)
            return

        if aiohttp is None:
            print("⚠️  aiohttp not available. Install with: pip install aiohttp")
            print(DEMO_MODE_MESSAGE)
            return

        try:
            self.session = aiohttp.ClientSession()

            # Check if LM Studio server is running
            await self._check_server_status()

            # Get available models
            models = await self._get_available_models()

            # Try to find gpt-oss model
            gpt_oss_models = [
                m for m in models if 'gpt-oss' in m.lower() or 'gpt_oss' in m.lower()]

            if gpt_oss_models:
                self.model_name = gpt_oss_models[0]
                print(f"🎯 Found gpt-oss model in LM Studio: {self.model_name}")
                print(
                    "💡 This model should run much faster than raw transformers on Apple Silicon")
            elif models:
                self.model_name = models[0]
                print(f"🔄 Using available model: {self.model_name}")
                print(
                    "💡 Consider loading openai/gpt-oss-20b in LM Studio for hackathon compliance")
            else:
                print("⚠️  No models loaded in LM Studio")
                print("💡 Please load openai/gpt-oss-20b in LM Studio and restart")
                self.model_name = None

            print("✅ LM Studio backend initialized successfully")

        except LMStudioError as e:
            print(f"❌ Failed to initialize LM Studio backend: {e}")
            print("💡 Make sure LM Studio is running with a model loaded")
            print("💡 Download LM Studio from: https://lmstudio.ai/")
            print(DEMO_MODE_MESSAGE)
            self.model_name = None

    async def _check_server_status(self) -> None:
        """Check if LM Studio server is running."""
        if self.session is None:
            raise LMStudioConnectionError("Session not initialized")

        if aiohttp is None:
            raise LMStudioConnectionError("aiohttp not available")

        try:
            async with self.session.get(f"{self.base_url}/models", timeout=5) as response:
                if response.status == 200:
                    print("✅ LM Studio server detected and running")
                else:
                    raise LMStudioAPIError(
                        f"LM Studio server responded with status {response.status}")
        except asyncio.TimeoutError as e:
            raise LMStudioConnectionError(
                "LM Studio server not accessible: timeout") from e
        except aiohttp.ClientError as e:
            raise LMStudioConnectionError(
                f"LM Studio server not accessible: {e}") from e

    async def _get_available_models(self) -> List[str]:
        """Get list of models loaded in LM Studio."""
        if self.session is None:
            print("⚠️  Session not initialized")
            return []

        if aiohttp is None:
            print("⚠️  aiohttp not available")
            return []

        try:
            async with self.session.get(f"{self.base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [model['id'] for model in data.get('data', [])]
                    print(f"📋 Available models in LM Studio: {models}")
                    return models
                else:
                    print("⚠️  Could not retrieve model list from LM Studio")
                    return []
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"⚠️  Error getting models: {e}")
            return []

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.session:
            await self.session.close()
            self.session = None

    async def get_model_info(self) -> ModelInfo:
        """Get model information."""
        if self.model_name:
            # Extract approximate size from model name
            size = "unknown"
            if "20b" in self.model_name.lower():
                size = "20B"
            elif "7b" in self.model_name.lower():
                size = "7B"
            elif "13b" in self.model_name.lower():
                size = "13B"

            return ModelInfo(
                name=self.model_name,
                size=size,
                backend="LM Studio (Optimized for Apple Silicon)",
                adapters=self.adapters,
                memory_usage="Optimized by LM Studio"
            )
        else:
            return ModelInfo(
                name="demo-model",
                size="unknown",
                backend="LM Studio (Demo Mode)",
                adapters=self.adapters,
                memory_usage="N/A"
            )

    async def _run_inference(self, prompt: str) -> str:
        """Run inference using LM Studio's API."""
        if not self.model_name or not self.session:
            print("🚧 LM Studio model not available, using demo response")
            return self._get_demo_response(prompt)

        if aiohttp is None:
            print("🚧 aiohttp not available, using demo response")
            return self._get_demo_response(prompt)

        print(
            f"🔍 Running LM Studio inference with prompt length: {len(prompt)}")

        try:
            # Try completions endpoint first
            result = await self._try_completions_endpoint(prompt)
            if result:
                return result

            # Fallback to chat completions endpoint
            return await self._try_chat_completions_endpoint(prompt)

        except asyncio.TimeoutError:
            print("⏰ LM Studio request timed out, using demo response")
            return self._get_demo_response(prompt)
        except (aiohttp.ClientError, LMStudioAPIError) as e:
            print(f"❌ LM Studio inference error: {e}")
            return self._get_demo_response(prompt)

    async def _try_completions_endpoint(self, prompt: str) -> Optional[str]:
        """Try the completions endpoint."""
        if self.session is None or aiohttp is None:
            return None

        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "temperature": 0.1,
                "max_tokens": 256,
                "stream": False,
                "stop": ["}"]
            }

            async with self.session.post(
                f"{self.base_url}/completions",
                json=payload,
                timeout=30
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'choices' in data and len(data['choices']) > 0:
                        content = data['choices'][0]['text']
                        print(
                            f"✅ LM Studio response received: {len(content)} characters")
                        print(f"🔤 Response preview: {content[:100]}...")
                        return self._extract_json_or_return_content(content)
                else:
                    print(
                        f"⚠️  Completions endpoint returned: {response.status}")
                    raise LMStudioAPIError("Completions endpoint failed")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"⚠️  Completions endpoint failed: {e}")
            return None

    async def _try_chat_completions_endpoint(self, prompt: str) -> str:
        """Try the chat completions endpoint."""
        if self.session is None or aiohttp is None:
            return self._get_demo_response(prompt)

        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 256,
            "stream": False,
            "stop": ["}"]
        }

        print("🔄 Trying chat completions endpoint...")

        async with self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=30
        ) as response:
            if response.status == 200:
                data = await response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    content = data['choices'][0]['message']['content']
                    print(
                        f"✅ LM Studio chat response received: {len(content)} characters")
                    print(f"🔤 Response preview: {content[:100]}...")
                    return self._extract_json_or_return_content(content)
                else:
                    print("⚠️  No choices in LM Studio response")
                    return self._get_demo_response(prompt)
            else:
                print(f"❌ LM Studio API error: {response.status}")
                try:
                    error_text = await response.text()
                    print(f"❌ Error details: {error_text}")
                except (aiohttp.ClientError, UnicodeDecodeError):
                    print("❌ Could not read error details")
                return self._get_demo_response(prompt)

    def _extract_json_or_return_content(self, content: str) -> str:
        """Extract JSON from content or return raw content."""
        if '{' in content and '}' in content:
            start = content.find('{')
            end = content.rfind('}') + 1
            json_part = content[start:end]
            try:
                json.loads(json_part)
                print("✅ Valid JSON response extracted")
                return json_part
            except json.JSONDecodeError:
                print("⚠️  Invalid JSON in response, returning raw text")
        return content

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
  "cautions": ["This is a demo response from LM Studio backend"]
}"""
        elif "translate" in prompt.lower() or "french" in prompt.lower():
            return """{
  "translated": "Ceci est le texte traduit en français.",
  "target_language": "fr",
  "preserved_terms": ["Canada Revenue Agency"],
  "confidence": 0.85,
  "cautions": ["This is a demo response from LM Studio backend"]
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
            return '{"result": "Demo response for LM Studio development"}'

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
                rationale=["Simplified using LM Studio"],
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

        response_text = await self._run_inference(prompt)

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

        response_text = await self._run_inference(prompt)

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
