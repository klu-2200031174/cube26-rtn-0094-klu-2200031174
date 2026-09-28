# Build log

| Date (IST) | What changed | Why |
|---|---|---|
| 2026-09-28 | Project skeleton: reference data (catalogue, Amazon condition scale with sources, rule table), single-call Gemini inspection, deterministic checks and rules, evidence record, SQLite store with tenant isolation, overrides and audit log, operator UI, CLI, eval harness, 26 unit tests | Core workflow first, per the brief |
| 2026-09-28 | Documented contradictions in the sample data (docs/FINDINGS.md) | Honesty rule 3 |
| 2026-09-28 | First live Gemini runs: added retries/back-off and more fallback models after HTTP 503 (model overloaded); fail-open kept the case | Live test |
| 2026-09-28 | Bug: completeness returned PASS (0/0) for a SKU missing from the catalogue -> now UNCERTAIN | Found in live earbuds test |
| 2026-09-28 | New rule R09B: if unseen parts could change the disposition, send to review | Earbuds test: left earbud not verifiable while other parts missing |
| 2026-09-28 | Consistency fix: same earphone photos gave DISPOSE once and RESTOCK once (model flipped between 'lightly used' and 'opened'). Hygiene rule R08 now keys on sealed vs not sealed | Live repeat test |
| 2026-09-28 | Redesigned operator UI (decision pipeline, evidence links, record stats); household items added to catalogue | Usability |
| 2026-09-28 | Latency fix: with the primary model overloaded, retries could keep an operator waiting for minutes. Busy models are now skipped immediately, total wait capped at 75 s, unfinished inspections show a Retry button | Live use: inspections felt stuck |
| 2026-09-28 | Catalogue fix: earbuds listed as separate "left" and "right" parts, which photos cannot tell apart -> one part "earbuds (pair of 2)" | Live earbuds test |
