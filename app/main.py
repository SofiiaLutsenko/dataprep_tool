import csv
import io
import logging
import urllib.parse

import anyio
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import settings
from app.core import MAX_INPUT_LENGTH, mask_all

logger = logging.getLogger("dataprep")

# --- Auth ---

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Depends(API_KEY_HEADER)) -> None:
    if not api_key or api_key != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )


# --- App ---

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="DataPrep Tool",
    description="PII masking API for HR and Finance workflows",
    version=settings.app_version
)

# Trust X-Forwarded-For only from localhost (Nginx on same machine)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="127.0.0.1")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
CSV_INJECTION_CHARS = ("=", "@", "+", "-")
MAX_FILE_BYTES = 99_000  # aligned with MAX_INPUT_LENGTH in core.py (~100KB)


def _is_utf8_text_content(data: bytes) -> bool:
    """Reject binary files by checking for null bytes in first 1024 bytes.
    Note: UTF-16 encoded files will also be rejected — UTF-8 is required."""
    return b"\x00" not in data[:1024]


async def _read_file_chunked(file: UploadFile, max_bytes: int) -> bytes:
    """Read file in chunks, raise 413 if size exceeds limit."""
    content = bytearray()
    while chunk := await file.read(1024 * 1024):  # 1MB chunks
        content.extend(chunk)
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {max_bytes // 1000}KB"
            )
    return bytes(content)


def _sanitize_csv(text: str) -> str:
    """Prevent CSV injection using proper CSV parsing.
    Uses csv module to correctly handle quoted fields with commas."""
    input_stream = io.StringIO(text)
    output_stream = io.StringIO()

    reader = csv.reader(input_stream)
    writer = csv.writer(output_stream)

    for row in reader:
        clean_row = []
        for field in row:
            if field.lstrip().startswith(CSV_INJECTION_CHARS):
                field = f"'{field}"
            clean_row.append(field)
        writer.writerow(clean_row)

    return output_stream.getvalue()


# --- Endpoints ---

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/v1/mask/text", response_model=TextResponse, dependencies=[Depends(verify_api_key)])
@limiter.limit("30/minute")
def mask_text(request: Request, body: TextRequest):
    try:
        result = mask_all(body.text)
        return TextResponse(
            masked_text=result,
            chars_processed=len(body.text)
        )
    except TypeError:
        logger.warning("Invalid input type received")
        raise HTTPException(status_code=422, detail="Invalid input format")
    except ValueError:
        logger.warning("Invalid input value received")
        raise HTTPException(status_code=400, detail="Invalid input data")


@app.post("/api/v1/mask/file", dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def mask_file(request: Request, file: UploadFile = File(...)):
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
    if not _is_utf8_text_content(content):
        raise HTTPException(
            status_code=422,
            detail="File appears to be binary or non-UTF-8 encoded. Please upload a UTF-8 encoded file"
        )

    # Decode
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=422,
            detail="File encoding not supported. Please upload a UTF-8 encoded file"
        )

    # Sanitize CSV injection before masking
    if ext == ".csv":
        text = _sanitize_csv(text)

    # Mask — run in thread pool to avoid blocking event loop
    try:
        masked = await anyio.to_thread.run_sync(mask_all, text)
    except ValueError:
        logger.warning("File content validation failed")
        raise HTTPException(status_code=400, detail="Invalid file content")

    # Sanitize filename — prevents Header Injection
    safe_filename = urllib.parse.quote(filename, safe=".-_")

    return Response(
        content=masked.encode("utf-8"),
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''masked_{safe_filename}"
        }
    )