import re

MAX_INPUT_LENGTH = 100_000

# --- PII Patterns ---

# EMAIL: explicit dash escape, lookahead prevents trailing punctuation,
# negative lookahead prevents consecutive dots in local part
EMAIL_PATTERN = re.compile(
    r'(?!.*\.\.)[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}(?=[^a-zA-Z]|$)',
    re.IGNORECASE
)

# PHONE: counts digits explicitly (not characters), allows separators between them.
# Requires 7-15 digits total (E.164 standard).
# Known limitations:
#   - Dates like 2024-01-15 may still match (regex cannot distinguish context)
#   - IBANs and card numbers may partially match (requires NER for full fix - v2)
PHONE_PATTERN = re.compile(
    r'\+?(?:\d[\s\-(). ]*){7,15}\d'
)


# --- Validation ---

def _validate_input(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError(f"Expected str, got {type(text).__name__}")
    if '\x00' in text:
        raise ValueError("Input contains null bytes")
    if len(text) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input too large: {len(text)} chars (max {MAX_INPUT_LENGTH})")
    return text


# --- Masking Functions ---

def mask_emails(text: str) -> str:
    return EMAIL_PATTERN.sub('[EMAIL]', text)


def mask_phones(text: str) -> str:
    return PHONE_PATTERN.sub('[PHONE]', text)


def mask_all(text: str) -> str:
    text = _validate_input(text)
    text = mask_emails(text)
    text = mask_phones(text)
    return text