"""
MapleClear Local Inference Server

FastAPI server that provides local AI inference for simplifying and translating
Canadian government text. Supports multiple backends (llama.cpp, vLLM) and
maintains a local terminology cache.
"""

import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List
import sqlite3

import aiosqlite  # type: ignore # pylint: disable=import-error
import uvicorn  # type: ignore # pylint: disable=import-error
from fastapi import (Depends,  # type: ignore # pylint: disable=import-error
                     FastAPI, HTTPException)
from fastapi.middleware.cors import CORSMiddleware  # type: ignore # pylint: disable=import-error
from fastapi.staticfiles import StaticFiles  # type: ignore # pylint: disable=import-error
from pydantic import (BaseModel,  # type: ignore # pylint: disable=import-error
                      Field)

from .backends.base import InferenceBackend
from .backends.llama_cpp import LlamaCppBackend
from .backends.vllm_backend import VLLMBackend
from .prompts.schema import (AcronymResponse, ModelInfo,
                             SimplificationResponse, TranslationResponse)


class Config:
    """Configuration for the MapleClear server."""
    MODEL_PATH = os.getenv("MAPLECLEAR_MODEL_PATH",
                           "~/.mapleclear/models/gpt-oss-20b/")
    BACKEND = os.getenv("MAPLECLEAR_BACKEND", "vllm")  # or "llama.cpp"
    ADAPTERS = os.getenv("MAPLECLEAR_ADAPTERS", "").split(
        ",") if os.getenv("MAPLECLEAR_ADAPTERS") else []
    TERMS_DB = os.getenv("MAPLECLEAR_TERMS_DB", "data/terms.sqlite")
    HOST = os.getenv("MAPLECLEAR_HOST", "127.0.0.1")
    PORT = int(os.getenv("MAPLECLEAR_PORT", "11434"))


class SimplifyRequest(BaseModel):
    """Request/Response Models"""
    text: str = Field(..., description="Text to simplify")
    target_grade: int = Field(
        7, description="Target reading grade level (6-8)")
    preserve_acronyms: bool = Field(
        True, description="Preserve known acronyms")
    context: str = Field(
        "", description="Additional context about the document")


class TranslateRequest(BaseModel):
    """Request model for translation."""
    text: str = Field(..., description="Text to translate")
    target_language: str = Field(
        "fr", description="Target language code (fr, iu, etc.)")
    preserve_terms: bool = Field(
        True, description="Preserve official terminology")
    experimental: bool = Field(
        False, description="Enable experimental features")


class AcronymRequest(BaseModel):
    """Request model for acronym expansion."""
    text: str = Field(..., description="Text containing potential acronyms")
    context: str = Field("", description="Context to help with disambiguation")


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    model_info: ModelInfo
    local_mode: bool
    backend: str
    adapters: List[str]

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Manage startup and shutdown events for the FastAPI app."""
    # Startup logic
    print("🍁 Starting MapleClear server...")
    print(f"📍 Backend: {Config.BACKEND}")
    print(f"📁 Model path: {Config.MODEL_PATH}")
    print(f"🔧 Adapters: {Config.ADAPTERS}")

    try:
        if Config.BACKEND == "llama.cpp":
            fastapi_app.state.backend = LlamaCppBackend(
                model_path=Config.MODEL_PATH,
                adapters=Config.ADAPTERS
            )
        elif Config.BACKEND == "vllm":
            fastapi_app.state.backend = VLLMBackend(
                model_path=Config.MODEL_PATH,
                adapters=Config.ADAPTERS
            )
        else:
            raise ValueError(f"Unknown backend: {Config.BACKEND}")

        await fastapi_app.state.backend.initialize()
        print(
            f"✅ MapleClear server ready on http://{Config.HOST}:{Config.PORT}")

    except Exception as e:
        print(f"❌ Failed to initialize backend: {e}")
        raise

    try:
        yield
    finally:
        # Shutdown logic
        if hasattr(fastapi_app.state, 'backend') and fastapi_app.state.backend:
            await fastapi_app.state.backend.cleanup()
        if hasattr(fastapi_app.state, 'backend') and fastapi_app.state.backend:
            await fastapi_app.state.backend.cleanup()

app = FastAPI(
    title="MapleClear Inference Server",
    description="Local AI inference for simplifying Canadian government text",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_backend() -> InferenceBackend:
    """Dependency to get the current backend instance."""
    return app.state.backend

async def get_terms_db():
    """Get database connection for terms."""
    db_path = Path(Config.TERMS_DB)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return await aiosqlite.connect(db_path)

@app.get("/health", response_model=HealthResponse)
async def health_check(backend: InferenceBackend = Depends(get_backend)):
    """Health check endpoint with model information."""
    model_info = await backend.get_model_info()
    return HealthResponse(
        status="healthy",
        model_info=model_info,
        local_mode=True,
        backend=Config.BACKEND,
        adapters=Config.ADAPTERS
    )


@app.post("/simplify", response_model=SimplificationResponse)
async def simplify_text(
    request: SimplifyRequest,
    backend: InferenceBackend = Depends(get_backend)
):
    """Simplify text to plain language."""
    try:
        response = await backend.simplify(
            text=request.text,
            target_grade=request.target_grade,
            preserve_acronyms=request.preserve_acronyms,
            context=request.context
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Simplification failed: {str(e)}") from e


@app.post("/translate", response_model=TranslationResponse)
async def translate_text(
    request: TranslateRequest,
    backend: InferenceBackend = Depends(get_backend)
):
    """Translate text to target language."""
    try:
        response = await backend.translate(
            text=request.text,
            target_language=request.target_language,
            preserve_terms=request.preserve_terms,
            experimental=request.experimental
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Translation failed: {str(e)}") from e


@app.post("/acronyms", response_model=AcronymResponse)
async def expand_acronyms(request: AcronymRequest):
    """Find and expand acronyms in text."""    
    try:
        # Simple regex to find potential acronyms
        potential_acronyms = re.findall(r'\b[A-Z]{2,}\b', request.text)

        found_acronyms = []

        # Try to connect to database
        try:
            db_path = Path(Config.TERMS_DB)
            db_path.parent.mkdir(parents=True, exist_ok=True)

            # Use a simpler synchronous approach to avoid threading issues
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                for acronym in set(potential_acronyms):
                    cursor.execute(
                        "SELECT expansion, definition, source_url FROM acronyms WHERE acronym = ?",
                        (acronym,)
                    )
                    row = cursor.fetchone()
                    if row:
                        found_acronyms.append({
                            "acronym": acronym,
                            "expansion": row[0],
                            "definition": row[1],
                            "source_url": row[2],
                            "confidence": 1.0,
                            "source": "local_cache"
                        })
        except (sqlite3.Error, OSError) as db_error:
            print(f"Database error: {db_error}")
            # If database fails, just return empty list

        return AcronymResponse(acronyms=found_acronyms)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Acronym expansion failed: {str(e)}") from e


if Path("demo").exists():
    app.mount("/demo", StaticFiles(directory="demo"), name="demo")


if __name__ == "__main__":
    uvicorn.run(
        "server.app:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=True
    )
