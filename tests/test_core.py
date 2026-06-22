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
    
"""
Phase 1.3 — mask_dates() hardened test suite.

These tests cover behaviour introduced or changed in the hardened core.py
and are explicitly non-overlapping with the tests already in test_core.py.

Append this file's content to tests/test_core.py and add `mask_dates`
to the existing import if not already present:

    from app.core import (
        ...,
        mask_dates,
        ...,
    )
"""

import pytest
from app.core import mask_dates, mask_all


# -----------------------------------------------------------------------
# AGE LABEL — no-colon variant (space-only separator)
# AGE_LABEL_PATTERN: \bage\s*(?::\s*|\s+) — colon is now optional
# -----------------------------------------------------------------------

def test_age_label_no_colon_space_separator():
    """'Age 34' with no colon — hardened pattern accepts space-only trigger."""
    result = mask_dates("Age 34")
    assert "[DATE]" in result
    assert "34" not in result
    # "Age" label must survive
    assert "Age" in result


def test_age_label_no_colon_with_years_suffix():
    """'Age 28 years' — space separator, no colon."""
    result = mask_dates("Candidate age 28 years, available immediately.")
    assert "[DATE]" in result
    assert "28" not in result


def test_age_label_no_colon_uppercase():
    result = mask_dates("AGE 45")
    assert "[DATE]" in result
    assert "45" not in result


# -----------------------------------------------------------------------
# AGE GUARD — values > 120 must NOT be masked
# Both AGE_LABEL_PATTERN and AGE_TRAILING_PATTERN enforce int(age) <= 120
# -----------------------------------------------------------------------

def test_age_label_exactly_120_is_masked():
    """Boundary value: 120 is a valid (if extreme) age and must be masked."""
    result = mask_dates("Age: 120")
    assert "[DATE]" in result
    assert "120" not in result


def test_age_label_121_not_masked():
    """121 exceeds the guard — must be left untouched."""
    result = mask_dates("Age: 121")
    assert "[DATE]" not in result
    assert "121" in result


def test_age_label_999_not_masked():
    """Three-digit number well above 120 — guard must fire."""
    result = mask_dates("Age: 999")
    assert "[DATE]" not in result
    assert "999" in result


def test_age_trailing_121_not_masked():
    """Guard applies to trailing pattern too: '121 years old' is not a real age."""
    result = mask_dates("The system has been running for 121 years old.")
    # Grammatically odd but the guard is the important thing here
    assert "[DATE]" not in result
    assert "121" in result


def test_age_trailing_exactly_120_is_masked():
    result = mask_dates("She is 120 years old.")
    assert "[DATE]" in result
    assert "120" not in result
    assert "years old" in result


def test_age_label_zero_is_masked():
    """Age 0 is valid in medical/childcare HR contexts."""
    result = mask_dates("Age: 0")
    assert "[DATE]" in result


# -----------------------------------------------------------------------
# DOB — abbreviated month with trailing period (Jan., Feb., etc.)
# _MONTH_NAMES now includes Jan\.? so "Jan." and "Jan" both match
# -----------------------------------------------------------------------

def test_dob_abbreviated_month_with_period():
    """'Jan.' with trailing period — hardened _MONTH_NAMES handles this."""
    result = mask_dates("DOB: Jan. 5, 2000")
    assert "[DATE]" in result
    assert "Jan. 5, 2000" not in result
    assert "DOB:" in result


def test_dob_abbreviated_month_feb_with_period():
    result = mask_dates("born Feb. 14, 1995")
    assert "[DATE]" in result
    assert "Feb. 14, 1995" not in result


def test_dob_abbreviated_month_dec_with_period():
    result = mask_dates("Birthdate: Dec. 31, 1980")
    assert "[DATE]" in result
    assert "Dec. 31, 1980" not in result


# -----------------------------------------------------------------------
# DOB — en-dash and em-dash separators
# _TRIGGER_SEP: (?:\s*[:,\-–—]\s*|\s+) — explicitly includes – and —
# -----------------------------------------------------------------------

def test_dob_trigger_en_dash_separator():
    """En-dash between trigger and date."""
    result = mask_dates("born – 15.03.1990")
    assert "[DATE]" in result
    assert "15.03.1990" not in result


def test_dob_trigger_em_dash_separator():
    """Em-dash between trigger and date."""
    result = mask_dates("DOB — 1990-03-15")
    assert "[DATE]" in result
    assert "1990-03-15" not in result
    assert "DOB" in result


def test_dob_trigger_en_dash_month_name():
    result = mask_dates("Birthday – March 15, 1990")
    assert "[DATE]" in result
    assert "March 15, 1990" not in result


# -----------------------------------------------------------------------
# DOB — 'd.o.b' without trailing dot (the trailing dot is optional: d\.o\.b\.?)
# -----------------------------------------------------------------------

def test_dob_trigger_d_o_b_no_trailing_dot():
    """'d.o.b' without the final period — pattern uses \.? so this must match."""
    result = mask_dates("d.o.b 01.01.1985")
    assert "[DATE]" in result
    assert "01.01.1985" not in result


def test_dob_trigger_d_o_b_colon_no_trailing_dot():
    result = mask_dates("d.o.b: 1985-01-01")
    assert "[DATE]" in result
    assert "1985-01-01" not in result


# -----------------------------------------------------------------------
# DOB — 'born:' with explicit colon (not yet in existing suite)
# -----------------------------------------------------------------------

def test_dob_trigger_born_with_colon():
    """'born:' — colon immediately after the trigger word."""
    result = mask_dates("born: 22.07.1993")
    assert "[DATE]" in result
    assert "22.07.1993" not in result
    assert "born:" in result


# -----------------------------------------------------------------------
# Multiline text — DOB on its own line, ranges on adjacent lines
# -----------------------------------------------------------------------

def test_multiline_dob_only_line_masked():
    """DOB line is masked; employment line on the adjacent line is untouched."""
    text = "Software Engineer, 2018-2022\nDOB: 15.03.1990\nBerlin, Germany"
    result = mask_dates(text)
    assert "[DATE]" in result
    assert "15.03.1990" not in result
    # Employment range must survive
    assert "2018-2022" in result


def test_multiline_multiple_safe_ranges_with_one_dob():
    text = (
        "Work Experience\n"
        "Acme Corp: 2019-2021\n"
        "Beta Ltd: 2021-2023\n"
        "Personal Data\n"
        "Date of Birth: 01/01/1990"
    )
    result = mask_dates(text)
    assert "[DATE]" in result
    assert "01/01/1990" not in result
    assert "2019-2021" in result
    assert "2021-2023" in result


# -----------------------------------------------------------------------
# mask_dob=False — age trailing case (gap in existing suite)
# -----------------------------------------------------------------------

def test_mask_all_dob_opt_out_age_trailing():
    """mask_dob=False must also leave 'N years old' untouched."""
    result = mask_all("The applicant is 34 years old.", mask_dob=False)
    assert "[DATE]" not in result
    assert "34 years old" in result


def test_mask_all_dob_opt_out_age_label_no_colon():
    """mask_dob=False with space-separator age label."""
    result = mask_all("Age 29, available from Berlin.", mask_dob=False)
    assert "[DATE]" not in result
    assert "29" in result


# -----------------------------------------------------------------------
# mask_dates purity — function returns input unchanged when no PII present
# -----------------------------------------------------------------------

def test_mask_dates_no_pii_returns_identical_string():
    """mask_dates must be a no-op when no patterns fire — value equality."""
    text = "Experienced developer, 5 years in Python, based in Hamburg."
    assert mask_dates(text) == text


def test_mask_dates_empty_string_returns_empty():
    assert mask_dates("") == ""


def test_mask_dates_whitespace_only():
    """Pure whitespace — no pattern should fire."""
    assert mask_dates("   \n\t  ") == "   \n\t  "


# -----------------------------------------------------------------------
# Co-occurrence: DOB alongside other PII types — mask_all integration
# -----------------------------------------------------------------------

def test_mask_all_dob_and_phone_coexist():
    """DOB and phone in the same string — both masked, no interference."""
    text = "DOB: 15.03.1990, Phone: +49 151 12345678"
    result = mask_all(text)
    assert "[DATE]" in result
    assert "15.03.1990" not in result
    assert "[PHONE]" in result
    assert "+49 151 12345678" not in result


def test_mask_all_dob_and_email_coexist():
    text = "Contact hr@company.com — DOB: 01/01/1985"
    result = mask_all(text)
    assert "[DATE]" in result
    assert "01/01/1985" not in result
    assert "[EMAIL]" in result
    assert "hr@company.com" not in result


def test_mask_all_age_label_and_name_coexist():
    text = "Applicant: Jane Doe, Age: 29"
    result = mask_all(text)
    assert "[DATE]" in result
    assert "29" not in result
    # Name must also be masked by NER
    assert "Jane Doe" not in result


# -----------------------------------------------------------------------
# Regression guard — confirm safe values that are numerically near the
# age guard boundary are not accidentally caught by other patterns
# -----------------------------------------------------------------------

def test_year_1990_standalone_not_masked():
    """A standalone 4-digit year with no trigger is not PII."""
    result = mask_dates("Founded in 1990.")
    assert "[DATE]" not in result
    assert "1990" in result


def test_number_34_standalone_not_masked():
    """Bare number with no 'age' trigger and no 'years old' suffix is not PII."""
    result = mask_dates("We have 34 open positions.")
    assert "[DATE]" not in result
    assert "34" in result


def test_version_number_not_masked():
    """Version strings must not be mistaken for ages."""
    result = mask_dates("Running Python 3 on 34 servers.")
    assert "[DATE]" not in result
    assert "34" in result
    
# -----------------------------------------------------------------------
# HARDENING REPRESSION TESTS — Explicit validation for past leak vectors
# -----------------------------------------------------------------------

def test_dob_space_before_colon_leak_protection():
    """CRITICAL: Space before colon (e.g. 'DOB :') must be caught safely."""
    result = mask_dates("DOB : 15.03.1990")
    assert "[DATE]" in result
    assert "15.03.1990" not in result
    assert "DOB :" in result


def test_dob_lowercase_abbreviated_month_with_period():
    """Case insensitivity combined with trailing period abbreviation."""
    result = mask_dates("born jan. 15, 1990")
    assert "[DATE]" in result
    assert "jan. 15, 1990" not in result


def test_age_label_space_before_colon():
    """Validates space-before-colon layout for age fields."""
    result = mask_dates("Age : 25")
    assert "[DATE]" in result
    assert "25" not in result
    assert "Age :" in result


def test_age_guard_string_floats_handled_safely():
    """Ensures age strings that aren't clean integers don't crash the lambda inside mask_dates."""
    # This shouldn't match AGE_LABEL_PATTERN due to \d{1,3}, but if it ever bypasses, 
    # the int() conversion inside must catch it via try/except.
    result = mask_dates("Age: 25.5")
    assert "25.5" in result  # Should pass through safely or lookups skip it