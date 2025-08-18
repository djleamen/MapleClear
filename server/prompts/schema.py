"""
Pydantic schemas for API request/response models.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field # type: ignore # pylint: disable=import-error


class SimplificationResponse(BaseModel):
    """Response from text simplification."""
    plain: str = Field(..., description="Simplified text")
    rationale: List[str] = Field(
        default_factory=list, description="List of changes made")
    cautions: List[str] = Field(
        default_factory=list, description="Warnings or uncertainties")
    readability_grade: Optional[float] = Field(
        None, description="Estimated reading grade level")
    original_grade: float = Field(...,
    original_grade: Optional[float] = Field(
        None, description="Original reading grade level")


class TranslationResponse(BaseModel):
    """Response from text translation."""
    translated: str = Field(..., description="Translated text")
    target_language: str = Field(..., description="Target language code")
    preserved_terms: List[str] = Field(
        default_factory=list, description="Terms preserved from original")
    confidence: float = Field(...,
                              description="Translation confidence score (0-1)")
    experimental: bool = Field(
        default=False, description="Whether experimental features were used")
    cautions: List[str] = Field(
        default_factory=list, description="Translation warnings")


class AcronymExpansion(BaseModel):
    """Individual acronym expansion."""
    acronym: str = Field(..., description="The acronym")
    expansion: str = Field(..., description="Full expansion")
    definition: str = Field("", description="Brief definition")
    confidence: float = Field(..., description="Confidence score (0-1)")
    source: str = Field(...,
                        description="Source of expansion (local_cache, ai_inference, etc.)")
    source_url: Optional[str] = Field(
        None, description="URL to official definition if available")


class AcronymResponse(BaseModel):
    """Response from acronym expansion."""
    acronyms: List[AcronymExpansion] = Field(
        default_factory=list, description="Found acronym expansions")


class ModelInfo(BaseModel):
    """Information about the loaded model."""
    name: str
    size: str
    quantization: Optional[str] = None
    backend: str
    adapters: List[str] = Field(default_factory=list)
    memory_usage: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
