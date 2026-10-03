"""PR #173 checks what the README says today, not the KILO-era process rules it no longer states.

The gate required four phrases of the old KILO README ("one implementation PR at a time", "single-theme",
"fast-by-default", "--e2e"). PR #316 rewrote the README for the product and AGENTS.md 0.2 replaced the process
("Pack related work into one PR"), so the first phrase would make the README contradict current policy and the
others describe CI that PR #308 removed. The README pointers and the claim scans still apply.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from thinkbox import kilo_pr173_chronicle_honesty as pr173

ROOT = Path(__file__).resolve().parents[2]

POINTERS = (
    "docs/roadmaps/kilo-post-170-pr-roadmap.md",
    "verify_kilo_spine.py",
    "verify_kilo_beyond_kilo_lint.py",
    "TEST VERIFIED",
)


def _docs(readme: str) -> dict[str, str]:
    docs = {str(rel): (ROOT / rel).read_text(encoding="utf-8") for rel in pr173.CHRONICLE_DOC_RELS}
    docs[str(pr173.README_REL)] = readme
    return docs


def _codes(readme: str) -> set[str]:
    return {v.code for v in pr173.validate_chronicle_documents(_docs(readme))[1]}


class TestReadmeScope(unittest.TestCase):
    def test_a_readme_with_the_pointers_and_without_the_old_process_phrases_passes(self) -> None:
        readme = "# Product README\n\n" + "\n".join(POINTERS) + "\n"
        self.assertEqual(_codes(readme), set())

    def test_the_old_process_phrases_are_no_longer_demanded(self) -> None:
        self.assertFalse(hasattr(pr173, "README_HONESTY_MARKERS"))

    def test_a_missing_pointer_is_still_a_violation(self) -> None:
        for missing in POINTERS:
            readme = "\n".join(p for p in POINTERS if p != missing)
            self.assertIn("readme_required_pointer_missing", _codes(readme), missing)

    def test_forbidden_claims_in_the_readme_are_still_violations(self) -> None:
        pointers = "\n".join(POINTERS)
        self.assertIn("forbidden_literal_claim", _codes(pointers + "\nKILO LIVE VERIFIED\n"))
        self.assertIn("affirmative_kilo_live_claim", _codes(pointers + "\nThe KILO build is production ready.\n"))

    def test_the_repository_readme_passes(self) -> None:
        ok, violations = pr173.validate_chronicle_documents()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])


if __name__ == "__main__":
    unittest.main()
