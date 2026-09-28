# Build log

| Date (IST) | What changed | Why |
|---|---|---|
| 2026-09-28 | Project skeleton: reference data (catalogue, Amazon condition scale with sources, rule table), single-call Gemini inspection, deterministic checks and rules, evidence record, SQLite store with tenant isolation, overrides and audit log, operator UI, CLI, eval harness, 26 unit tests | Core workflow first, per the brief |
| 2026-09-28 | Documented contradictions in the sample data (docs/FINDINGS.md) | Honesty rule 3 |
| 2026-09-28 | First live Gemini runs: added retries/back-off and more fallback models after HTTP 503 (model overloaded); fail-open kept the case | Live test |
| 2026-09-28 | Bug: completeness returned PASS (0/0) for a SKU missing from the catalogue -> now UNCERTAIN | Found in live earbuds test |
| 2026-09-28 | New rule R09B: if unseen parts could change the disposition, send to review | Earbuds test: left earbud not verifiable while other parts missing |
