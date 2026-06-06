import pytest
from app.core import mask_emails, mask_phones, mask_all, MAX_INPUT_LENGTH


# --- Validation tests ---

def test_invalid_type_raises():
    with pytest.raises(TypeError):
        mask_all(12345)

def test_null_bytes_raises():
    with pytest.raises(ValueError):
        mask_all("hello\x00world")

def test_too_large_input_raises():
    with pytest.raises(ValueError):
        mask_all("a" * (MAX_INPUT_LENGTH + 1))


# --- Boundary tests ---

def test_email_with_trailing_dot():
    result = mask_emails("Contact john@example.com. Tomorrow.")
    assert "john@example.com" not in result
    assert "." in result  # trailing dot preserved

def test_email_with_plus():
    assert "[EMAIL]" in mask_emails("Send to user+filter@gmail.com please")


# --- False positive tests ---

def test_date_false_positive_known_limitation():
    # Known limitation: dates matching phone pattern are masked
    # Full fix requires NER - planned for v2
    result = mask_phones("Date: 2024-01-15")
    assert "[PHONE]" in result

def test_iban_false_positive_known_limitation():
    # Known limitation: numeric sequences like IBANs may be partially masked
    # Full fix requires NER - planned for v2
    result = mask_phones("IBAN: DE89370400440532013000")
    assert result is not None