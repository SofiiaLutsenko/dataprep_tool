import re
import spacy

# Load once at module level — loading per-request would be too slow
_nlp = spacy.load("en_core_web_sm")

# Common tech terms, skills, and resume vocabulary that spaCy's small model
# frequently misclassifies as PERSON, ORG, GPE, or DATE entities.
SKILL_WHITELIST = {
    "python", "java", "javascript", "typescript", "react", "angular", "vue",
    "node", "django", "flask", "fastapi", "spring", "docker", "kubernetes",
    "aws", "azure", "git", "github", "gitlab", "linux", "windows", "mongodb",
    "postgresql", "mysql", "redis", "graphql", "rest", "html", "css", "sql",
    "swift", "kotlin", "golang", "rust", "scala", "ruby", "php", "c++", "c#",
    "computer science", "data science", "machine learning",
}

MAX_INPUT_LENGTH = 100_000

# --- PII Patterns ---

# EMAIL: Строгий паттерн без пробелов вокруг @
EMAIL_PATTERN = re.compile(
    r'(?<![a-zA-Z0-9._%+\-])'
    r'(?!\S*\.\.)'
    r'[a-zA-Z0-9._%+\-]+'
    r'@'
    r'[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
    r'(?=[^a-zA-Z0-9]|$)',
    re.IGNORECASE
)

# OBFUSCATED EMAIL: user [at] domain.com / user(at)domain[dot]com
OBFUSCATED_EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+\-]+'
    r'\s*(?:\[at\]|\(at\))\s*'
    r'[a-zA-Z0-9.\-]+'
    r'\s*(?:\[dot\]|\(dot\)|\.)\s*'
    r'[a-zA-Z]{2,}',
    re.IGNORECASE
)

# PHONE: E.164, European 00-prefix, separators, brackets, extensions
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


def _mask_entities(text: str, allowed_labels: set[str]) -> str:
    """Generic entity masking helper. Replaces entities whose label is in
    allowed_labels with [LABEL], skipping anything in the skill whitelist.
    Включает пост-обработку для защиты ошибочно захваченных глаголов."""
    doc = _nlp(text)
    spans = []

    for ent in doc.ents:
        if ent.label_ not in allowed_labels:
            continue
        if ent.text.lower() in SKILL_WHITELIST:
            continue

        start_char = ent.start_char
        end_char = ent.end_char

        # Корректировка границ NER: удаляем случайно захваченные начальные глаголы/предлоги
        for token in ent:
            if token.pos_ in {"VERB", "ADP"} or token.text.lower() in {"call", "write", "email", "contact", "to"}:
                # Сдвигаем начало маски за пределы этого токена
                start_char = token.idx + len(token.text)
                # Пропускаем пробелы после очищенного слова
                while start_char < len(text) and text[start_char].isspace():
                    start_char += 1
            else:
                # Как только дошли до реального имени (NOUN/PROPN) — останавливаемся
                break

        if start_char < end_char:
            spans.append((start_char, end_char, ent.label_))

    # Безопасная замена с конца строки с защитой от наложений
    last_start = len(text) + 1
    for start, end, label in sorted(spans, key=lambda x: x[0], reverse=True):
        if end > last_start:
            continue
        
        placeholder = f"[{label}]" if label != "PERSON" else "[NAME]"
        text = text[:start] + placeholder + text[end:]
        last_start = start

    return text


def mask_names(text: str) -> str:
    return _mask_entities(text, {"PERSON"})


def mask_all(text: str) -> str:
    text = _validate_input(text)
    text = mask_emails(text)
    text = mask_phones(text)
    text = mask_names(text) # Теперь имена точно маскируются
    return text