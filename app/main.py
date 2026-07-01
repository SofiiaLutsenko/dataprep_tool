import csv
import io
import logging
import urllib.parse
from contextlib import asynccontextmanager

import anyio
from fastapi import Body, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.auth_utils import get_password_hash
from app.config import settings
from app.core import MAX_INPUT_LENGTH, mask_all
from app.database import AsyncSessionLocal, Base, engine, get_db
from app.models import SubscriptionTier, TierType, User, normalize_email
from app.schemas import UserCreate, UserResponse
from app.payments import router as payments_router  # New payments router

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger("dataprep")

# --- Auth ---

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Depends(API_KEY_HEADER)) -> None:
    if not api_key or api_key != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )

# --- Lifespan Manager ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed the BASIC subscription tier
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SubscriptionTier).where(SubscriptionTier.name == TierType.BASIC)
        )
        if result.scalar_one_or_none() is None:
            session.add(SubscriptionTier(name=TierType.BASIC, daily_request_limit=50))
            await session.commit()

    yield

# --- App ---

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="DataPrep Tool",
    description="PII masking API for HR and Finance workflows",
    version=settings.app_version,
    lifespan=lifespan
)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="127.0.0.1")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Register the payments router
app.include_router(payments_router)

# --- Schemas ---

class UserRegisterRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email address format")
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def password_length_check(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


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
MAX_FILE_BYTES = 30_000

def _is_utf8_text_content(data: bytes) -> bool:
    return b"\x00" not in data[:1024]

async def _read_file_chunked(file: UploadFile, max_bytes: int) -> bytes:
    content = bytearray()
    while chunk := await file.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {max_bytes // 1000}KB"
            )
    return bytes(content)

def _sanitize_csv(text: str) -> str:
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

@app.post("/api/v1/auth/register", response_model=UserResponse, status_code=201)
async def register_user(
    body: UserRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    query = select(User).where(User.email == body.email)
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User with this email already registered"
        )

    hashed_pass = get_password_hash(body.password)
    new_user = User(email=normalize_email(body.email), hashed_password=hashed_pass)

    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    return new_user

@app.post(
    "/api/v1/mask/text",
    response_model=TextResponse,
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("10/minute")
def mask_text(
    request: Request,
    body: TextRequest,
    mode: str = Query("full", pattern="^(fast|full)$"),
):
    try:
        result = mask_all(body.text, mode=mode)
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

@app.post(
    "/api/v1/mask/file",
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("3/minute")
async def mask_file(
    request: Request,
    file: UploadFile = File(...),
    mode: str = Query("full", pattern="^(fast|full)$"),
):
    filename = file.filename or "upload"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content = await _read_file_chunked(file, MAX_FILE_BYTES)

    if not _is_utf8_text_content(content):
        raise HTTPException(
            status_code=422,
            detail="File appears to be binary or non-UTF-8 encoded."
        )

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=422,
            detail="File encoding not supported. Please upload a UTF-8 encoded file"
        )

    if ext == ".csv":
        text = _sanitize_csv(text)

    try:
        masked = await anyio.to_thread.run_sync(mask_all, text, mode)
    except ValueError:
        logger.warning("File content validation failed")
        raise HTTPException(status_code=400, detail="Invalid file content")

    safe_filename = urllib.parse.quote(filename, safe=".-_")

    return Response(
        content=masked.encode("utf-8"),
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''masked_{safe_filename}"
        }
    )