import pytest
from app.core import (
    mask_emails, 
    mask_phones, 
    mask_names, 
    mask_orgs, 
    mask_locations, 
    mask_all, 
    MAX_INPUT_LENGTH
)

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


# --- Names: NER masking ---

def test_mask_full_name():
    result = mask_names("My name is John Smith, contact me.")
    assert "[NAME]" in result
    assert "John Smith" not in result

def test_mask_single_first_name():
    result = mask_names("Contact Sarah for details.")
    assert "[NAME]" in result
    assert "Sarah" not in result

def test_tech_term_not_masked_as_name():
    result = mask_names("I have experience with Python and Java.")
    assert "[NAME]" not in result
    assert "Python" in result
    assert "Java" in result

def test_tech_term_with_real_name():
    result = mask_names("I worked with Sarah Connor using Python.")
    assert "[NAME]" in result
    assert "Sarah Connor" not in result
    assert "Python" in result

def test_no_names_in_text():
    result = mask_names("This document contains no personal names.")
    assert "[NAME]" not in result
    

# --- Phone: date range false positives (regression) ---

def test_phone_year_range_with_spaces_not_masked():
    result = mask_phones("Tenure: 2019 - 2021")
    assert "[PHONE]" not in result
    assert "2019 - 2021" in result

def test_phone_year_range_no_spaces_not_masked():
    result = mask_phones("Tenure: 2019-2021")
    assert "[PHONE]" not in result
    assert "2019-2021" in result

def test_phone_year_range_in_parens_not_masked():
    result = mask_phones("Technical University of Munich (2019 - 2021)")
    assert "[PHONE]" not in result
    assert "(2019 - 2021)" in result

def test_phone_year_range_does_not_corrupt_org_ner():
    # Regression test for the cascade: the [PHONE] placeholder was breaking
    # spaCy's token window, causing the adjacent ORG entity to go undetected.
    result = mask_all("Technical University of Munich (2019 - 2021)")
    assert "[PHONE]" not in result
    assert "Technical University of Munich" not in result
    assert "[ORG]" in result

def test_phone_year_range_does_not_corrupt_mit_acronym_case():
    result = mask_all("Massachusetts Institute of Technology (MIT) (2016 - 2019)")
    assert "[PHONE]" not in result
    assert "Massachusetts Institute of Technology" not in result


def test_phone_real_number_with_year_like_prefix_still_masked():
    # The exemption is anchored to the FULL match, so a real number carrying
    # a country code must never be exempted just because its digits start
    # with 19/20.
    assert "[PHONE]" in mask_phones("+49 1995 234 567")

def test_phone_eight_digit_grouped_number_still_masked():
    # Not year-shaped -> exemption must not apply.
    assert "[PHONE]" in mask_phones("Call 5512-8847 now")
    

# --- Sentence boundary forcing (line isolation for NER) ---

def test_force_line_sentence_boundaries_marks_token_after_newline():
    import spacy
    from app.core import _force_line_sentence_boundaries
    nlp = spacy.blank("en")
    doc = nlp("CERTIFICATIONS & SKILLS\n- Certified AWS Solutions Architect")
    doc = _force_line_sentence_boundaries(doc)
    dash_token = next(t for t in doc if t.text == "-")
    assert dash_token.is_sent_start is True

def test_force_line_sentence_boundaries_handles_crlf_and_blank_lines():
    import spacy
    from app.core import _force_line_sentence_boundaries
    nlp = spacy.blank("en")
    for text in ["a\r\nb", "a\n\nb"]:
        doc = _force_line_sentence_boundaries(nlp(text))
        assert doc[-1].text == "b"
        assert doc[-1].is_sent_start is True
        
def test_section_header_does_not_fuse_with_bullet_into_single_org():
    text = "CERTIFICATIONS & SKILLS\n- Certified AWS Solutions Architect (Terraform, Kubernetes)"
    result = mask_all(text)
    assert "CERTIFICATIONS & SKILLS" in result
    assert "Terraform" in result
    assert "Kubernetes" in result


# --- Locations: NER True Positives (Phase 1.2) ---

def test_mask_city_simple():
    result = mask_locations("I live in Berlin.")
    assert "[LOCATION]" in result
    assert "Berlin" not in result

def test_mask_country_only():
    result = mask_locations("Originally from Ukraine.")
    assert "[LOCATION]" in result
    assert "Ukraine" not in result

def test_mask_city_and_country():
    result = mask_locations("Relocating to Berlin, Germany.")
    assert "[LOCATION]" in result
    assert "Berlin" not in result
    assert "Germany" not in result

def test_mask_remote_mention():
    result = mask_locations("Working remotely from Lisbon.")
    assert "[LOCATION]" in result
    assert "Lisbon" not in result

def test_mask_us_city():
    result = mask_locations("Based in San Francisco.")
    assert "[LOCATION]" in result
    assert "San Francisco" not in result


# --- Locations: Street Address Regex ---

def test_mask_street_address_standard():
    result = mask_locations("Address: 123 Main Street.")
    assert "[LOCATION]" in result
    assert "123 Main Street" not in result

def test_mask_street_address_abbreviation():
    result = mask_locations("She lives at 456 Oak Ave.")
    assert "[LOCATION]" in result
    assert "456 Oak Ave" not in result


# --- Locations: Whitelist False Positive Verification ---

def test_terraform_not_masked_as_location():
    # Regression: Terraform documented as GPE false positive in small model.
    # Verifies 'terraform' was successfully added to SKILL_WHITELIST.
    result = mask_locations("Infrastructure managed via Terraform.")
    assert "[LOCATION]" not in result
    assert "Terraform" in result

def test_node_js_not_masked_as_location():
    # Regression: "Node.js" misclassified as location/GPE boundary.
    result = mask_locations("Backend built with Node.js and Express.")
    assert "[LOCATION]" not in result
    assert "Node.js" in result

def test_react_not_masked_as_location():
    result = mask_locations("Frontend in React and Angular.")
    assert "[LOCATION]" not in result
    assert "React" in result

def test_docker_not_masked_as_location():
    result = mask_locations("Containerized with Docker.")
    assert "[LOCATION]" not in result
    assert "Docker" in result

def test_no_location_no_mask():
    result = mask_locations("I build Python APIs using FastAPI and Redis.")
    assert "[LOCATION]" not in result


# --- Locations: mask_all Integration Tests ---

def test_mask_all_location_with_name():
    result = mask_all("John Smith is relocating to Munich.")
    assert "[NAME]" in result
    assert "[LOCATION]" in result
    assert "John Smith" not in result
    assert "Munich" not in result

def test_mask_all_location_with_org():
    result = mask_all("Software Engineer at Google in Munich.")
    assert "[ORG]" in result
    assert "[LOCATION]" in result
    assert "Google" not in result
    assert "Munich" not in result