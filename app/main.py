from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from app.core import mask_all, MAX_INPUT_LENGTH
import logging

logger = logging.getLogger("dataprep")

app = FastAPI(
    title="DataPrep Tool",
    description="PII masking API for HR and Finance workflows",
    version="0.1.0"
)

# --- Middleware ---

# Request size limiting is handled at the infrastructure level (Nginx).
# See deployment configuration for client_max_body_size setting.
# Pydantic field_validator provides application-level protection for text length.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # restrict in production via env
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# --- Schemas ---

class TextRequest(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def text_must_not_be_too_large(cls, v: str) -> str:
        if len(v) > MAX_INPUT_LENGTH:
            raise ValueError("Input text exceeds maximum allowed length")
        return v


class TextResponse(BaseModel):
    masked_text: str
    chars_processed: int


# --- Endpoints ---

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/v1/mask/text", response_model=TextResponse)
def mask_text(request: TextRequest):
    try:
        result = mask_all(request.text)
        return TextResponse(
            masked_text=result,
            chars_processed=len(request.text)
        )
    except TypeError:
        logger.warning("Invalid input type received")
        raise HTTPException(status_code=422, detail="Invalid input format")
    except ValueError:
        logger.warning("Invalid input value received")
        raise HTTPException(status_code=400, detail="Invalid input data")