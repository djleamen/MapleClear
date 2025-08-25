"""
Base class for inference backends.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

import textstat # type: ignore # pylint: disable=import-error

from ..prompts.schema import (AcronymResponse, ModelInfo, # type: ignore #pylint: disable=no-name-in-module
                              SimplificationResponse, TranslationResponse) # type: ignore #pylint: disable=no-name-in-module


class InferenceBackend(ABC):
    """Abstract base class for AI inference backends."""

    def __init__(self, model_path: str, adapters: Optional[List[str]] = None):
        self.model_path = model_path
        self.adapters = adapters or []
        self.model = None
        self.tokenizer = None

    @abstractmethod
    async def initialize(self) -> None:
        """TODO: Initialize the backend and load the model."""
        pass # pylint: disable=unnecessary-pass

    @abstractmethod
    async def cleanup(self) -> None:
        """TODO: Clean up resources."""
        pass # pylint: disable=unnecessary-pass

    @abstractmethod
    async def get_model_info(self) -> ModelInfo:
        """TODO: Get information about the loaded model."""
        pass # pylint: disable=unnecessary-pass

    @abstractmethod
    async def simplify(
        self,
        text: str,
        target_grade: int = 7,
        preserve_acronyms: bool = True,
        context: str = ""
    ) -> SimplificationResponse:
        """TODO: Simplify text to plain language."""
        pass # pylint: disable=unnecessary-pass

    @abstractmethod
    async def translate(
        self,
        text: str,
        target_language: str = "fr",
        preserve_terms: bool = True,
        experimental: bool = False
    ) -> TranslationResponse:
        """TODO: Translate text to target language."""
        pass # pylint: disable=unnecessary-pass

    @abstractmethod
    async def expand_acronyms(
        self,
        text: str,
        context: str = ""
    ) -> AcronymResponse:
        """TODO: Find and expand acronyms in text."""
        pass # pylint: disable=unnecessary-pass

    def _calculate_readability(self, text: str) -> float:
        """Calculate reading grade level using textstat."""
        try:
            return textstat.flesch_kincaid_grade(text)  # type: ignore[attr-defined]
        except (ImportError, AttributeError):
            # Fallback: simple heuristic based on sentence and word length
            sentences = text.split('.')
            words = text.split()

            if not sentences or not words:
                return 0.0

            avg_sentence_length = len(words) / len(sentences)
            avg_word_length = sum(len(word) for word in words) / len(words)

            # Simplified Flesch-Kincaid approximation
            return 0.39 * avg_sentence_length + 11.8 * avg_word_length - 15.59
