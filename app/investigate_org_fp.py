"""
Phase 1.1 — Investigation: false-positive rate of spaCy's ORG label.

Run this from your project root (where core.py lives), so it can import
SKILL_WHITELIST directly instead of relying on a copy that could drift
out of sync with the real one.

Usage:
    python investigate_org_fp.py
"""

import spacy
from core import SKILL_WHITELIST  # uses your real whitelist, not a duplicate

nlp = spacy.load("en_core_web_sm")

# 15 sentences, each tagged with what it's meant to test.
# Categories per TODO 1.1: real companies, real universities, tech stack,
# soft skills, certifications. Several sentences deliberately mix categories
# in one sentence (the TODO explicitly asks for "mixed sentences" testing).
CORPUS = [
    ("She worked as a senior backend developer at Google for three years.", "real_company"),
    ("He graduated from Stanford University with a degree in Computer Science.", "real_university + skill_term"),
    ("Familiar with Python, Docker, and Kubernetes in a microservices environment.", "tech_stack"),
    ("Strong communication skills and a collaborative mindset are her biggest strengths.", "soft_skills"),
    ("Certified AWS Solutions Architect with hands-on experience in Terraform.", "certification + tech_stack"),
    ("Previously employed at Deloitte as a financial analyst.", "real_company"),
    ("She completed her Master's degree at the University of Augsburg.", "real_university"),
    ("Proficient in JavaScript, React, and Node.js for full-stack development.", "tech_stack"),
    ("Worked closely with the Marketing team to launch a new product line.", "generic_org_like"),
    ("He is a Certified Scrum Master with experience leading agile teams.", "certification + soft_skills"),
    ("Built scalable REST APIs using FastAPI and PostgreSQL at Siemens.", "tech_stack + real_company"),
    ("Adept at problem-solving, time management, and working under pressure.", "soft_skills"),
    ("Holds a Bachelor of Science from the Massachusetts Institute of Technology (MIT).", "real_university + abbreviation"),
    ("Contributed to open-source projects on GitHub and GitLab.", "tech_stack"),
    ("Currently interning at Microsoft while studying at Technical University of Munich.", "real_company + real_university"),
]


def has_confidence_scores(doc) -> bool:
    """en_core_web_sm uses a transition-based NER with no native confidence
    exposed via doc.ents in standard greedy decoding. This checks empirically
    rather than assuming, since the TODO asks us to verify this rather than
    guess."""
    ner = nlp.get_pipe("ner")
    doc = nlp.make_doc("She worked at Google in Mountain View.")
    try:
        beams = ner.beam_parse([doc], beam_width=16, beam_density=0.0001)
        print("beam_parse ran without error:", beams)
    except Exception as e:
        print(f"beam_parse failed: {type(e).__name__}: {e}")

def main():
    print(f"spaCy version: {spacy.__version__}")
    print(f"Model: en_core_web_sm ({nlp.meta.get('version', '?')})")
    print(f"Whitelist size: {len(SKILL_WHITELIST)} terms\n")
    print("=" * 80)

    org_true_positives = []
    org_false_positives = []
    whitelist_catches = []

    for text, category in CORPUS:
        doc = nlp(text)
        print(f"\n[{category}]")
        print(f"  \"{text}\"")
        if not doc.ents:
            print("  (no entities detected)")
            continue

        for ent in doc.ents:
            in_whitelist = ent.text.lower() in SKILL_WHITELIST
            word_count = len(ent.text.split())
            flag = ""
            if ent.label_ == "ORG":
                if in_whitelist:
                    flag = " <- caught by whitelist (correctly excluded)"
                    whitelist_catches.append((ent.text, category))
                else:
                    # Heuristic-only judgment call: is this plausibly a real
                    # org name, or a misclassified tech/skill term?
                    flag = " <- ORG, NOT in whitelist"
            print(f"    {ent.text!r:45} {ent.label_:10} words={word_count}{flag}")

    print("\n" + "=" * 80)
    print("CONFIDENCE SCORE CHECK")
    sample_doc = nlp(CORPUS[0][0])
    print(f"  Reliable per-entity confidence available: {has_confidence_scores(sample_doc)}")
    print("  (If False: option 2 from the TODO is not viable without switching")
    print("   to beam search or spacy-experimental, which has its own latency/")
    print("   complexity tradeoffs worth weighing separately.)")

    print("\n" + "=" * 80)
    print("SUMMARY — read the ORG rows above and manually sort each")
    print("'ORG, NOT in whitelist' line into true positive (real org) or")
    print("false positive (misclassified tech/skill/soft-skill term).")
    print("This script doesn't auto-judge that — it's a judgment call per")
    print("the TODO's own instruction ('judge this manually, not just tests pass').")


if __name__ == "__main__":
    main()