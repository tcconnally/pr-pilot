# Claims Audit — pr-pilot

**Date:** 2026-06-12 · **Audited:** README.md, AGENTS.md vs code on `main`

## Findings (ranked by judge visibility)

### MEDIUM — "90%+ autonomous code review — no human in the loop"

- **Claim:** README differentiator section.
- **Reality:** The 5-agent chain (Reviewer, Fixer, Tester, Verifier, Escalator — all present in `src/agents/`, none stubbed) is real, but the 90% figure is asserted, not measured. No eval set, no acceptance-rate data.
- **Fix:** either soften to "designed for autonomous review" or attach a small measured sample.

### MEDIUM — "finds bugs … then generates and verifies fixes without human intervention"

- **Reality:** The pipeline exists and the orchestration engine wires it, but verification quality depends on Gemini outputs that CI exercises only with stub keys. The end-to-end "verified fix" path has no recorded successful run in the repo (no fixture transcript, no demo artifact).
- **Fix:** commit one captured end-to-end run (input PR → review → fix → verification) as a demo artifact.

## Verified claims

- 5 agents exist and are non-trivial implementations (`reviewer.py`, `fixer.py`, `tester.py`, `verifier.py`, `escalator.py`). ✓
- Test suite — 59 test functions across 8 files (README-era claim of 49 now undersells it); full suite passes in CI with stub `GEMINI_API_KEY`. ✓
- Stripe billing and dashboard auth have dedicated tests (`test_stripe_handler.py`, `test_dashboard_auth.py`). ✓
- Package imports cleanly with stub credentials (smoke-test CI green). ✓
