"""
Groq backend implementation for MapleClear.
Uses Groq's fast inference API for gpt-oss models.
"""
import os
import json
import re
from typing import Optional, List

try:
    import httpx  # type: ignore
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

from .base import InferenceBackend
from ..prompts.schema import SimplificationResponse, TranslationResponse, AcronymResponse, ModelInfo


class GroqError(Exception):
    """Custom exception for Groq backend errors."""


class GroqConnectionError(GroqError):
    """Exception for Groq connection issues."""


class GroqAPIError(GroqError):
    """Exception for Groq API errors."""


# Constants
GROQ_API_BASE = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b"
DEMO_MODE_MESSAGE = "🚧 Running in demo mode"


class GroqBackend(InferenceBackend):
    """Backend using Groq's API for fast gpt-oss inference."""

    def __init__(self, model_path: str = "", adapters: Optional[List[str]] = None):
        super().__init__(model_path or DEFAULT_MODEL, adapters or [])
        self.api_key = None
        self.client = None
        self.demo_mode = False

    async def initialize(self) -> None:
        """Initialize Groq backend."""
        if not HTTPX_AVAILABLE:
            print("httpx not available, running in demo mode")
            self.demo_mode = True
            return

        self.api_key = os.getenv("GROQ")
        if not self.api_key:
            print("⚠️ GROQ API key not found in environment, running in demo mode")
            self.demo_mode = True
            return

        if HTTPX_AVAILABLE and httpx is not None:
            self.client = httpx.AsyncClient(
                base_url=GROQ_API_BASE,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )

        try:
            await self._check_api_status()
            print(f"Groq backend initialized with model: {self.model_path}")
        except (GroqConnectionError, GroqAPIError) as e:
            print(f"Groq API not accessible ({e}), running in demo mode...")
            self.demo_mode = True

    async def _check_api_status(self) -> None:
        """Check if Groq API is accessible."""
        if self.demo_mode or not self.client or not HTTPX_AVAILABLE or httpx is None:
            return

        try:
            response = await self.client.get("/models")
            response.raise_for_status()
        except (httpx.ConnectError, httpx.RequestError, httpx.TimeoutException) as e:
            raise GroqConnectionError(
                f"Failed to connect to Groq API: {e}") from e
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            response_text = e.response.text
            raise GroqAPIError(
                f"Groq API error: {status_code} - {response_text}") from e
        except httpx.HTTPError as e:
            raise GroqAPIError(f"Groq API error: {e}") from e

    async def cleanup(self) -> None:
        """Cleanup Groq backend."""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def get_model_info(self) -> ModelInfo:
        """Get information about the current model."""
        return ModelInfo(
            name=self.model_path,
            size="20B" if "20b" in self.model_path.lower() else "120B",
            backend="groq",
            parameters={"api_endpoint": GROQ_API_BASE},
            adapters=self.adapters,
            memory_usage="Remote (Groq API)",
            quantization="FP16"
        )

    async def _run_inference(self, prompt: str) -> str:
        """Run inference using Groq API."""
        if self.demo_mode:
            return self._get_demo_response(prompt)

        if not self.client:
            raise GroqError("Groq client not initialized")

        data = None # Initialize to avoid unbound variable issues

        try:
            # Use OpenAI-compatible chat completions endpoint
            request_data = {
                "model": self.model_path,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 2048,
                "temperature": 0.1,
                "stream": False
            }

            print(
                f"Sending request to Groq API with model: {self.model_path}")

            response = await self.client.post(
                "/chat/completions",
                json=request_data
            )
            response.raise_for_status()

            data = response.json()
            print(
                f"✅ Received response from Groq API: {len(str(data))} characters")
            print(f"Full response data: {json.dumps(data, indent=2)}")

            if "choices" not in data or not data["choices"]:
                print(
                    f"❌ No choices in API response. Keys: {list(data.keys())}")
                raise GroqAPIError("No choices in API response")

            choice = data["choices"][0]
            message = choice.get("message", {})

            # Try to get content from either content or reasoning field
            content = message.get("content", "")
            reasoning = message.get("reasoning", "")

            # Use reasoning if content is empty (happens when model hits token limit)
            if not content.strip() and reasoning.strip():
                print("Content field empty, using reasoning field instead")
                content = reasoning
            elif not content.strip():
                print("❌ Both content and reasoning fields are empty")
                raise GroqAPIError("No content in API response")

            print(
                f"Content extracted ({len(content)} chars): {repr(content[:500])}")

            # Extract JSON if present, otherwise return content
            return self._extract_json_or_return_content(content)

        except (ConnectionError, TimeoutError) as e:
            print(f"Connection error: {e}")
            raise GroqConnectionError(
                f"Failed to connect to Groq API: {e}") from e
        except (KeyError, json.JSONDecodeError) as e:
            print(f"Parse error: {e}")
            if data:
                print(f"Raw response data: {data}")
            else:
                print("No response data available")
            raise GroqAPIError(f"Failed to parse Groq response: {e}") from e
        except Exception as e:  # pylint: disable=broad-except
            print(f"Unexpected error: {type(e).__name__}: {e}")
            # Handle any other errors as API errors
            raise GroqAPIError(f"Groq API error: {e}") from e

    def _extract_json_or_return_content(self, content: str) -> str:
        """Extract JSON from response content or return the content as-is."""
        print(
            f"Extracting JSON from content ({len(content)} chars): {repr(content[:200])}")

        if not content or not content.strip():
            print("❌ Content is empty or whitespace only")
            return content

        # Try to find JSON in the response
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                # Validate that it's proper JSON
                parsed = json.loads(json_str)
                print(f"Found valid JSON with keys: {list(parsed.keys())}")
                return json_str
            except json.JSONDecodeError as e:
                print(f"Invalid JSON found: {e}")

        # If the entire content looks like JSON, try parsing it directly
        try:
            parsed = json.loads(content)
            print(f"Content is valid JSON with keys: {list(parsed.keys())}")
            return content
        except json.JSONDecodeError:
            print(
                f"Content is not valid JSON, returning as-is: {repr(content[:100])}")

        # Return content as-is if no valid JSON found
        return content

    def _get_demo_response(self, prompt: str) -> str:
        """Return demo responses for testing without API."""
        if "simplify" in prompt.lower():
            return json.dumps({
                "plain": "This is a simplified version of the text. Complex terms have been replaced with simpler alternatives.",  # pylint: disable=line-too-long
                "rationale": ["Replaced technical jargon", "Shortened sentences", "Used common words"],  # pylint: disable=line-too-long
                "cautions": ["Some nuance may be lost in simplification"],
                "readability_grade": 7.2
            })
        if "translate" in prompt.lower():
            return json.dumps({
                "translated": "Ceci est une traduction du texte en français.",
                "target_language": "French",
                "preserved_terms": ["specific terminology"],
                "confidence": 0.85,
                "cautions": ["Some context may be lost in translation"]
            })
        if "acronym" in prompt.lower():
            return json.dumps({
                "expansions": [
                    {"acronym": "API", "expansion": "Application Programming Interface",
                        "confidence": 0.95},
                    {"acronym": "JSON", "expansion": "JavaScript Object Notation",
                        "confidence": 0.98}
                ]
            })
        return f"{DEMO_MODE_MESSAGE}: Demo response for: {prompt[:50]}..."

    async def simplify(
        self,
        text: str,
        target_grade: int = 7,
        preserve_acronyms: bool = True,
        context: str = ""
    ) -> SimplificationResponse:
        """Simplify text to target reading grade level."""
        try:
            prompt_template = self._load_prompt_template("simplify")
            prompt = prompt_template.format(
                text=text,
                target_grade=target_grade,
                preserve_acronyms=preserve_acronyms,
                context=context
            )

            result = await self._run_inference(prompt)
            print(f"Simplify result: {result[:200]}...")

            try:
                response_data = json.loads(result)
                print("✅ Successfully parsed JSON response for simplification")
                return SimplificationResponse(**response_data)
            except (json.JSONDecodeError, KeyError) as e:
                print(
                    f"❌ Failed to parse simplification response as JSON: {e}")
                print(f"Raw result: {result}")

                # Try to extract just the text content if JSON parsing fails
                cleaned_result = self._extract_clean_text(result)

                return SimplificationResponse(
                    plain=cleaned_result,
                    rationale=["Response was not in expected JSON format"],
                    cautions=[
                        "AI response required cleanup - please verify accuracy"]
                )
        except (GroqConnectionError, GroqAPIError) as e:
            print(f"❌ Simplification failed with Groq error: {e}")
            return SimplificationResponse(
                plain="Simplification failed",
                rationale=[f"Groq API error: {str(e)}"],
                cautions=["An error occurred during processing"]
            )

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

        result = await self._run_inference(prompt)

        # Try JSON first in case the model ignores our instructions
        try:
            response_data = json.loads(result)
            return TranslationResponse(**response_data)
        except (json.JSONDecodeError, KeyError):
            # Use the result directly as translated text (expected path)
            return TranslationResponse(
                translated=result.strip(),
                target_language=target_language,
                preserved_terms=[],
                confidence=0.8,
                cautions=[]
            )

    async def expand_acronyms(
        self,
        text: str,
        context: str = ""
    ) -> AcronymResponse:
        """Expand acronyms found in text."""
        prompt_template = self._load_prompt_template("acronym")
        prompt = prompt_template.format(
            text=text,
            context=context
        )

        result = await self._run_inference(prompt)

        try:
            response_data = json.loads(result)
            return AcronymResponse(**response_data)
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback for non-JSON responses
            return AcronymResponse(
                expansions=[],
                cautions=[f"Parse error: {str(e)}"]
            )

    def _load_prompt_template(self, task: str) -> str:
        """Load prompt template for the given task."""
        templates = {
            # pylint: disable=line-too-long
            "simplify": """You are a helpful assistant that simplifies Canadian government text. 

IMPORTANT: Respond with ONLY valid JSON. Do not include any explanation, reasoning, or other text.

Task: Simplify this text to Grade {target_grade} reading level while preserving accuracy and acronyms.

Text: {text}

Response format (JSON only):
{{
    "plain": "your simplified text here",
    "rationale": ["briefly explain major changes"],
    "cautions": ["any important warnings"],
    "readability_grade": 7.0
}}""",
            "translate": """You are a helpful translator for Canadian government content.

IMPORTANT: Respond with ONLY the translated text. Do not include any explanations or reasoning.

Translate this text to {target_language}:

{text}

TRANSLATED TEXT:""",
            "acronym": """Find and expand all acronyms in this text. Respond with ONLY valid JSON.

{text}

Response format (JSON only):
{{
    "expansions": [
        {{
            "acronym": "acronym",
            "expansion": "full expansion", 
            "confidence": 0.9
        }}
    ]
}}"""
        }

        return templates.get(task, "Process this text: {text}")

    def _extract_clean_text(self, raw_result: str) -> str:
        """Extract clean text from a malformed AI response."""
        if not raw_result or not raw_result.strip():
            return "No content was generated"

        # Remove common reasoning patterns
        cleaned = raw_result

        # Remove "We need to..." type reasoning
        cleaned = re.sub(r'^We need to.*?\. ', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^I need to.*?\. ', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^The.*?is to.*?\. ', '',
                         cleaned, flags=re.MULTILINE)

        # Remove JSON-related text
        cleaned = re.sub(r'.*?with plain simplified text.*?\. ',
                         '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'.*?Provide.*?\. ', '', cleaned, flags=re.DOTALL)

        # If it looks like JSON but is malformed, try to extract content
        if '{' in cleaned and '}' in cleaned:
            # Try to find content between quotes after "plain":
            plain_match = re.search(
                r'"plain"\s*:\s*"([^"]*)"', cleaned, re.DOTALL)
            if plain_match:
                return plain_match.group(1)

        # Clean up remaining reasoning text
        lines = cleaned.split('\n')
        content_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Skip lines that look like reasoning
            if any(phrase in line.lower() for phrase in [
                'we need to', 'i need to', 'the goal is to', 'let\'s', 'first,', 'second,',
                'provide', 'ensure', 'make sure', 'it is important', 'we can', 'we should'
            ]):
                continue

            content_lines.append(line)

        result = ' '.join(content_lines)
        return result if result.strip() else "Content could not be extracted from AI response"
