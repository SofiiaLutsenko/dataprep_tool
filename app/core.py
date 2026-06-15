import re
import spacy

# Load once at module level — loading per-request would be too slow
_nlp = spacy.load("en_core_web_sm")

# Common tech terms that spaCy's small model sometimes misclassifies as PERSON
TECH_TERM_WHITELIST = {
    "python", "java", "javascript", "typescript", "react", "angular", "vue",
    "node", "django", "flask", "fastapi", "spring", "docker", "kubernetes",
    "aws", "azure", "git", "github", "gitlab", "linux", "windows", "mongodb",
    "postgresql", "mysql", "redis", "graphql", "rest", "html", "css", "sql",
    "swift", "kotlin", "golang", "rust", "scala", "ruby", "php", "c++", "c#",
}

MAX_INPUT_LENGTH = 100_000

# --- PII Patterns ---

# EMAIL: standard format with complex TLDs and subdomains
EMAIL_PATTERN = re.compile(
    r'(?<![a-zA-Z0-9._%+\-])'
    r'(?!\S*\.\.)'
    r'[a-zA-Z0-9._%+\-]+'
    r'\s*@\s*'
    r'[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
    r'(?=[^a-zA-Z0-9]|$)',
    re.IGNORECASE
)

# OBFUSCATED EMAIL: user [at] domain.com / user(at)domain[dot]com / user @ domain.com
OBFUSCATED_EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+\-]+'
    r'\s*(?:\[at\]|\(at\))\s*'
    r'[a-zA-Z0-9.\-]+'
    r'\s*(?:\[dot\]|\(dot\)|\.)\s*'
    r'[a-zA-Z]{2,}',
    re.IGNORECASE
)

# PHONE: covers E.164, European 00-prefix, separators, brackets, extensions
# Handles: +49, 0049, spaces, dashes, dots, slashes, (0) notation, ext/x
PHONE_PATTERN = re.compile(
    r'(?:'
        r'(?:\+{1,2}|00)[1-9]\d{0,3}'
        r'[\s\-./]?'
    r')?'
    r'(?:\(0?\d{1,4}\)[\s\-./]?)?'
    r'\d[\d\s\-./]{4,18}\d'
    r'(?:[\s\-]?(?:ext\.?|x)\s*\d{1,5})?'
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
    text = OBFUSCATED_EMAIL_PATTERN.sub('[EMAIL]', text)
    text = EMAIL_PATTERN.sub('[EMAIL]', text)
    return text


def mask_phones(text: str) -> str:
    return PHONE_PATTERN.sub('[PHONE]', text)

def mask_names(text: str) -> str:
    """Mask person names using spaCy NER.
    Single-word entities matching common tech terms are skipped to avoid
    false positives (e.g. 'Python', 'React')."""
    doc = _nlp(text)

    spans = []
    for ent in doc.ents:
        if ent.label_ != "PERSON":
            continue
        if ent.text.lower() in TECH_TERM_WHITELIST:
            continue
        spans.append((ent.start_char, ent.end_char))

    for start, end in sorted(spans, reverse=True):
        text = text[:start] + "[NAME]" + text[end:]

    return text


def mask_all(text: str) -> str:
    text = _validate_input(text)
    text = mask_emails(text)
    text = mask_phones(text)
    return text