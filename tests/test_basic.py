"""
Basic tests for MapleClear server functionality.
"""

import sqlite3  # type: ignore # pylint: disable=import-error
import tempfile  # type: ignore # pylint: disable=import-error
from pathlib import Path

import pytest  # type: ignore # pylint: disable=import-error

from server.backends.base import InferenceBackend
from server.prompts.schema import ModelInfo, SimplificationResponse, TranslationResponse, AcronymResponse
from tools.seed_terms import (GOVERNMENT_ACRONYMS, create_database,
                              seed_acronyms)


class MockBackend(InferenceBackend):
    """Mock backend for testing."""

    async def initialize(self):
        """TODO: Initialize the mock backend."""
        pass  # pylint: disable=unnecessary-pass

    async def cleanup(self):
        """TODO: Clean up the mock backend."""
        pass  # pylint: disable=unnecessary-pass

    async def get_model_info(self):
        """TODO: Get model information from the mock backend."""
        return ModelInfo(
            name="test-model",
            backend="mock",
            size="test"
        )

    async def simplify(self, text, target_grade=7, preserve_acronyms=True, context=""):
        return SimplificationResponse(
            plain="This is simplified text.",
            rationale=["Made text simpler"],
            cautions=[]
        )

    async def translate(self, text, target_language="fr", preserve_terms=True, experimental=False):
        return TranslationResponse(
            translated="Texte traduit",
            target_language=target_language,
            preserved_terms=[],
            confidence=0.85,
            cautions=[]
        )

    async def expand_acronyms(self, text, context=""):
        return AcronymResponse(
            acronyms=[{
                "acronym": "CRA",
                "expansion": "Canada Revenue Agency",
                "definition": "Test definition",
                "confidence": 0.9,
                "source": "test"
            }]
        )

    def calculate_readability(self, text):
        """Public method to calculate readability for testing."""
        # Simple mock calculation based on text length and complexity
        words = len(text.split())
        sentences = text.count('.') + text.count('!') + text.count('?')
        if sentences == 0:
            sentences = 1
        avg_words_per_sentence = words / sentences
        # Mock grade level calculation
        return min(12, max(1, avg_words_per_sentence / 3))


def test_database_creation():
    """Test terminology database creation."""
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as f:
        db_path = Path(f.name)

    try:
        create_database(db_path)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            assert 'acronyms' in tables
            assert 'terms' in tables

    finally:
        db_path.unlink(missing_ok=True)


def test_acronym_seeding():
    """Test seeding acronyms into database."""
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as f:
        db_path = Path(f.name)

    try:
        create_database(db_path)
        seed_acronyms(db_path, GOVERNMENT_ACRONYMS)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM acronyms")
            count = cursor.fetchone()[0]

            assert count > 0

            cursor.execute(
                "SELECT expansion FROM acronyms WHERE acronym = 'CRA'")
            result = cursor.fetchone()
            assert result is not None
            assert "Canada Revenue Agency" in result[0]

    finally:
        db_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_mock_backend():
    """Test mock backend functionality."""
    backend = MockBackend("test-model")

    await backend.initialize()

    result = await backend.simplify("Complex government text here.")
    assert "simplified" in result.plain.lower()
    assert len(result.rationale) > 0


def test_readability_calculation():
    """Test readability grade calculation."""
    backend = MockBackend("test")

    simple_text = "This is simple. Easy to read."
    simple_grade = backend.calculate_readability(simple_text)

    complex_text = "The aforementioned administrative procedures necessitate comprehensive documentation and verification protocols."
    complex_grade = backend.calculate_readability(complex_text)

    assert complex_grade > simple_grade


if __name__ == "__main__":
    pytest.main([__file__])
