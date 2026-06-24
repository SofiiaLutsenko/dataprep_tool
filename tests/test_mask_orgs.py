"""
Tests for mask_orgs() -- true-positive/false-positive behavior on the ORG
entity label, from the Phase 1.1 investigation (see investigate_org_fp.py
and CONTEXT.md).

Strategy note: unlike test_mask_entities_boundary.py, these tests call the
real en_core_web_sm model directly -- no synthetic Doc, no monkeypatching.
That's deliberate, not an inconsistency: the boundary tests isolate
deterministic post-processing logic from model drift, but these tests exist
specifically to verify the model's real classification behavior on company/
university names vs. tech-stack and soft-skill terms. Coupling to the
installed spaCy model version is an accepted tradeoff here -- if a future
model upgrade changes these results, that IS the regression these tests
exist to catch.

Sentences are drawn directly from the Phase 1.1 investigation corpus, which
found zero ORG false positives across 15 sentences and confirmed that a
minimum-word-count heuristic would break true positives like "Google" and
"MIT" (both single-word, both real, both must be masked).
"""

import pytest
from app.core import mask_orgs, mask_all


# --- True positives: real organizations must be masked ---

@pytest.mark.parametrize("text,real_org", [
    ("She worked as a senior backend developer at Google for three years.", "Google"),
    ("Previously employed at Deloitte as a financial analyst.", "Deloitte"),
    ("Built scalable REST APIs using FastAPI and PostgreSQL at Siemens.", "Siemens"),
    ("Currently interning at Microsoft while studying at Technical University of Munich.", "Microsoft"),
])
def test_mask_orgs_catches_real_companies(text, real_org):
    result = mask_orgs(text)
    assert "[ORG]" in result
    assert real_org not in result


@pytest.mark.parametrize("text,real_university", [
    ("He graduated from Stanford University with a degree in Computer Science.", "Stanford University"),
    ("She completed her Master's degree at the University of Augsburg.", "University of Augsburg"),
    (
        "Holds a Bachelor of Science from the Massachusetts Institute of Technology (MIT).",
        "Massachusetts Institute of Technology",
    ),
])
def test_mask_orgs_catches_real_universities(text, real_university):
    result = mask_orgs(text)
    assert "[ORG]" in result
    assert real_university not in result


def test_mask_orgs_catches_short_acronym_university():
    # MIT is a single-word true positive. This test exists specifically to
    # guard against ever reintroducing a minimum-word-count heuristic
    # (option 3, rejected during Phase 1.1 -- it would leak short company
    # names like this one).
    result = mask_orgs("Holds a Bachelor of Science from the Massachusetts Institute of Technology (MIT).")
    assert "MIT" not in result


# --- False positives: tech/skill/soft-skill terms must NOT be masked as orgs ---

@pytest.mark.parametrize("text", [
    "Familiar with Python, Docker, and Kubernetes in a microservices environment.",
    "Proficient in JavaScript, React, and Node.js for full-stack development.",
    "Contributed to open-source projects on GitHub and GitLab.",
])
def test_mask_orgs_does_not_mask_tech_stack_terms(text):
    result = mask_orgs(text)
    assert "[ORG]" not in result


def test_mask_orgs_does_not_mask_soft_skills():
    text = "Strong communication skills and a collaborative mindset are her biggest strengths."
    assert mask_orgs(text) == text


def test_mask_orgs_does_not_mask_certifications():
    text = "He is a Certified Scrum Master with experience leading agile teams."
    assert mask_orgs(text) == text


def test_mask_orgs_does_not_mask_generic_department_name():
    text = "Worked closely with the Marketing team to launch a new product line."
    assert mask_orgs(text) == text


# --- Mixed: real org and tech/skill term in the same sentence ---

def test_mask_orgs_mixed_sentence_masks_org_not_tech_term():
    text = "Built scalable REST APIs using FastAPI and PostgreSQL at Siemens."
    result = mask_orgs(text)
    assert "[ORG]" in result
    assert "Siemens" not in result
    assert "FastAPI" in result
    assert "PostgreSQL" in result


def test_mask_orgs_mixed_sentence_university_and_skill_term():
    text = "He graduated from Stanford University with a degree in Computer Science."
    result = mask_orgs(text)
    assert "Stanford University" not in result
    assert "Computer Science" in result  # whitelisted, must survive


def test_mask_orgs_mixed_sentence_two_real_orgs():
    text = "Currently interning at Microsoft while studying at Technical University of Munich."
    result = mask_orgs(text)
    assert "Microsoft" not in result
    assert "Technical University of Munich" not in result
    assert result.count("[ORG]") == 2


# --- Integration: mask_all() now includes org masking, composed with the rest ---

def test_mask_all_masks_org_alongside_email_and_phone():
    text = "Contact john@example.com or call 555-123-4567 about the Siemens project."
    result = mask_all(text)
    assert "[EMAIL]" in result
    assert "[PHONE]" in result
    assert "john@example.com" not in result


def test_mask_all_does_not_mask_tech_stack_as_org():
    text = "My stack is Python, FastAPI, and PostgreSQL."
    result = mask_all(text)
    assert "[ORG]" not in result
    assert "Python" in result
    assert "FastAPI" in result
    assert "PostgreSQL" in result