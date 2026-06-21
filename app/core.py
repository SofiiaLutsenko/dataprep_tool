import re
import spacy
from spacy.language import Language
from spacy.tokens import Doc

# Load once at module level — loading per-request would be too slow
_nlp = spacy.load("en_core_web_sm")

@Language.component("force_line_sentence_boundaries")
def _force_line_sentence_boundaries(doc: Doc) -> Doc:
    """
    Forces a hard sentence boundary at the start of every structural line.

    en_core_web_sm's sentence segmentation comes from the dependency parser
    and is unreliable on non-prose text -- resume-style content (section
    headers, bullet points, no terminal punctuation) frequently gets read
    as one continuous sentence spanning multiple lines.

    This matters because the NER transition system's `In` action (entity
    continuation) explicitly refuses to extend a span across a token with
    sent_start == 1 -- see spacy/pipeline/_parser_internals/ner.pyx. An
    undetected sentence break at a line boundary is exactly what lets a
    header like "CERTIFICATIONS & SKILLS" fuse with the next bullet line
    into one giant misclassified ORG span.

    Runs before `ner`: guarantees a sentence start at every newline
    regardless of what the statistical parser inferred, so the NER
    component's own boundary-respecting logic does the rest. No change to
    _mask_entities() is needed -- it already just calls _nlp(text) once.
    """
    for i, token in enumerate(doc):
        if i == 0:
            continue
        if "\n" in doc[i - 1].text:
            token.is_sent_start = True
    return doc

_nlp.add_pipe("force_line_sentence_boundaries", before="parser")

# Common tech terms, skills, and resume vocabulary that spaCy's small model
# frequently misclassifies as PERSON, ORG, GPE, or DATE entities.
SKILL_WHITELIST = {
    "python", "java", "javascript", "typescript", "react", "angular", "vue",
    "node", "django", "flask", "fastapi", "spring", "docker", "kubernetes",
    "aws", "azure", "git", "github", "gitlab", "linux", "windows", "mongodb",
    "postgresql", "mysql", "redis", "graphql", "rest", "html", "css", "sql",
    "swift", "kotlin", "golang", "rust", "scala", "ruby", "php", "c++", "c#",
    "computer science", "data science", "machine learning", "machine learning", "certifications & skills",
    "professional experience",
    "education"
}

MAX_INPUT_LENGTH = 100_000

# --- PII Patterns ---

# EMAIL: 
EMAIL_PATTERN = re.compile(
    r'(?<![a-zA-Z0-9._%+\-])'
    r'(?!\S*\.\.)'
    r'[a-zA-Z0-9._%+\-]+'
    r'\s*@\s*'
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

# YEAR RANGE FALSE POSITIVE: checked against the FULL phone match, not the
# raw input text. A match can only equal this shape if it carries no
# country code, no area-code parens, and no extension — structurally it's
# nothing but two bare 19xx/20xx numbers joined by a hyphen. A real phone
# number can never satisfy this anchor, so this cannot introduce new false
# negatives — it can only exempt things that were never phone numbers.
PHONE_YEAR_RANGE_PATTERN = re.compile(r'^(?:19|20)\d{2}\s*-\s*(?:19|20)\d{2}$')


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


def _mask_entities(text: str, allowed_labels: set[str]) -> str:
    """Generic entity masking helper. Replaces entities whose label is in
    allowed_labels with [LABEL], skipping anything in the skill whitelist.
    Включает пост-обработку для защиты ошибочно захваченных глаголов."""
    doc = _nlp(text)
    spans = []

    for ent in doc.ents:
        if ent.label_ not in allowed_labels:
            continue
        if ent.text.strip().lower() in SKILL_WHITELIST:
            continue

        start_char = ent.start_char
        end_char = ent.end_char

        # Корректировка границ NER: удаляем случайно захваченные начальные глаголы/предлоги
        for token in ent:
            if token.text.lower() in {"call", "write", "email", "contact", "to", "copy", "paste", "upload", "verify", "enter"}:
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

def mask_orgs(text: str) -> str:
    return _mask_entities(text, {"ORG"})


def mask_all(text: str) -> str:
    text = _validate_input(text)
    text = mask_emails(text)
    text = mask_phones(text)
    text = mask_names(text) # Теперь имена точно маскируются
    text = mask_orgs(text)
    return text

def mask_phones(text: str) -> str:
    def _replace(match: re.Match) -> str:
        matched = match.group(0)
        if PHONE_YEAR_RANGE_PATTERN.match(matched):
            return matched  # bare year range (e.g. resume dates), not a phone number
        return '[PHONE]'
    return PHONE_PATTERN.sub(_replace, text)