# G002 Candidate Review Note Schema and Builder Evidence

Changed files:
- `src/models.py`
- `src/review_notes.py`

Evidence:
- Added `CandidateReviewNote` dataclass in the existing `Serializable` style.
- Added optional `Candidate.review_note` field without changing ranking/scoring semantics.
- Added `src/review_notes.py` helper/builder outside rendering logic.
- Builder uses existing candidate rationale, risks, score inputs, provenance, macro status/provider, and generated context.
- Explicit first-pass near-miss/exclusion decision: ranked candidates get notes; excluded/near-miss cases are summarized separately by top exclusion categories (`top_exclusion_categories_only`).
- Verification: `python3 -m py_compile src/models.py src/review_notes.py` and an import smoke constructing a note from a sample candidate.
