import re
import spacy
from spacy.language import Language
from spacy.tokens import Doc
import phonenumbers
from functools import lru_cache

# Load once at module level — loading per-request would be too slow
_nlp = spacy.load("en_core_web_sm")

@Language.component("force_line_sentence_boundaries")
def _force_line_sentence_boundaries(doc: Doc) -> Doc:
    """
    Forces a hard sentence boundary at the start of every structural line.

    en_core_web_sm's sentence segmentation comes from the dependency parser
    and is unreliable on non-prose text — resume-style content (section
    headers, bullet points, no terminal punctuation) frequently gets read
    as one continuous sentence spanning multiple lines.

    This matters because the NER transition system's `In` action (entity
    continuation) explicitly refuses to extend a span across a token with
    sent_start == 1. An undetected sentence break at a line boundary is
    exactly what lets a header like "CERTIFICATIONS & SKILLS" fuse with the
    next bullet line into one giant misclassified ORG span.

    IMPORTANT: spaCy only puts whitespace into a token's `.text` when
    there are 2+ consecutive whitespace characters (e.g. a blank line). A
    single "\n" between two tokens — the normal case for one-line-per-entry
    resume content — lives in the *previous* token's `.whitespace_`, not in
    anyone's `.text`. Checking `.text` alone misses exactly the case this
    component exists to fix, so we check `.text_with_ws` (text + trailing
    whitespace) instead, which covers both single and multi-newline breaks.

    Runs before `ner`: guarantees a sentence start at every newline
    regardless of what the statistical parser inferred.
    """
    for i, token in enumerate(doc):
        if i == 0:
            continue
        if "\n" in doc[i - 1].text_with_ws:
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

# --- Date / Age Patterns ---

_TRIGGER_SEP = r'(?:\s*[:,\-–—]\s*|\s+)'

_MONTH_NAMES = (
    r'(?:January|February|March|April|May|June|July|August|September|'
    r'October|November|December|'
    r'Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Oct\.?|Nov\.?|Dec\.?)'
)

_ORD = r'(?:st|nd|rd|th)?'

_DATE_VALUE = (
    r'(?:'
    r'\d{4}-\d{2}-\d{2}'                          # ISO (YYYY-MM-DD)
    r'|\d{1,2}\.\d{1,2}\.\d{4}'                   # DD.MM.YYYY
    r'|\d{1,2}/\d{1,2}/\d{4}'                     # MM/DD/YYYY
    r'|' + _MONTH_NAMES + r'\s+\d{1,2}' + _ORD + r',?\s*\d{4}'   # Month DD, YYYY
    r'|\d{1,2}' + _ORD + r'\s+' + _MONTH_NAMES + r'\s+\d{4}'     # DD Month YYYY
    r')'
)

DOB_PATTERN = re.compile(
    r'(?P<trigger>'
    r'(?:born|d\.o\.b\.?|dob|date\s+of\s+birth|birthd(?:ay|ate))'
    + _TRIGGER_SEP +
    r')'
    r'(?P<date>' + _DATE_VALUE + r')',
    re.IGNORECASE,
)

AGE_LABEL_PATTERN = re.compile(
    r'(?P<trigger>\bage\s*(?::\s*|\s+))'
    r'(?P<age>\d{1,3})'
    r'(?!\.\d)'  # Protection: do not mask the integer part of floats (e.g., Age: 25.5)
    r'(?=\s*(?:years?)?(?:\s+old)?\b|\s|$)',
    re.IGNORECASE,
)

AGE_TRAILING_PATTERN = re.compile(
    r'(?<!\.)'  # Protection: do not mask the fractional part of floats (e.g., 25.5 years old)
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

@lru_cache(maxsize=128)
def is_valid_phone(text: str) -> bool:
    try:
        region = None if text.strip().startswith('+') else "DE"
        parsed = phonenumbers.parse(text, region)
        
        is_valid = phonenumbers.is_possible_number(parsed)
        
        if not is_valid:
            print(f"DEBUG: Rejected phone candidate: '{text}'") 
        return is_valid
    except phonenumbers.NumberParseException:
        return False
    
# --- Masking Functions ---

def mask_emails(text: str) -> str:
    text = OBFUSCATED_EMAIL_PATTERN.sub('[EMAIL]', text)
    text = EMAIL_PATTERN.sub('[EMAIL]', text)
    return text

def mask_phones(text: str) -> str:
    def _replace(match: re.Match) -> str:
        matched = match.group(0)
        
        # Keep year ranges unmasked
        if PHONE_YEAR_RANGE_PATTERN.match(matched):
            return matched
            
        # Use library as a filter
        if is_valid_phone(matched):
            return '[PHONE]'
            
        # If not a valid phone, return original text
        return matched
        
    return PHONE_PATTERN.sub(_replace, text)

_PLACEHOLDER = {
    "PERSON": "[NAME]",
    "GPE": "[LOCATION]",
    "LOC": "[LOCATION]",
    "ORG": "[ORG]"
}


def _mask_entities(text: str, allowed_labels: set[str]) -> str:
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
    # 1. DOB label + date value (label preserved)
    def _replace_dob(m: re.Match) -> str:
        return m.group('trigger') + '[DATE]'

    text = DOB_PATTERN.sub(_replace_dob, text)

    # 2. Age label — Evaluates a realistic upper limit of 120 years
    def _replace_age_label(m: re.Match) -> str:
        try:
            if int(m.group('age')) <= 120:
                return m.group('trigger') + '[DATE]'
        except ValueError:
            pass
        return m.group(0)

    text = AGE_LABEL_PATTERN.sub(_replace_age_label, text)

    # 3. Trailing "N years old" / "N-year-old"
    def _replace_age_trailing(m: re.Match) -> str:
        try:
            if int(m.group('age')) <= 120:
                return '[DATE]' + m.group('suffix')
        except ValueError:
            pass
        return m.group(0)

    text = AGE_TRAILING_PATTERN.sub(_replace_age_trailing, text)

    return text


def mask_all(text: str, mode: str = "full", mask_dob: bool = True) -> str:
    """
    mode="full": Regex + NER (Names, Orgs, Locations)
    mode="fast": Only Regex (Emails, Phones, Dates)
    """
    text = _validate_input(text)

    # Run FIRST to protect dates from phone/NER masking
    if mask_dob:
        text = mask_dates(text)
    text = mask_emails(text)
    text = mask_phones(text)

    # NER — only executed if "full" mode is requested.
    # Run as a SINGLE combined pass instead of three separate mask_names/
    # mask_orgs/mask_locations calls: each of those re-tokenizes the text
    # with spaCy from scratch, and doing it three times in sequence means
    # passes 2 and 3 run NER on text that already contains [NAME]/[ORG]
    # placeholders from the previous pass — which shifts offsets and can
    # change how the parser reads surrounding context. One pass is both
    # ~3x faster (matters on the CX23) and avoids that placeholder-induced
    # drift.
    if mode == "full":
        text = STREET_ADDRESS_PATTERN.sub("[LOCATION]", text)
        text = _mask_entities(text, {"PERSON", "ORG", "GPE", "LOC"})

    return text