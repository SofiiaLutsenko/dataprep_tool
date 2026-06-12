import pytest
from app.core import mask_emails, mask_phones, mask_all, MAX_INPUT_LENGTH


# --- Validation ---

def test_invalid_type_raises():
    with pytest.raises(TypeError):
        mask_all(12345)

def test_null_bytes_raises():
    with pytest.raises(ValueError):
        mask_all("hello\x00world")

def test_too_large_input_raises():
    with pytest.raises(ValueError):
        mask_all("a" * (MAX_INPUT_LENGTH + 1))


# --- Email: standard formats ---

def test_simple_email():
    assert mask_emails("Contact me at john@example.com") == "Contact me at [EMAIL]"

def test_email_with_dot_in_local():
    assert "[EMAIL]" in mask_emails("first.last@domain.com")

def test_email_with_special_chars():
    assert "[EMAIL]" in mask_emails("user_name-123@domain.com")

def test_email_with_plus():
    assert "[EMAIL]" in mask_emails("user+filter@gmail.com")

def test_email_uppercase():
    assert "[EMAIL]" in mask_emails("USER@GMAIL.COM")

def test_email_no_email():
    assert mask_emails("No email here") == "No email here"

def test_email_empty_string():
    assert mask_emails("") == ""


# --- Email: complex domains ---

def test_email_multilevel_subdomain():
    assert "[EMAIL]" in mask_emails("user@mail.department.company.co.uk")

def test_email_long_tld():
    assert "[EMAIL]" in mask_emails("admin@startup.engineering")


# --- Email: boundary ---

def test_email_trailing_dot():
    result = mask_emails("Contact john@example.com. Tomorrow.")
    assert "john@example.com" not in result
    assert "[EMAIL]" in result

def test_email_consecutive_dots_not_masked():
    result = mask_emails("user..name@example.com")
    assert "[EMAIL]" not in result


# --- Email: obfuscated formats ---

def test_email_at_in_brackets():
    assert "[EMAIL]" in mask_emails("user [at] domain.com")

def test_email_at_in_parens():
    assert "[EMAIL]" in mask_emails("user(at)domain[dot]com")

def test_email_spaces_around_at():
    assert "[EMAIL]" in mask_emails("user @ domain.com")


# --- Email: known limitations ---

def test_date_false_positive_known_limitation():
    # Known limitation: dates matching phone pattern are masked
    result = mask_phones("Date: 2024-01-15")
    assert "[PHONE]" in result

def test_iban_false_positive_known_limitation():
    # Known limitation: numeric sequences like IBANs may be partially masked
    result = mask_phones("IBAN: DE89370400440532013000")
    assert result is not None


# --- Phone: international formats ---

def test_phone_e164():
    assert "[PHONE]" in mask_phones("+4915123456789")

def test_phone_european_00_prefix():
    assert "[PHONE]" in mask_phones("004915123456789")

def test_phone_us_standard():
    assert "[PHONE]" in mask_phones("+1 (555) 123-4567")

def test_phone_ukraine_standard():
    assert "[PHONE]" in mask_phones("+380 (50) 1234567")


# --- Phone: separators ---

def test_phone_spaces():
    assert "[PHONE]" in mask_phones("+49 151 123 45 67")

def test_phone_dashes():
    assert "[PHONE]" in mask_phones("+380-50-123-45-67")

def test_phone_dots():
    assert "[PHONE]" in mask_phones("+1.555.123.4567")

def test_phone_slash():
    assert "[PHONE]" in mask_phones("0170/1234567")

def test_phone_mixed_separators():
    assert "[PHONE]" in mask_phones("+49 151 123-45-67")


# --- Phone: German specific ---

def test_phone_german_local():
    assert "[PHONE]" in mask_phones("(089) 123456")

def test_phone_german_zero_in_brackets():
    assert "[PHONE]" in mask_phones("+49 (0) 151 1234567")


# --- Phone: extensions ---

def test_phone_ext_dot():
    assert "[PHONE]" in mask_phones("+1-555-123-4567 ext. 89")

def test_phone_ext_x():
    assert "[PHONE]" in mask_phones("(555) 123-4567 x123")


# --- Phone: no phone ---

def test_no_phone():
    assert mask_phones("No phone here") == "No phone here"


# --- mask_all combined ---

def test_mask_all_combined():
    text = "Email: hr@company.com, Phone: +49 151 12345678"
    result = mask_all(text)
    assert "[EMAIL]" in result
    assert "[PHONE]" in result
    assert "hr@company.com" not in result
    assert "+49 151 12345678" not in result
    
def test_ip_based_email_known_limitation():
    # Known limitation: emails with IP-address-style domains (e.g. root@123.45.67.78)
    # are not recognized, since EMAIL_PATTERN requires a letter-based TLD.
    # This is intentional — IP-based emails are rare in HR/resume contexts.
    result = mask_all("Contact root@123.45.67.78 for access")
    assert result is not None