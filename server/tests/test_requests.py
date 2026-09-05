"""Smallest checks that fail if request validation or language handling breaks."""
import pytest
from pydantic import ValidationError

from server.app import (MAX_TEXT_CHARS, SimplifyRequest, TranslateRequest,
                        normalize_language_input)


def test_language_codes_and_names_normalize():
    assert normalize_language_input("fr") == "French"
    assert normalize_language_input(" French ") == "French"
    assert normalize_language_input("iu") == "Inuktitut"
    assert normalize_language_input("klingon") == "Klingon"


def test_simplify_rejects_oversized_text_and_bad_grade():
    with pytest.raises(ValidationError):
        SimplifyRequest(text="x" * (MAX_TEXT_CHARS + 1))
    with pytest.raises(ValidationError):
        SimplifyRequest(text="hello", target_grade=0)
    with pytest.raises(ValidationError):
        SimplifyRequest(text="")
    assert SimplifyRequest(text="hello", target_grade=12).target_grade == 12


def test_translate_defaults():
    req = TranslateRequest(text="Bonjour")
    assert req.target_language == "French"
    assert req.preserve_terms is True
