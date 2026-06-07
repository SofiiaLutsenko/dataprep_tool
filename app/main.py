from app.config import settings
import io
import logging
import urllib.parse

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.core import mask_all, MAX_INPUT_LENGTH

logger = logging.getLogger("dataprep")

app = FastAPI(
    title="DataPrep Tool",
    description="PII masking API for HR and Finance workflows",
    version=settings.app_version
)

# --- Middleware ---

# Request size limiting is handled at the infrastructure level (Nginx).
# See deployment configuration for client_max_body_size setting.
# Pydantic field_validator provides application-level protection for text length.

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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


# --- File Upload Helpers ---

ALLOWED_EXTENSIONS = {".txt", ".csv"}
MAX_FILE_BYTES = 5_242_880  # 5MB


def _is_text_content(data: bytes) -> bool:
    """Reject binary files by checking for null bytes in first 1024 bytes."""
    return b"\x00" not in data[:1024]


async def _read_file_chunked(file: UploadFile, max_bytes: int) -> bytes:
    """Read file in chunks, raise 413 if size exceeds limit."""
    content = bytearray()
    while chunk := await file.read(1024 * 1024):  # 1MB chunks
        content.extend(chunk)
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail="File too large. Maximum size is 5MB"
            )
    return bytes(content)


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


@app.post("/api/v1/mask/file")
async def mask_file(file: UploadFile = File(...)):
    # Validate extension
    filename = file.filename or "upload"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read in chunks — prevents OOM
    content = await _read_file_chunked(file, MAX_FILE_BYTES)

    # Validate content (not just extension)
    if not _is_text_content(content):
        raise HTTPException(
            status_code=422,
            detail="File appears to be binary. Please upload a plain text file"
        )

    # Decode
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=422,
            detail="File encoding not supported. Please upload a UTF-8 encoded file"
        )

    # Mask
    try:
        masked = mask_all(text)
    except ValueError:
        logger.warning("File content validation failed")
        raise HTTPException(status_code=400, detail="Invalid file content")

    # Sanitize filename — prevents Header Injection
    safe_filename = urllib.parse.quote(filename, safe=".-_")

    return StreamingResponse(
        io.BytesIO(masked.encode("utf-8")),
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''masked_{safe_filename}"
        }
    )