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
    "computer science", "data science", "machine learning", "certifications & skills",
    "professional experience", "education", "terraform", "node.js"
}

MAX_INPUT_LENGTH = 30_000  # 30 KB

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

# YEAR RANGE FALSE POSITIVE: checked against the FULL phone match.
PHONE_YEAR_RANGE_PATTERN = re.compile(r'^(?:19|20)\d{2}\s*-\s*(?:19|20)\d{2}$')

# STREET ADDRESS: number + 1-3 word street name + known suffix
STREET_ADDRESS_PATTERN = re.compile(
    r'\b\d{1,5}'
    r'\s+'
    r'(?:[A-Za-z]+\s+){1,3}'
    r'(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|'
    r'Lane|Ln|Way|Court|Ct|Place|Pl|Square|Sq)'
    r'\.?'
    r'(?=[\s,.]|$)',
    re.IGNORECASE
)

# --- Date / Age Patterns (Phase 1.3 Hardened) ---

# Secure separator handling optional colons/dashes and whitespace variables on BOTH sides
_TRIGGER_SEP = r'(?:\s*[:,\-–—]\s*|\s+)'

# Appended optional periods `\.?` to explicitly capture standard US prose abbreviations ("Jan.", "Feb.")
_MONTH_NAMES = (
    r'(?:January|February|March|April|May|June|July|August|September|'
    r'October|November|December|'
    r'Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Oct\.?|Nov\.?|Dec\.?)'
)

_ORD = r'(?:st|nd|rd|th)?'

# All branches require a 4-digit year to cleanly decouple from experience ranges like "2019-2022"
_DATE_VALUE = (
    r'(?:'
    r'\d{4}-\d{2}-\d{2}'                                          # 1. ISO (YYYY-MM-DD)
    r'|\d{1,2}\.\d{1,2}\.\d{4}'                                   # 2. DD.MM.YYYY
    r'|\d{1,2}/\d{1,2}/\d{4}'                                     # 3. MM/DD/YYYY
    r'|' + _MONTH_NAMES + r'\s+\d{1,2}' + _ORD + r',?\s*\d{4}'   # 4. Month DD, YYYY
    r'|\d{1,2}' + _ORD + r'\s+' + _MONTH_NAMES + r'\s+\d{4}'      # 5. DD Month YYYY
    r')'
)

# Matches a DOB trigger label followed directly by a validated date value format
DOB_PATTERN = re.compile(
    r'(?P<trigger>'
    r'(?:born|d\.o\.b\.?|dob|date\s+of\s+birth|birthd(?:ay|ate))'
    + _TRIGGER_SEP +
    r')'
    r'(?P<date>' + _DATE_VALUE + r')',
    re.IGNORECASE,
)

# Matches explicit labels including spaces or missing colons ("Age 34")
AGE_LABEL_PATTERN = re.compile(
    r'(?P<trigger>\bage\s*(?::\s*|\s+))'
    r'(?P<age>\d{1,3})'
    r'(?!\.\d)'  # Защита: не маскируем целую часть флоатов (например, Age: 25.5)
    r'(?=\s*(?:years?)?(?:\s+old)?\b|\s|$)',
    re.IGNORECASE,
)

# Matches the trailing descriptive age layout ("34 years old", "28-year-old")
AGE_TRAILING_PATTERN = re.compile(
    r'(?<!\.)'  # Защита: не маскируем дробную часть флоатов (например, 25.5 years old)
    r'(?P<age>\d{1,3})'
    r'(?P<suffix>[ \t]*-?years?[ \t]*-?old)',
    re.IGNORECASE,
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
    def _replace(match: re.Match) -> str:
        matched = match.group(0)
        if PHONE_YEAR_RANGE_PATTERN.match(matched):
            return matched
        return '[PHONE]'
    return PHONE_PATTERN.sub(_replace, text)


def _mask_entities(text: str, allowed_labels: set[str]) -> str:
    """Generic entity masking helper. Replaces entities whose label is in
    allowed_labels with [LABEL], skipping anything in the skill whitelist."""
    doc = _nlp(text)
    spans = []

    for ent in doc.ents:
        if ent.label_ not in allowed_labels:
            continue
        if ent.text.strip().lower() in SKILL_WHITELIST:
            continue

        start_char = ent.start_char
        end_char = ent.end_char

        # NER boundary correction: strip out accidentally captured leading verbs/prepositions
        for token in ent:
            if token.text.lower() in {"call", "write", "email", "contact", "to", "copy", "paste", "upload", "verify", "enter"}:
                start_char = token.idx + len(token.text)
                while start_char < len(text) and text[start_char].isspace():
                    start_char += 1
            else:
                break

        if start_char < end_char:
            spans.append((start_char, end_char, ent.label_))

    last_start = len(text) + 1
    
    _PLACEHOLDER = {
        "PERSON": "[NAME]", 
        "GPE": "[LOCATION]", 
        "LOC": "[LOCATION]",
        "ORG": "[ORG]"
    }
    
    for start, end, label in sorted(spans, key=lambda x: x[0], reverse=True):
        if end > last_start:
            continue
        
        placeholder = _PLACEHOLDER.get(label, f"[{label}]")
        text = text[:start] + placeholder + text[end:]
        last_start = start

    return text


def mask_names(text: str) -> str:
    return _mask_entities(text, {"PERSON"})

def mask_orgs(text: str) -> str:
    return _mask_entities(text, {"ORG"})

def mask_locations(text: str) -> str:
    text = STREET_ADDRESS_PATTERN.sub("[LOCATION]", text)
    return _mask_entities(text, {"GPE", "LOC"})


def mask_dates(text: str) -> str:
    """
    Masks dates of birth and explicit age declarations using deterministic regex.
    Protects employment duration records and baseline framework terms.
    """
    # 1. DOB label + date value (label preserved)
    def _replace_dob(m: re.Match) -> str:
        return m.group('trigger') + '[DATE]'

    text = DOB_PATTERN.sub(_replace_dob, text)

    # 2. Age label — Evaluates a realistic upper limit of 120 years to isolate data
    def _replace_age_label(m: re.Match) -> str:
        try:
            if int(m.group('age')) <= 120:
                return m.group('trigger') + '[DATE]'
        except ValueError:
            pass
        return m.group(0)

    text = AGE_LABEL_PATTERN.sub(_replace_age_label, text)

    # 3. Trailing "N years old" / "N-year-old" (suffix context preserved)
    def _replace_age_trailing(m: re.Match) -> str:
        try:
            if int(m.group('age')) <= 120:
                return '[DATE]' + m.group('suffix')
        except ValueError:
            pass
        return m.group(0)

    text = AGE_TRAILING_PATTERN.sub(_replace_age_trailing, text)

    return text


def mask_all(text: str, mask_dob: bool = True) -> str:
    text = _validate_input(text)
    if mask_dob:
        text = mask_dates(text)  # Запускаем ПЕРВЫМ, чтобы защитить даты от маски телефонов и NER
    text = mask_emails(text)
    text = mask_phones(text)
    text = mask_names(text)
    text = mask_orgs(text)
    text = mask_locations(text)
    return text