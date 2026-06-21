"""
Tests for the verb/preposition boundary-trimming logic inside _mask_entities().

Strategy note: these tests inject synthetic spaCy Doc objects (built via
spacy.blank("en"), with explicit words/POS tags/entity spans) instead of
running the real en_core_web_sm model on raw sentences. This is deliberate:

- The trimming algorithm's correctness depends only on token.pos_ and
  token.text, not on which exact sentence produced them. Testing via
  controlled Doc construction makes assertions exact and reproducible,
  independent of spaCy model version drift -- a model upgrade could
  silently change real NER/POS output and break sentence-based tests for
  reasons that have nothing to do with this code.
- It lets us deliberately construct adversarial cases (see the two
  "overtrim" tests below) that represent a real structural risk in the
  algorithm, regardless of whether en_core_web_sm happens to mistag those
  exact words today.

mask_names() -- the real, unmodified public function -- is still the thing
under test. Only the model call (_nlp) is replaced via monkeypatch. The
trimming logic, span-overlap protection, and label/whitelist filtering all
run for real, unmodified.
"""
import spacy
from spacy.tokens import Doc, Span

from app.core import mask_names
import app.core as core

_VOCAB = spacy.blank("en").vocab


def _doc(text, words, spaces, pos_tags, ent_spans):
    """Build a synthetic Doc with explicit tokens/POS tags/entity spans.

    ent_spans: list of (start_token_idx, end_token_idx, label) tuples.
    """
    doc = Doc(_VOCAB, words=words, spaces=spaces, pos=pos_tags)
    doc.ents = [Span(doc, s, e, label=label) for (s, e, label) in ent_spans]
    assert doc.text == text, (
        f"Doc construction mismatch -- words/spaces don't reconstruct the "
        f"intended sentence: {doc.text!r} != {text!r}"
    )
    return doc


def _patch_nlp(monkeypatch, doc):
    """Replace core._nlp with a stub returning a pre-built Doc, regardless
    of the text passed in (the text is already baked into the Doc)."""
    monkeypatch.setattr(core, "_nlp", lambda text: doc)


# --- Boundary trimming: required TODO cases ---

def test_trim_leading_verb_contact(monkeypatch):
    text = "Contact John Smith for details"
    doc = _doc(
        text,
        words=["Contact", "John", "Smith", "for", "details"],
        spaces=[True, True, True, True, False],
        pos_tags=["VERB", "PROPN", "PROPN", "ADP", "NOUN"],
        ent_spans=[(0, 3, "PERSON")],  # spaCy mis-included "Contact" in the span
    )
    _patch_nlp(monkeypatch, doc)
    assert mask_names(text) == "Contact [NAME] for details"


def test_trim_leading_noun_tagged_email(monkeypatch):
    # "Email" at the start of a sentence is often POS-tagged NOUN, not
    # VERB -- this is exactly why the hardcoded lexical list exists
    # alongside the POS check; POS alone would miss this case.
    text = "Email Sarah Connor today"
    doc = _doc(
        text,
        words=["Email", "Sarah", "Connor", "today"],
        spaces=[True, True, True, False],
        pos_tags=["NOUN", "PROPN", "PROPN", "NOUN"],
        ent_spans=[(0, 3, "PERSON")],
    )
    _patch_nlp(monkeypatch, doc)
    assert mask_names(text) == "Email [NAME] today"


def test_trim_leading_verb_and_preposition(monkeypatch):
    # Two leading tokens to trim in sequence: "Write" (VERB) then "to" (ADP).
    text = "Write to John Smith"
    doc = _doc(
        text,
        words=["Write", "to", "John", "Smith"],
        spaces=[True, True, True, False],
        pos_tags=["VERB", "ADP", "PROPN", "PROPN"],
        ent_spans=[(0, 4, "PERSON")],
    )
    _patch_nlp(monkeypatch, doc)
    assert mask_names(text) == "Write to [NAME]"


def test_no_leading_verb_unaffected(monkeypatch):
    # Normal case: entity span is already clean (no leading verb
    # captured). Confirms the trimming loop is a no-op when there's
    # nothing to trim.
    text = "John Smith arrived early"
    doc = _doc(
        text,
        words=["John", "Smith", "arrived", "early"],
        spaces=[True, True, True, False],
        pos_tags=["PROPN", "PROPN", "VERB", "ADV"],
        ent_spans=[(0, 2, "PERSON")],
    )
    _patch_nlp(monkeypatch, doc)
    assert mask_names(text) == "[NAME] arrived early"


# --- Over-trim: actively trying to break it ---
#
# Originally both cases below leaked part of a real name as plaintext,
# because the trimming loop treated "this token is POS-tagged VERB/ADP"
# as proof the token wasn't part of the name -- false whenever the POS
# tagger mistagged a genuine name token. Fixed in core.py by dropping the
# POS-based condition and trimming only on the explicit lexical list.

def test_overtrim_fixed_for_mistagged_given_name(monkeypatch):
    # "Will" is a known weak spot for small POS taggers (dominant use as
    # a modal auxiliary) -- previously mistagging it as VERB caused it to
    # leak as plaintext. The fix removes that path entirely: trimming no
    # longer depends on POS at all, so this can't recur regardless of how
    # the tagger mistags a name token.
    text = "Will Smith starred in the film"
    doc = _doc(
        text,
        words=["Will", "Smith", "starred", "in", "the", "film"],
        spaces=[True, True, True, True, True, False],
        pos_tags=["VERB", "PROPN", "VERB", "ADP", "DET", "NOUN"],
        ent_spans=[(0, 2, "PERSON")],
    )
    _patch_nlp(monkeypatch, doc)
    assert mask_names(text) == "[NAME] starred in the film"


def test_lexical_trigger_word_as_surname_known_limitation(monkeypatch):
    # Known limitation, not fully resolved by the fix above: "to" is
    # itself one of the five hardcoded lexical trigger words, so a name
    # component literally spelled "To" (e.g. the romanized Vietnamese
    # surname "To"/"Tô") still gets trimmed -- not because of a POS
    # mistag, but because the trigger word and a legitimate name token
    # are the same string with no signal to disambiguate them. This is
    # the same class of intentional scope boundary as the other
    # known_limitation tests in test_core.py: rare, and not worth chasing
    # given the cost of disambiguating it (see TODO/CONTEXT.md "What NOT
    # To Do"). Affects "call"/"write"/"email"/"contact"/"to" as leading
    # surname tokens specifically -- not the general case.
    text = "To Van Minh called yesterday"
    doc = _doc(
        text,
        words=["To", "Van", "Minh", "called", "yesterday"],
        spaces=[True, True, True, True, False],
        pos_tags=["ADP", "ADP", "PROPN", "VERB", "ADV"],
        ent_spans=[(0, 3, "PERSON")],
    )
    _patch_nlp(monkeypatch, doc)
    # Documents actual (improved but imperfect) post-fix behavior: "To"
    # still leaks, "Van" no longer does (that part of the original bug,
    # the POS mistag on "Van", is resolved).
    assert mask_names(text) == "To [NAME] called yesterday"


# --- Empty-span guard ---

def test_fully_trimmed_single_token_entity_discarded(monkeypatch):
    # If the entity is ENTIRELY a trimmable word (here: a single
    # mistagged "contact"), start_char should reach or overshoot
    # end_char (overshoot happens if a trailing space gets skipped past
    # the entity boundary), and the `start_char < end_char` guard must
    # discard the span -- not mask nothing, not crash, not mask the
    # wrong range.
    text = "Please contact us soon"
    doc = _doc(
        text,
        words=["Please", "contact", "us", "soon"],
        spaces=[True, True, True, False],
        pos_tags=["INTJ", "VERB", "PRON", "ADV"],
        ent_spans=[(1, 2, "PERSON")],  # "contact" alone mistagged PERSON
    )
    _patch_nlp(monkeypatch, doc)
    assert mask_names(text) == "Please contact us soon"


def test_fully_trimmed_multi_token_entity_at_string_end_discarded(monkeypatch):
    # Same guard, but with two trimmable tokens and the entity ending
    # exactly at the end of the string (no trailing whitespace to
    # overshoot past) -- checks the boundary is handled correctly via
    # equality (start_char == end_char), not just via overshoot.
    text = "Reach out and email contact"
    doc = _doc(
        text,
        words=["Reach", "out", "and", "email", "contact"],
        spaces=[True, True, True, True, False],
        pos_tags=["VERB", "ADP", "CCONJ", "NOUN", "NOUN"],
        ent_spans=[(3, 5, "PERSON")],  # "email contact" mistagged PERSON
    )
    _patch_nlp(monkeypatch, doc)
    assert mask_names(text) == "Reach out and email contact"
